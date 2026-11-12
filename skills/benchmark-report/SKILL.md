---
name: benchmark-report
description: Prove an AI feature works the way frontier AI labs prove model capability - a frozen benchmark with an answer key, a held-out set, repeated runs with error bars, baselines, per-slice breakdowns, failure analysis, a ratcheted regression gate, and a "system card" style report with only qualified claims. Use whenever an AI feature is built, changed or marketed (extraction, classification, document Q&A, agents, any model or prompt swap), whenever someone asks "how accurate is it", "prove it", "benchmark", "eval", "score it", "accuracy report", "is the new version better", or wants a number for a customer, investor or landing page - even if they don't say "benchmark". Not for ordinary unit tests, load testing, or website performance audits.
---

# Benchmark report

Every AI feature should ship with evidence, not adjectives. Coding agents became trustworthy because tests gate every change; AI labs earn trust because they publish how they measured, what they measured on, how sure they are, and where the model fails. This skill applies both to your own features.

The rule it enforces: **no AI feature or AI change ships without a benchmark run, and no accuracy claim is made outside a benchmark report.**

## 0. Local settings

If a file named `local.md` sits next to this one, read it first. It says where benchmarks and reports live in the user's repos, which features already have one, and any house rules (for example, where private test data is kept). `local.example.md` shows the format.

## Why this matters

- Accuracy claims in most markets ("up to 98% accurate") are usually measured after human correction, on unstated data, with no error bars. A report a customer can check stands out.
- Benchmarks rot. OpenAI stopped reporting SWE-bench Verified in February 2026 after finding that at least 59.4% of the hard problems it audited had flawed tests, and that models had seen the answers in training. Apply the same skepticism to your own benchmarks.
- A benchmark that can be gamed will be gamed, usually by accident: prompt tuning on the test set, scorers that guess which item a result means from its value, gates that only watch the weakest variant. Each of these happened in a real benchmark before review caught it (see `references/lessons.md`).

## The workflow

It follows the three stages of NIST AI 800-2 (draft, January 2026): define the target, run the evaluation, analyze and report. `references/methodology.md` has the detail and the sources.

### 1. Define what is being measured

Write the claim before building anything, as one sentence with its scope:

> "The invoice reader extracts line-item quantities and prices that match a hand-checked key within 1% on typed PDF invoices in English. Handwritten and scanned invoices are out of scope."

Then write down:
- **Unit of evaluation** (a page, a document, a question, a line item) and the metric that answers the claim (F1, % within tolerance, exact match, latency p95).
- **What "correct" means**, including tolerances and the conventions the key assumes (units, rounding, what counts as one item). Conventions belong in the key, never only in someone's head.
- **Out of scope**, stated in the report, not discovered by a customer.

### 2. Build the dataset

- **Answer keys are computed, not typed.** Synthetic cases derive the key from the same model that generates the input; real cases need two independent annotators or a reconciled ground truth.
- **Bind the input to the key.** A test must fail if the input and the key drift apart: read the input back (parse the generated file) and re-derive the key, with negative controls (remove a drawn item, shorten a line, change a printed value) that must be caught.
- **Hold out a private set.** Keep 20-30% of cases out of every prompt, fine-tune, example and debugging session. Record each case's creation date and who has seen it. Tune on the dev split only.
- **Stratify.** Cover the slices customers care about (document type, source quality, language, easy and hard) so a total can't hide a weak slice.
- **Version the dataset** (schema version, case ids, generator commit). Never edit a case in place; add a new version.

### 3. Build the scorer, then attack it

- Settle **identity before value**: decide which key item a result row refers to without looking at its number, or value accuracy becomes self-fulfilling.
- Make scoring **order-invariant** and **deterministic** (sorted sums, stable tie-breaks); test with shuffled inputs.
- **Validate inputs at the scorer boundary**: finite, in-range values, whole numbers where counts are expected. Invalid rows count against the result.
- **Attack the scorer** before trusting it: ambiguous descriptions, duplicate flooding, split or negative values, wrong units, missing fields, reordered rows. If an obviously bad result can score 100, the scorer is broken.
- Have someone else (another person, or an independent reviewer agent) try to game it.

### 4. Run the evaluation

- **Freeze the protocol** per run: model id and version, prompt hash, temperature and other settings, ruleset version, dataset version, code commit, date, and region or hardware if it affects results. Save it next to the results.
- **Repeat runs.** Models are nondeterministic: run each case k times (k >= 3; 5 for headline numbers). Report the mean and spread. For pass/fail tasks report pass@1 and, where it matters, pass^k (all k succeed), which shows reliability.
- **Run baselines in the same harness**: the previous version, a trivial baseline (empty result, or "always the most common answer"), and where possible a human's accuracy and time on the same cases.
- **Log everything**: per-item results, latencies, tokens and cost, errors and timeouts. A timeout is a failure, not a missing value.

### 5. Analyze

- **Uncertainty**: 95% confidence intervals by bootstrap over cases (resample cases, not rows); see `scripts/bootstrap_ci.py`. To compare versions, use a paired bootstrap on the same cases and report the difference with its interval.
- **Slices**: per type, source, difficulty. Flag any slice with fewer than ~20 items as low confidence.
- **Failure analysis**: sample failures, classify the cause (model, scorer, key, ambiguous input), and fix the key when it is wrong. Audit the hardest failures for flawed answers before blaming the model.
- **Contamination check**: confirm no held-out case appeared in prompts, examples, fine-tuning data or debugging transcripts. If one did, retire it.

### 6. Gate

- A committed `thresholds.json` holds floors **per case x variant x metric** (overall and per slice). The gate fails if any floor drops.
- Floors only ratchet up after a passing run. Never lower a floor to ship; fix the regression or record an explicit, reviewed exception.
- Floors of 0 protect nothing. Say so until real results have been ratcheted in.
- Reject bad gate flags (missing or non-numeric thresholds) with a nonzero exit, so the gate can't be switched off by accident.

### 7. Report

Write the report from `references/report-template.md`. It is a "system card" for the feature: a one-paragraph summary first, then results with error bars, slices, baselines, failures with examples, methodology, reproduction details and known limitations. Keep it clear and plain; nothing decorative.

Only make **qualified claims**: what was measured, on what, with what uncertainty. "F1 0.94 (95% CI 0.91-0.96) on 120 typed English invoices; scans not tested", never "94% accurate".

## Where things live

- Benchmarks live in the product repo next to the feature they test.
- Reports live in the repo under `benchmarks/reports/<feature>/<date>-<version>.md`, so they are versioned with the code.
- Held-out cases containing real customer data never go in git: store them outside the repo and record only their ids and hashes.

## Reference files

- `references/methodology.md`: the detailed practices and their sources (NIST AI 800-2, lab system cards, the SWE-bench Verified lessons).
- `references/report-template.md`: the report layout to copy.
- `references/lessons.md`: real holes found in a production benchmark, as a checklist.
- `scripts/bootstrap_ci.py`: case-level bootstrap and paired comparison (Python 3.8+, standard library only).
