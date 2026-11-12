# Local settings for benchmark-report (example)

Copy this file to `local.md` in the same folder and edit it. `local.md` is private: don't publish it.

## Where things live

- Benchmarks: `<repo>/scripts/bench/<feature>/`
- Reports: `<repo>/benchmarks/reports/<feature>/`
- Held-out cases with customer data: `~/private-bench-data/<feature>/` (never in git; record ids and hashes only)

## Existing benchmarks

- `invoice-reader`: `my-app/scripts/bench/invoice/`, gate `thresholds.json`, last report 2026-01-10.

## House rules

- Headline numbers use k = 5.
- A separate reviewer tries to game every new scorer before its first report.
- Reports follow our design guide at `my-app/DESIGN.md`.
