#!/usr/bin/env python3
"""Case-level bootstrap confidence intervals, standard library only.

Usage:
  bootstrap_ci.py scores.json                 # one version
  bootstrap_ci.py new.json --compare old.json # paired difference on shared cases
  add --lower-is-better for latency, cost or error rates

Input JSON: {"case-id": score, ...} or {"case-id": [trial scores...], ...}.
Trials are averaged per case first, so resampling is over cases (the unit that
generalizes), not over rows or trials.
"""
import argparse
import json
import math
import random
import statistics


def per_case(path):
    raw = json.load(open(path))
    out = {}
    for case, value in raw.items():
        values = value if isinstance(value, list) else [value]
        if not values or not all(
            isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in values
        ):
            raise SystemExit(f"{path}: case {case!r} needs a finite number or a list of finite numbers")
        out[case] = statistics.fmean(values)
    if not out:
        raise SystemExit(f"{path}: no cases")
    return out


def bootstrap(values, iterations, rng):
    n = len(values)
    means = sorted(statistics.fmean(rng.choices(values, k=n)) for _ in range(iterations))
    lo = means[int(0.025 * iterations)]
    hi = means[min(iterations - 1, int(0.975 * iterations))]
    return statistics.fmean(values), lo, hi


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("scores")
    parser.add_argument("--compare", help="older version's scores, for a paired difference")
    parser.add_argument("--iterations", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--lower-is-better", action="store_true",
                        help="for latency, cost, error rates: a negative difference is an improvement")
    args = parser.parse_args()
    if args.iterations < 100:
        parser.error("--iterations must be at least 100")
    rng = random.Random(args.seed)

    new = per_case(args.scores)
    mean, lo, hi = bootstrap(list(new.values()), args.iterations, rng)
    print(f"{args.scores}: mean {mean:.3f}  95% CI [{lo:.3f}, {hi:.3f}]  n={len(new)} cases")
    if len(new) < 20:
        print("  note: fewer than 20 cases; treat the interval as rough")

    if args.compare:
        old = per_case(args.compare)
        shared = sorted(set(new) & set(old))
        if not shared:
            raise SystemExit("no shared cases to compare")
        missing = sorted(set(new) ^ set(old))
        diffs = [new[c] - old[c] for c in shared]
        mean, lo, hi = bootstrap(diffs, args.iterations, rng)
        up, down = ("worse", "better") if args.lower_is_better else ("better", "worse")
        verdict = up if lo > 0 else down if hi < 0 else "no clear difference"
        print(f"paired difference (new - old): {mean:+.3f}  95% CI [{lo:+.3f}, {hi:+.3f}]  n={len(shared)}  -> {verdict}")
        if missing:
            print(f"  not compared (in only one file): {', '.join(missing)}")


if __name__ == "__main__":
    main()
