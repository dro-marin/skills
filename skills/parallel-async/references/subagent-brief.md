# Subagent brief (one subagent per repo, run in parallel)

Fill the `<...>` slots from `local.md` and the repo's agent instructions. Keep the rules verbatim.

---

Load the `parallel-async` skill and follow it.

Repo: <repo> (<stack: runtime, database and client, auth>). Work ONLY in <worktree path> on branch <branch> (from the main branch). Do NOT touch <the user's checkout>; it may have uncommitted work.

Goal: deep-scan the hot paths and fix UNNECESSARY sequential async calls: independent awaits one after another, awaits in loops over independent items, sequential fetches in server components, route handlers, server actions, middleware, layouts and generateMetadata, and session lookups repeated or awaited before unrelated work.

Hot paths to prioritise: <list>. Already done (don't redo; build on it): <list or "none">.
Known follow-ups you may take on if safe: <list or "none">.

Start with `python3 <skill dir>/scripts/find_sequential_awaits.py <worktree>`, then read the hot paths by hand for what the scanner can't see (cross-helper chains, duplicate per-request lookups).

Rules (from the skill, non-negotiable):
- Parallelise only truly independent work. Keep auth, membership and allowlist gates first for private data; a read may start early only if cheap, read-only, discarded on gate failure, and with errors swallowed until awaited.
- No Promise.all on a single database client or inside a transaction; no unbounded fan-out (one query or a pool of 4); respect bound-parameter limits; atomic multi-writes go in a batch or transaction.
- Preserve error precedence (allSettled and rethrow in the original order where needed); no promise sharing across requests.
- No behaviour, copy, schema or UI changes; no new dependencies; comments only where the reason is not obvious.
- Run typecheck, lint and relevant unit tests (full suite if reasonable). No e2e, deploys, shared-database writes or paid API calls.
- Focused commits `perf(<area>): ...` on the branch. Do NOT push, open PRs, merge or deploy.

Report back: a table per change (file:function | was sequential | now | round trips saved), behaviour differences, spots deliberately left sequential with reasons, existing bugs noticed (not fixed), checks run and results, and the commit list.
