# Local notes for parallel-async (example)

Copy this file to `local.md` in the same folder. Keep one section per repo and update it after every run. `local.md` is private: don't publish it.

## my-app

- Stack: Next.js on Cloudflare Workers, D1 with Drizzle (100 bound parameters per query), Better Auth.
- Checks: `npm run typecheck`, `npm run lint`, `npx vitest run` (about 5 minutes).
- Hot paths: `app/[city]/[slug]/**`, `app/api/search`, `lib/db/queries.ts`, `middleware.ts`.
- Done (2026-01-10): metadata and page share one cached lookup; search filters run together.
- Keep sequential: the profile route loads the profile before reviews (most traffic; speculation would add 2 queries per view). Tag create loop (duplicate names race).
- Gotchas: the pre-commit hook runs the full suite; run checks by hand first.
- Open: `getStats` reads the whole table; flagged, not fixed.
