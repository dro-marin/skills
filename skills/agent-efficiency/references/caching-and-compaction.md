# Prompt caching, compaction and cache rebuilds

Model changes are the obvious lever. In practice, how sessions use the prompt cache often costs as much as which model they use. Measure with the queries at the end before quoting any number.

## How the cost works

Every turn re-sends the whole conversation. Providers with prompt caching (Anthropic, and others with different rules) charge three rates:
- **cache read**: everything already cached. On Anthropic, 0.1x the normal input price on most models, less on some newer ones.
- **cache write**: anything not cached yet. On Anthropic, 1.25x input for the 5-minute cache, 2x for the 1-hour cache.
- **output**: the model's reply.

So a cache write costs roughly 12-25x a read, depending on the model and cache length. Check the provider's pricing page (or models.dev) for the model you use. Two consequences:
1. Cost per turn grows with conversation size, because the whole history is read every turn.
2. Any turn that misses the cache re-pays the whole conversation at the write price. A 400k-token session that loses its cache pays for 400k tokens of writes on the next turn.

Measure your own split (reads vs writes vs output) with the first query below. In one heavy multi-agent setup we measured, reads were about half the cost and writes about 40%. Output, the part people usually think about, was about 10%.

## Compaction

OpenCode compacts a session (summarises it and starts a fresh context) when it nears the model's context limit. With 1M-token models that is very late: a session can run hundreds of turns above 300k, each one re-reading everything.

Settings in `opencode.json` (key names as of OpenCode 2.2; check the docs for your version):

```json
"compaction": { "auto": true, "buffer": 700000, "keep": { "tokens": 30000 } }
```

- `buffer` is the number of tokens kept free. With a 1M window, `700000` compacts at about 300k. Models with smaller windows than the buffer fall back to the default, so this does not break them.
- Don't use a percentage-style setting that would compact small-window models below the size every session starts at (system prompt, tools and instructions are often 50-100k on their own).
- A compaction costs a few dollars on a frontier model and forces one cache rebuild on the next turn. It pays off once a session would otherwise run a few dozen turns past the threshold.
- The summary itself can run on a cheap model (`agents.compaction.model`), and `experimental.background_compaction: true` lets it run without blocking the session (experimental; check it exists in your version).
- Measure what compaction costs you: rows with `type='compaction'` (query below). In the setup above it was under 2% of the bill, far less than the long turns it removed.

Run the "cost by conversation size" query before and after the change. If most of the cost sits above your threshold, compact earlier.

## Cache rebuilds (turns that re-write 50k+ tokens)

Sort large cache writes by what came before them:

| Cause | Expected? | What to do |
|---|---|---|
| First call of a session | yes | Keep the fixed prompt small (instructions, tool list, skill descriptions) |
| Resumed after the cache expired (5 min or 1 h idle) | yes | Shorter sessions make each one cheaper; a 1-hour cache doubles write cost, so measure before enabling |
| Model, effort or agent switched mid-session | avoidable | Start a new session instead of switching |
| Instruction files, skills or config edited | avoidable | Every running session re-pays its prompt on the next turn: batch such edits |
| **Rebuild under 5 minutes after the last call, nothing visible in between** | **no** | Something is changing text near the start of the prompt. Find it (below) |

### The plugin trap

The last row is worth hunting down. In one setup it was the single largest avoidable cost, about 16% of the weekly bill, and the cause was our own plugin.

A plugin added a live status summary (task counts, a revision number) to the system prompt on every request, by pushing text into `event.system` from its `context` hook. OpenCode places cache breakpoints on the first and last system blocks, so whenever that summary changed, everything after it, the entire conversation, was written to the cache again. Sessions using that plugin rebuilt on 4.7% of quick back-to-back calls; other sessions rebuilt on 0.1%.

The fix: plugin text that goes into the system prompt must stay byte-for-byte identical between "cold" points (first request, after compaction, after a model or agent change, after the cache has expired anyway). Compute live summaries only at those points and freeze them in between, labelled as possibly stale. Refresh immediately only when it matters for safety (for example, work was paused or cancelled).

To check your own setup, split the quick-rebuild rate by any feature you suspect (a plugin's tool, an agent, a provider) using the last query below. A healthy rate is well under 1%.

## Sessions stuck on a retired model

A session keeps the model it last used; changing agent defaults does not move existing sessions. After retiring a model, find sessions whose latest `assistant` or `model-switched` row in `session_message` used it, and switch idle ones through the OpenCode server API (`POST /api/session/<id>/model` with body `{"model":{"providerID":"…","id":"…","variant":"…"}}` on 2.x; check the API docs for your version) or by reopening them.

## Queries (read-only: `sqlite3 -readonly ~/.local/share/opencode/opencode.db`)

Cost split, Anthropic only (adjust the provider):
```sql
select round(sum(json_extract(data,'$.tokens.cache.read'))/1e6) read_M,
       round(sum(json_extract(data,'$.tokens.cache.write'))/1e6) write_M,
       round(sum(json_extract(data,'$.tokens.output'))/1e6,1) output_M,
       round(sum(json_extract(data,'$.cost'))) usd
from session_message where type='assistant' and json_extract(data,'$.model.providerID')='anthropic'
  and time_created > (strftime('%s','now')-7*86400)*1000;
```

Cost by conversation size:
```sql
with m as (select coalesce(json_extract(data,'$.cost'),0) c,
  coalesce(json_extract(data,'$.tokens.input'),0)+coalesce(json_extract(data,'$.tokens.cache.read'),0)
  +coalesce(json_extract(data,'$.tokens.cache.write'),0) ctx
  from session_message where type='assistant' and json_extract(data,'$.model.providerID')='anthropic'
  and time_created > (strftime('%s','now')-7*86400)*1000)
select case when ctx<200000 then 'a <200k' when ctx<300000 then 'b 200-300k'
  when ctx<500000 then 'c 300-500k' else 'd 500k+' end size,
  count(*) calls, round(sum(c)) usd, round(100.0*sum(c)/(select sum(c) from m),1) pct
from m group by 1;
```

Compaction cost: rows with `type='compaction'` carry `$.cost`, `$.tokens`, `$.reason` and `$.model`.

Cache rebuilds by gap since the previous call:
```sql
with m as (select time_created t, coalesce(json_extract(data,'$.tokens.cache.write'),0) cw,
  lag(time_created) over (partition by session_id order by seq) pt
  from session_message where type='assistant' and json_extract(data,'$.model.providerID')='anthropic'
  and time_created > (strftime('%s','now')-7*86400)*1000)
select case when cw<50000 then 'incremental' when pt is null then 'first' when t-pt>3600000 then '>1h'
  when t-pt>300000 then '5-60min' else '<5min' end kind,
  count(*) calls, round(sum(cw)/1e6) write_M
from m group by 1;
```

Quick-rebuild rate, split by sessions that used a suspect feature (here: any call to a tool named `my_tool`; change the `like` patterns):
```sql
with flagged as (select distinct session_id from session_message
  where type='assistant' and time_created > (strftime('%s','now')-7*86400)*1000
  and data like '%"name":"my_tool"%'),
m as (select session_id, time_created t, coalesce(json_extract(data,'$.tokens.cache.write'),0) cw,
  lag(time_created) over (partition by session_id order by seq) pt
  from session_message where type='assistant' and json_extract(data,'$.model.providerID')='anthropic'
  and time_created > (strftime('%s','now')-7*86400)*1000)
select case when session_id in (select session_id from flagged) then 'flagged' else 'other' end grp,
  count(*) quick_pairs, sum(cw>=50000) rebuilds, round(100.0*sum(cw>=50000)/count(*),2) pct
from m where pt is not null and t-pt<=300000 group by 1;
```
On a database of many GB this takes minutes. To measure only after a fix, replace the time filter with `time_created > <epoch ms of the fix>`.
