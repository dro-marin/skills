# Usage queries (read-only)

Database: `~/.local/share/opencode/opencode.db` by default (it can grow to many GB). Always open it with `sqlite3 -readonly`, and run big scans with `nice` on shared machines.

Model calls live in `session_message` with `type='assistant'`. Useful fields in the `data` JSON column:

| Field | Meaning |
|---|---|
| `$.agent` | agent name |
| `$.model.providerID`, `$.model.id`, `$.model.variant` | provider, model, effort variant |
| `$.cost` | API-equivalent USD (often 0 for flat-rate plans) |
| `$.tokens.input`, `$.tokens.output`, `$.tokens.reasoning` | token counts |
| `$.tokens.cache.read`, `$.tokens.cache.write` | prompt-cache tokens |

`time_created` is epoch milliseconds; `seq` orders messages within a session. Some OpenCode versions also have an older `message` table that is no longer updated: query `session_message`, and check `.tables` if a query returns nothing.

## Per day, per agent (tell history from a live misconfiguration)

```sql
select json_extract(data,'$.agent') agent,
       date(time_created/1000,'unixepoch','localtime') day,
       json_extract(data,'$.model.providerID')||'/'||json_extract(data,'$.model.id') model,
       count(*) n
from session_message
where type='assistant' and time_created > (strftime('%s','now')-7*86400)*1000
  and json_extract(data,'$.agent') in ('general','explore')
group by 1,2,3 order by 1,2;
```

## Effort variant mix for one agent

```sql
select coalesce(json_extract(data,'$.model.variant'),'default') variant, count(*),
       round(sum(json_extract(data,'$.cost')),0) usd
from session_message
where type='assistant' and json_extract(data,'$.agent')='build'
  and time_created > (strftime('%s','now')-7*86400)*1000
group by 1;
```

## Sessions costing the most (long-session check)

```sql
select session_id, count(*) turns, round(sum(json_extract(data,'$.cost')),0) usd,
       round(sum(json_extract(data,'$.tokens.cache.read'))/1e6,0) cache_read_M
from session_message
where type='assistant' and json_extract(data,'$.model.providerID')='anthropic'
  and time_created > (strftime('%s','now')-7*86400)*1000
group by 1 order by usd desc limit 10;
```

Session titles: the `session` table, or `opencode session list` (current project only).
