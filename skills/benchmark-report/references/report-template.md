# {Feature} benchmark report - {version} ({date})

> Copy this file to `benchmarks/reports/{feature}/{date}-{version}.md` and fill
> every section. Delete these quote blocks. If a section has nothing, say why.

## Summary

One paragraph a customer can read: what the feature does, the headline result
as a qualified claim, how it compares to the previous version and to a person
doing the same task, and the biggest known limitation.

**Headline:** {metric} {value} (95% CI {low}-{high}) on {n cases} {scope}.
**Change vs {previous version}:** {+/- delta} (95% CI {low}-{high}).
**Not tested:** {scope gaps}.

## Results

| Metric | This version | Previous | Trivial baseline | Human |
|---|---|---|---|---|
| {primary metric} | {mean} ± {CI half-width} | | | |
| {secondary metric} | | | | |
| Latency p50 / p95 | | | | |
| Cost per {unit} | | | | |

> Error bars are 95% bootstrap intervals over cases. Runs: k = {k} per case.

## Results by slice

| Slice | n items | Score | 95% CI | vs previous |
|---|---|---|---|---|
| Document type: invoice | | | | |
| ... | | | | |
| Source: scanned | | | | |

> Flag any slice with fewer than ~20 items as low confidence.

## Where it fails

For each main failure category: what happened, how often, one concrete example
(input snippet or item, expected vs got), and the cause (model, scorer, key,
ambiguous input). Note any answer-key corrections made during this run.

## Gate

Pass or fail against `thresholds.json`, listing any floor that moved and why.

## Methodology

- **Claim:** {the one-sentence claim and scope}
- **Dataset:** {version, cases, provenance, held-out share, slices}
- **Conventions:** {measurement conventions the key assumes}
- **Scoring:** {matching rules, tolerances, metric definitions}
- **Contamination check:** {how held-out cases were kept out of prompts and tuning}

### Protocol

| Setting | Value |
|---|---|
| Model and version | |
| Prompt hash | |
| Sampling settings | |
| Trials per case | |
| Ruleset version | |
| Dataset version | |
| Scorer commit | |
| Code commit | |
| Date and environment | |

## Limitations

What this report does not show, in plain words.

## Reproduce

Exact commands, inputs and the commit, so anyone can rerun it and
get the same numbers.
