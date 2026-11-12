# Agent skills

Skills I use every day to run [BuildX](https://buildx.pro) with AI coding agents, cleaned up so anyone can use them. Each one is a folder with a `SKILL.md` that agent tools such as [OpenCode](https://opencode.ai) and Claude Code load when the task matches.

| Skill | What it does |
|---|---|
| [`agent-efficiency`](skills/agent-efficiency) | Finds out which agents and sessions use up your paid model quota, explains where the tokens go (long sessions, cache rebuilds, compaction, plugins that break the prompt cache), and recommends a cheaper per-agent model plan backed by current prices and benchmarks. Includes a usage script for OpenCode's local database. |
| [`parallel-async`](skills/parallel-async) | Finds and safely removes request waterfalls in TypeScript/JavaScript backends: independent awaits run one after another, N+1 loops, duplicate lookups per request. Ships a scanner that ranks candidates by how hot the code path is, and a checklist for when parallelising is *not* safe. |
| [`benchmark-report`](skills/benchmark-report) | Proves an AI feature works the way AI labs prove model capability: frozen answer keys, a held-out set, repeated runs with bootstrap error bars, baselines, a ratcheting regression gate and a "system card" report that only makes qualified claims. Includes a standard-library bootstrap script. |

## Install

With the [skills CLI](https://github.com/vercel-labs/skills):

```bash
npx skills add dro-marin/skills
```

Or copy a folder from `skills/` into your agent's skill directory (`~/.config/opencode/skill/` for OpenCode, `~/.claude/skills/` for Claude Code).

Script paths in each `SKILL.md` are relative to that skill's folder. Requirements: the scripts need Python 3.8+ (standard library only) or bash and `sqlite3`. `agent-efficiency`'s usage script reads OpenCode 2.x's session database; the rest of that skill applies to any agent tool.

## Your own settings: `local.md`

Every skill works with no setup. To tailor one to your setup, copy its `local.example.md` to `local.md` in the same folder and edit it: extra machines, where things live, which models you allow, house rules. The skill reads `local.md` first and lets it override its defaults.

`local.md` is ignored by git here. If you keep your settings in another repo, `tools/install.sh` installs the skills and copies your private files on top (an overlay can also add trigger words to a skill's description with `description.txt`, or a note at the top with `preamble.md`). It backs up what it replaces and keeps an existing `local.md` if the overlay has none:

```bash
tools/install.sh --dest ~/.config/opencode/skill --overlays ~/my-private-repo/skill-overlays        # preview
tools/install.sh --dest ~/.config/opencode/skill --overlays ~/my-private-repo/skill-overlays --apply
```

## Contributing

Issues and pull requests are welcome. Before opening one, run `tools/check-public.sh` and `python3 skills/parallel-async/scripts/test_find_sequential_awaits.py`.

## License

MIT. See [LICENSE](LICENSE).
