---
name: agent-efficiency
description: Measure which OpenCode agents and sessions use up your paid model budget (a subscription quota or an API bill), find where the tokens actually go (long sessions, cache rebuilds, compaction, plugins that break the prompt cache), research current prices and benchmark rankings for cheaper models, and recommend - then, once approved, apply - a per-agent model and effort plan. Use when someone says agent usage, usage breakdown, quota or limits running out, "we're burning through tokens", cheaper models, model routing, which agents can use a cheaper model, agent efficiency, token efficiency, or asks about compaction, prompt caching, cache rebuilds, long sessions, or sessions stuck on a retired model.
---

# Agent efficiency

Goal: spend the expensive model's budget only on work that needs it, and send everything else to cheaper models, without making the agents worse at their jobs. A recommendation is only useful if it rests on measured usage and current prices, so: **measure first, research second, recommend third, and change config only after the user says yes.**

Works with [OpenCode](https://opencode.ai) 2.x, which records every model call in a local SQLite database. Other agent tools are not supported by the scripts; the method still applies.

## 0. Local settings

If a file named `local.md` sits next to this one, read it before anything else. It holds the user's own setup: extra machines to measure, where to save snapshots, which models are allowed, and house rules that override the defaults below. `local.example.md` shows the format. Without one, use the defaults and ask the user for anything you need.

## 1. Measure usage (always first)

Paths below are relative to this skill's folder.

```bash
scripts/agent-usage.sh 7 --save                    # this machine, last 7 days
scripts/agent-usage.sh 7 --ssh my-server --save    # plus another machine over SSH
```

Read-only. For each machine it prints a `## <machine>` header, then `agent model variant calls api_usd cache_read_M` rows sorted by cost. It exits 1 if no machine returned data. Options: `--db PATH` (default `$OPENCODE_DB` or `~/.local/share/opencode/opencode.db`), `--ssh HOST` (repeatable; the remote needs `sqlite3`, and key-based SSH login), `--save` writes a snapshot to `$AGENT_USAGE_DIR` (default `~/.local/state/agent-efficiency/`) and prints the previous one so you can compare.

How to read it:
- `api_usd` is OpenCode's API-equivalent cost. On a subscription plan it is still the best proxy for how fast the quota drains. Flat-rate models often show `0`: compare those by call count instead.
- Work out each agent's share of the expensive model's `api_usd`. The top three usually dominate; don't spend the report on agents under ~1%.
- Before blaming a config, check *when* the calls happened (`references/queries.md`, per-day query). Rows from before a config change are history, not a bug.
- A large `cache_read_M` relative to calls means long sessions re-reading their history every turn. That is a session-length habit, not an agent setting; report it separately.
- For compaction, prompt caching, cache rebuilds and sessions stuck on a retired model, read `references/caching-and-compaction.md`. This is often where the biggest savings are.
- The OpenCode server loads agent config at start. Until it restarts, new calls still use the old models.

## 2. Read the current config

The global model and per-agent overrides are in `~/.config/opencode/opencode.json` (`model`, `agents.<name>.model`; older versions use `agent`); custom agents set `model:` in the frontmatter of `~/.config/opencode/agents/*.md` (or `agent/`). Model strings may carry an effort variant, e.g. `anthropic/<model>#medium`. Put it in one table: agent, model, variant, what the agent does.

## 3. Research prices and quality (fresh every run; these change monthly)

- **Prices and limits** for each candidate provider and plan, from the provider's own pricing page. Note monthly or weekly limits, peak vs off-peak pricing, free limited-time models, and any endpoint that trains on request data (a privacy decision for the user, not a free saving).
- **Exact model IDs and capabilities**: `opencode models` lists what is actually available. Check image input, tool calling and context size before recommending a model for a role that needs them.
- **Agent and coding leaderboards**: the LM Arena agent and WebDev boards, Terminal-Bench, SWE-bench Pro, Aider polyglot. Older benchmarks such as SWE-bench Verified are contaminated (their answers leaked into training data) and some of their tests are flawed, and no public benchmark is fully clean, so treat each as one signal. Prefer the benchmark's own leaderboard over vendor blog posts, note the date of each number, and weigh agent-style benchmarks above chat ones, since that is how these models will be used. Some leaderboards block plain fetches; use a search or scraping tool, or a browser.

Cite every number with its source and date. If a source can't be reached, say so instead of filling the gap from memory.

## 4. Recommend a plan

Classify each agent by what it actually does (read its description and prompt), then match it to the cheapest model that clears the bar for that class:

| Class | Typical agents | Default home |
|---|---|---|
| User-facing judgment, coordination, product and UI work | main orchestrator, planner | strongest model (tune effort, don't downgrade the model) |
| Safety gates | code reviewer, security reviewer | strongest model |
| Hard implementation or design | deep implementer, architecture consultant | strong model, usually medium effort |
| Bounded execution: search, research, tests, docs, ops | explore, general, test writer, librarian | cheap fast model |
| Describing images or video | screenshot or footage describer | cheapest model with image input |
| Taste or quality judging | render or design judge | test a cheap model side by side before switching |

Defaults worth keeping unless the user decides otherwise:
- Move low-judgment work to a cheap model before you downgrade judgment work to a mid-tier one. A reviewer that misses a bug costs more than it saves.
- Agents that read untrusted web content should favour robustness to prompt injection over price.
- Any new paid plan, upgrade or "extra usage" is spending: ask first.

House rules in `local.md` override all of the above.

Each recommendation needs: the agent, current model and effort, proposed model and effort, its share of expensive-model usage, the expected saving, the quality evidence (benchmark or arena rank vs the current model), and the risk. Rank by saving and include "keep as is" rows with a one-line reason so the user sees the whole picture. Give the non-config levers (session length, compaction settings, cache-breaking plugins or habits) their own section: they often beat any model swap.

Then ask which rows to apply. Changing the models someone relies on is their call.

## 5. Apply (approved rows only)

Follow `references/apply.md`: back up each file, change only the model line, verify the ID, copy to any other machines, restart, and save a usage snapshot as the baseline for the next comparison.

## Report format

1. Usage table: top agents by share of the expensive model's cost, with machine and window.
2. Candidate models: the 4-6 relevant ones with price, limits, image input yes/no, and benchmark and arena numbers with sources and dates.
3. Recommendations table plus "keep" rows.
4. Non-config levers, with their measured cost.
5. One question: which rows to apply.

Keep it scannable.
