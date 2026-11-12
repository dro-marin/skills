# Methodology: how frontier labs prove capability, applied to your features

## Sources

- NIST AI 800-2 (initial public draft, January 2026), "Practices for Automated Benchmark Evaluations of Language Models", Center for AI Standards and Innovation. https://doi.org/10.6028/NIST.AI.800-2.ipd
  Three stages: define objectives and select benchmarks; implement and run; analyze and report. Practices are cited below by number.
- OpenAI, "Why we no longer evaluate SWE-bench Verified" (2026-02-23). https://openai.com/index/why-we-no-longer-evaluate-swe-bench-verified/
- Frontier model system cards (Anthropic, OpenAI, Google DeepMind): one evaluation section per capability, stated methodology, discussion of error bars, external testers, and explicit shortcomings.

## Stage 1: define the target (NIST 1.1, 1.2)

- State the evaluation objective as the decision it informs ("can we advertise automatic extraction?", "is prompt v4 better than v3?").
- Check that the benchmark measures the construct, not a proxy: a scorer that rewards matching descriptions is measuring text overlap, not extraction skill.
- Use automated benchmarks only where answers are structured and verifiable. Subjective qualities (how good a UI looks, how helpful an answer is) need human review or a validated LLM judge.

## Stage 2: implement and run (NIST 2.1-2.4)

Protocol settings to fix and report for every run:

| Setting | Example |
|---|---|
| Model and version | provider/model-id, plus the date if the provider updates models in place |
| Prompt / system message | file path plus SHA-256 |
| Sampling | temperature, max tokens, seed if supported |
| Trials per item ("epochs") | k = 3 by default, 5 for headline claims |
| Tooling | which pages were rendered, image size, text budget |
| Ruleset version | e.g. `extraction-rules@3` |
| Dataset version | schema version, case ids, generator commit |
| Scoring | scorer commit, tolerances, matching rules |
| Timeouts and retries | what counts as a failure |

LLM-as-judge (NIST 2.1, emerging practice): if a judge model grades free text, compare it against human grading on a sample, report agreement, use more than one judge when stakes are high, and keep the rubric in the repo.

Debugging (NIST 2.4): read a sample of transcripts and outputs before trusting any aggregate. Look for harness bugs: truncated inputs, parsing failures, timeouts scored as zero or silently dropped.

## Stage 3: analyze and report (NIST 3.1-3.3)

- Quantify uncertainty from both item sampling (bootstrap over cases) and model sampling (variance across trials). Report both.
- Choose aggregate statistics that answer the claim; for comparisons, use paired metrics on the same items.
- Share enough to reproduce: the protocol table, dataset version, code commit and per-item results.
- Make qualified claims: scope, uncertainty, known limitations, and what was not tested.

## Lessons from SWE-bench Verified

1. **Answer keys can be wrong.** Audit the items models fail most; in OpenAI's audit, at least 59.4% of 138 hard problems had tests that rejected correct solutions. When your feature "misses" an item, check the key and the convention before counting it as a model error.
2. **Contamination inflates scores.** Public problems leak into training. Keep a private held-out set, date every case, and retire cases that leak into prompts or examples.
3. **Underspecified tasks reward guessing.** State conventions explicitly so a correct-but-different method isn't scored wrong, and make conventions explicit options rather than hidden choices in the key.
4. **Saturation hides progress.** When the top score stops moving, check whether the remaining failures are real before adding harder cases.

## What a lab-quality evaluation section contains

1. What was measured and why it matters.
2. The dataset: size, provenance, slices, held-out status.
3. The protocol table.
4. Results with error bars, against baselines and the previous version.
5. Slice results, flagging low-n slices.
6. Failure analysis with concrete examples.
7. Limitations and things not tested.
8. Reproduction instructions.
