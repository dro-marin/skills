# Local settings for agent-efficiency (example)

Copy this file to `local.md` in the same folder and edit it. `local.md` is for your own setup only; don't publish it.

## Machines

- This machine: database at the default path.
- `my-server` (SSH alias): run with `--ssh my-server`. Slow CPU, so expect a full scan to take minutes.

## Snapshots

Save with `AGENT_USAGE_DIR=~/notes/agent-usage scripts/agent-usage.sh 7 --save`.

## Allowed models

- Strong: `anthropic/claude-opus-4-1`
- Cheap: `provider/cheap-flash-model`. Never use `provider/pro-model` (too slow for us).

## House rules (override the skill's defaults)

- Code review and security review always stay on the strongest model.
- Ask before any new paid plan or usage add-on.

## Where to record changes

Update the model list in `~/notes/agents.md` after applying.
