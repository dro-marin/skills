# Applying approved model changes

Change only the rows the user approved. Never touch an agent's prompt or permissions here; widening permissions is a separate decision.

## 1. Verify the model ID

The ID must appear in `opencode models`. Effort variants (`#low`, `#medium`, `#high`) only work if the provider supports them for that model; variants already in use in your config are known-good. If unsure, stop and offer the closest real IDs.

## 2. Back up and edit

```bash
D=$(date +%Y%m%d)
cd ~/.config/opencode
# custom agent defined in a markdown file
cp agents/<name>.md agents/<name>.md.bak-$D
sed -i.tmp 's|^model: .*|model: <new-id>|' agents/<name>.md && rm agents/<name>.md.tmp   # add a model: line under mode: if none exists
# built-in agents (build, plan, general, explore) and JSON-defined agents
cp opencode.json opencode.json.bak-$D
# then edit agents.<name>.model (older versions: agent.<name>.model) and check the JSON still parses
```

Show the diff (`diff -u <backup> <file>`) to the user.

## 3. Other machines

If the same config runs on more than one machine, change one copy (the source of truth) and copy it to the others with whatever you normally use (rsync, a dotfiles repo). Confirm each copy shows the new value; never hand-edit the copies separately.

## 4. Restart so running agents load it

The OpenCode server reads agent config at start. Restarting it disconnects every session on that machine, including the one you are talking in, and stops their running commands. Before restarting:
- check whether another session is in the middle of a deploy, migration or long build, and wait if so;
- tell the user the chat will drop and they will need to reopen it.

Sessions keep the model they last used. Existing sessions on a retired model need moving (see `caching-and-compaction.md`).

## 5. Record it

- Note which agents are on which model, the date and the backup suffix wherever the user keeps such notes (`local.md` says where, if anywhere).
- Run `scripts/agent-usage.sh 7 --save` so the next run has a baseline to compare against. Re-run after a week and compare.
