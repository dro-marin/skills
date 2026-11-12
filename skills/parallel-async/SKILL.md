---
name: parallel-async
description: Deep-scan a TypeScript/JavaScript repo's hot paths (pages, metadata, API routes, middleware, auth/session, database query helpers, serverless and edge handlers) for unnecessary sequential async calls and fix them safely - Promise.all for independent reads, start-early/await-late, reads behind gates, per-request cache() dedupe, batched IN queries instead of N+1 loops, capped concurrency pools, atomic batches for multi-writes. Ships a triage scanner (scripts/find_sequential_awaits.py). Use when the user says parallelize awaits, sequential awaits, waterfall, request waterfall, N+1, too many round trips, speed up hot paths, Promise.all, or /parallel-async. Works with Next.js, Cloudflare Workers, Node servers, Drizzle, postgres.js, D1 and similar stacks.
---

# Parallel async: remove unnecessary sequential awaits on hot paths

The goal is fewer round trips on the critical path **with identical behaviour**. A wrong parallelisation (auth bypass, lost update, broken ordering, connection exhaustion) is far worse than a missed one. When unsure, leave it sequential and list it under "left sequential".

## 0. Local settings

If a file named `local.md` sits next to this one, read it first. It holds per-repo notes: what earlier runs already fixed, what was left sequential on purpose and why, test commands, and known gotchas. `local.example.md` shows the format. After a run, add what you learned to it.

## 1. Set up (never on someone else's working branch)

- Work in a fresh branch, ideally a separate git worktree off the main branch, so the user's uncommitted work is never touched:
  `git fetch -q origin && git worktree add -b perf/parallel-async-<date> ../<repo>-parallel-async origin/main`
- Read the repo's agent instructions (`AGENTS.md`, `CLAUDE.md` or similar), then find: the runtime (serverless/edge, Node), the database client and how it is created (pool or single client, per request?), the auth/session entry point, and the high-traffic routes.
- Several repos: if your agent tool supports subagents, run one per repo in parallel with `references/subagent-brief.md`.

## 2. Find candidates

```bash
python3 scripts/find_sequential_awaits.py <repo-dir> [--kind SEQ] [--json]
```
The path is relative to this skill's folder. Python 3.8+, standard library only. Ranked by hot-path score `[n]` (middleware/proxy 5; page, layout, route, actions 4; api/functions 4; lib/db 2).
- `SEQ`: independent awaited statements in one block. Strongest signal.
- `GATED`: independent, but an existence check sits between (`if (!row) return null`). Candidate for read-behind-gate. Auth, permission, rate-limit and cache gates are hidden by default (`--auth-gated` shows them); those usually stay first.
- `LOOP`: await inside for/while/forEach. N+1 or one-at-a-time.
- `W`: touches writes or sends. Check ordering and atomicity before anything else.

The scanner is triage, not truth: roughly half its hits are fine as they are. It **cannot** see the following, so also read the hot paths by hand:
- chains across helpers (`a = await getA(); b = await helperThatAwaitsTwice()`), and helpers that await sequentially inside;
- the same lookup run twice per request: `generateMetadata` and the page, layout and page, a router re-entering itself, the session resolved separately by middleware, layout and route;
- per-request setup on every call (`CREATE TABLE IF NOT EXISTS`, schema probes) that only needs to run once per process or isolate;
- client components doing fetch waterfalls (lower priority than server paths).

## 3. Decide per candidate (all must hold to parallelise)

1. **No data dependency**: the later call uses nothing from the earlier one, directly or through derived values.
2. **No ordering side effect**: no write-then-read, foreign-key delete order, read-modify-write of the same row or field, create-if-missing that could duplicate under concurrency, rate-limited sends, or ordered output.
3. **Gates still gate**: auth, membership, allowlist and plan checks run before private data is *returned*. A read may start before the gate only if it is cheap, read-only, its result is discarded when the gate fails, and its errors cannot leak (attach `.catch(() => {})` to the early promise and `await` it after the gate). Never start a write or an external send before the gate.
4. **Real concurrency exists**: a single database client, a single connection, or anything inside a transaction runs serially anyway; `Promise.all` inside a transaction gains nothing and is unsafe with most drivers. Connection pools, HTTP-based database drivers and `fetch` are fine.
5. **Bounded fan-out**: never `Promise.all` over an unbounded list. Use one query (`inArray` / `= ANY($1)`) or a capped pool (4 is a good default).
6. **Error semantics preserved**: `Promise.all` rejects on the first failure. If the old code returned 404 before a later 503, use `Promise.allSettled` and rethrow in the original order. Use `allSettled` for partial results only where the old code tolerated partial failure.
7. **Worth it on the hot path**: don't add speculative queries to the busiest route if most requests would throw them away. Extra reads on miss paths are fine; say so in the report.

## 4. Fix patterns

```ts
// Independent reads
const [user, posts] = await Promise.all([getUser(id), getPosts(id)]);

// Start early, await late (the dependency covers only part of the work)
const typesP = getBookingTypes(slug);            // needs only the slug
const profile = await getProfile(slug);
if (!profile) return notFound();
const types = await typesP;

// Read behind a gate (the early promise must not throw unhandled)
const rowsP = readRows(projectId); rowsP.catch(() => {});
if (!(await canAccessProject(db, userId, projectId))) return null;
return rowsP;

// Same lookup in generateMetadata and the page, or layout and page: dedupe per request (React server)
import { cache } from "react";
export const getCityData = cache(async (city: string, slug: string) => { /* ... */ });

// N+1 -> one query per chunk (SQLite-based stores such as D1 cap bound parameters; chunk well under the cap)
const rows = (await Promise.all(chunks(ids, 90).map((c) => db.select().from(t).where(inArray(t.id, c))))).flat();

// Capped, ordered fan-out for genuinely per-item work (external APIs, object storage, rendering)
const out = await mapWithConcurrency(items, 4, (item) => work(item));

// Atomic multi-write: a batch or transaction, not Promise.all
await db.batch([db.delete(lines).where(eq(lines.orderId, id)), db.insert(lines).values(rows)]);

// Postgres: fold dependent-but-cheap lookups into one SQL statement (subquery, CTE, json_agg) instead of two trips.
```

A dependency-free `mapWithConcurrency`, if the repo has none:

```ts
export async function mapWithConcurrency<T, R>(items: readonly T[], limit: number, fn: (item: T, i: number) => Promise<R>): Promise<R[]> {
  const out = new Array<R>(items.length);
  let next = 0;
  let failed = false;
  const worker = async () => {
    while (!failed && next < items.length) {
      const i = next++;
      try { out[i] = await fn(items[i], i); } catch (err) { failed = true; throw err; }
    }
  };
  const workers = Math.min(Math.max(1, Math.floor(limit) || 1), items.length);
  await Promise.all(Array.from({ length: workers }, worker));
  return out;
}
```

**Never**
- share an in-flight promise across requests in Cloudflare Workers (a module-level memo of a *pending* promise): a request awaiting I/O started by another request can hang or error. Memoise resolved values, or use per-request `cache()`.
- parallelise create loops where two items can resolve to the same new row (duplicate tags, members, services).
- parallelise sends that share a budget (email, SMS, rate-limited APIs) or anything where order is visible to users.
- change copy, schema, UI or behaviour beyond timing. Don't add dependencies.

## 5. Verify and commit

- Install dependencies in the worktree if needed. Typecheck, lint, and unit tests for touched areas, then the full unit suite when reasonable. No end-to-end runs against live services, no deploys, no writes to shared databases, no paid API calls.
- Where cheap, add a test that proves the concurrency or the preserved semantics, for example a fake DB that records overlapping calls, or a check that 404 still wins over 503. Good tests fail on the old code for concurrency and pass on both for behaviour.
- One focused commit per area: `perf(<area>): <what now runs together>`.
- Don't push, open PRs, merge or deploy unless the user asks.
- Afterwards, record durable facts (done items, deliberate keeps, gotchas, follow-ups) in `local.md` so the next run builds on this one.

## 6. Report

Per repo, in plain words:
1. Table: `file : function` | was sequential | now | round trips saved (on the critical path, per request).
2. Behaviour differences, however small (extra reads on miss paths, different error surfacing, newly atomic writes).
3. Left sequential on purpose, with the reason (dependency, gate, ordering, cost).
4. Existing bugs noticed but not fixed (parameter limits, full-table reads, missing auth checks). Flag them; don't fix them in this change.
5. Checks run and results; commit list; branch and worktree path.
