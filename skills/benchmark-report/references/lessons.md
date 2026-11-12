# Lessons from a production benchmark

Real holes that independent review found in a line-item extraction benchmark (quantities read from technical drawings) in November 2026. Each was fixed and became a regression test before any result was published. Check new benchmarks for the same holes before trusting them.

| Hole | Example | Test to add |
|---|---|---|
| Identity guessed from value | A row whose description listed four different item types was scored as whichever item its quantity happened to match; a whole category scored 100 | Ambiguous descriptions must not match; settle identity before comparing values |
| Order-dependent matching | The same rows in reverse order scored 97.6 vs 100 | Shuffle results N times; the report must be identical |
| Unvalidated values | 0.5 + 0.5 items, 100 x 0.01 items, and 100 + -99 items all scored 100 | Reject non-finite, non-positive and fractional counts at the scorer boundary |
| Float order effects | [1e16, -1e16, 1] summed differently when reversed | Stable (sorted) summation |
| Gate watched the weakest variant | One floor per case (the minimum over variants) let one variant drop from 100 to 70 while another stayed low | Floors per case x variant x metric |
| Gate silently disabled | `--min-score NaN` or a missing value turned the threshold off | Reject bad flags with a nonzero exit |
| Input not bound to the key | Removing items from the generated drawing left the derived key unchanged | Read the input back and re-derive the key; negative controls for each item family |
| Zero floors | A gate with all-zero thresholds passed empty results | State plainly that the gate protects nothing until floors are ratcheted |

From live runs:

- A run on a real 8-page document timed out at 92 s against a 100 s platform limit, on a question that took 26 s on retry. Record latency and timeouts as first-class results; a mean hides the tail.
- A test question can be wrong: it asked about an item that was not on the page, and the model's answer (pointing to the item that was) was correct. Audit failures against the source before counting them.
