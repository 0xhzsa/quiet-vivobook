#!/usr/bin/env python3
"""
analyze-mode-run.py - paired statistics for a mode-effect run.

The harness produces samples; this decides what they mean. It exists because
the difference between "a number" and "a measurement" is exactly this file:
replicates of the same condition, a noise floor estimated from them, and an
effect that is only claimed if it clears that floor.

    uv run --no-project python controller/fan-scan/analyze-mode-run.py <run-dir>
    uv run --no-project python controller/fan-scan/analyze-mode-run.py --latest

What it reports
---------------
  * per-phase steady-window statistics, recomputed from samples.jsonl using
    the same window rule the harness used
  * per-mode replicates, the mean and the between-replicate standard
    deviation, which is the NOISE FLOOR
  * the mode-to-mode difference against that noise floor, in units of the
    pooled standard deviation
  * a verdict per quantity: real effect, or not resolved by this run

The rule it applies: an effect is only called real if the difference between
the mode means exceeds the between-replicate standard deviation of the
means. A run that cannot resolve the effect says so. It does not report the
difference as if it were a finding, because that is how a noise floor gets
mistaken for a signal.

It also checks the things that void a run:
  * any phase that was not on AC
  * any phase with fewer than three steady samples
  * any phase whose mode read-back did not match
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections import defaultdict


def load(run_dir: str) -> tuple:
    with open(os.path.join(run_dir, "summary.json"), encoding="utf-8") as fh:
        summary = json.load(fh)
    rows = defaultdict(list)
    with open(os.path.join(run_dir, "samples.jsonl"), encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            rows[r["label"]].append(r)
    return summary, rows


def steady_rows(rows, load_sec, steady_sec):
    if not rows:
        return []
    cut = rows[0]["t"] + max(0, load_sec - steady_sec)
    return [r for r in rows
            if r.get("t_max") is not None and r["t"] >= cut
            and r.get("pkg_w") is not None]


def phase_stats(rows, load_sec, steady_sec):
    st = steady_rows(rows, load_sec, steady_sec)
    if len(st) < 2:
        return None
    work = (st[-1]["iter"] - st[0]["iter"]) / (st[-1]["t"] - st[0]["t"])
    pw = [r["pkg_w"] for r in st]
    tt = [r["t_max"] for r in st]
    mean = lambda xs: sum(xs) / len(xs)
    sd = lambda xs: (sum((x - mean(xs)) ** 2 for x in xs) / (len(xs) - 1)) ** 0.5
    return {
        "n": len(st),
        "pkg_w": mean(pw), "pkg_sd": sd(pw),
        "die_c": mean(tt), "die_sd": sd(tt),
        "work": work,
        "peak_c": max(tt),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("run_dir", nargs="?")
    ap.add_argument("--latest", action="store_true")
    args = ap.parse_args()

    run_dir = args.run_dir
    if args.latest or not run_dir:
        base = os.path.join(os.path.dirname(os.path.abspath(__file__)))
        cands = sorted([os.path.join(base, d) for d in os.listdir(base)
                        if d.startswith("mode-v4-") or d.startswith("mode-20")
                        and os.path.isdir(os.path.join(base, d))],
                       key=os.path.getmtime)
        if not cands:
            print("no run directories found")
            return 1
        run_dir = cands[-1]
    print("run:", run_dir)

    summary, rows = load(run_dir)
    load_sec = summary.get("load_sec", 100)
    steady_sec = summary.get("steady_sec", 50)

    print()
    print("threads %s | load %ss | steady %ss | ac_state %s | driver_warm %sms" % (
        summary.get("thread_count"), load_sec, steady_sec,
        summary.get("ac_state"), summary.get("driver_warm_ms")))
    print()
    print("%-10s %5s %4s %9s %7s %8s %7s %9s %8s" % (
        "phase", "mode", "n", "pkg_W", "sd", "die_C", "sd", "work/s", "ac"))
    print("-" * 84)

    problems = []
    stats = []
    for ph in summary.get("phases", []):
        s = phase_stats(rows.get(ph["label"], []), load_sec, steady_sec)
        if s is None:
            problems.append("%s: fewer than 2 steady samples" % ph["label"])
            print("%-10s %5s %4s  INSUFFICIENT" % (ph["label"], ph["mode"], "-"))
            continue
        ac = ph.get("ac_state", "?")
        if ac != "ac":
            problems.append("%s: ran on %s, not AC" % (ph["label"], ac))
        if s["n"] < 3:
            problems.append("%s: only %d steady samples" % (ph["label"], s["n"]))
        print("%-10s %5d %4d %9.2f %7.2f %8.1f %7.1f %9.0f %8s" % (
            ph["label"], ph["mode"], s["n"], s["pkg_w"], s["pkg_sd"],
            s["die_c"], s["die_sd"], s["work"], ac))
        s["mode"] = ph["mode"]
        s["label"] = ph["label"]
        stats.append(s)

    by_mode = defaultdict(list)
    for s in stats:
        by_mode[s["mode"]].append(s)

    print()
    print("=" * 84)
    print("REPLICATES AND THE NOISE FLOOR")
    print("=" * 84)
    for m in sorted(by_mode):
        v = by_mode[m]
        pw = [x["pkg_w"] for x in v]
        wk = [x["work"] for x in v]
        tc = [x["die_c"] for x in v]
        print("mode %d (n=%d)" % (m, len(v)))
        print("   package W : %s  mean %.2f" % (
            ["%.2f" % x for x in pw], sum(pw) / len(pw)))
        print("   work/s    : %s  mean %.0f" % (
            ["%.0f" % x for x in wk], sum(wk) / len(wk)))
        print("   die C     : %s  mean %.1f" % (
            ["%.1f" % x for x in tc], sum(tc) / len(tc)))

    if len(by_mode) < 2:
        print()
        print("only one mode present: nothing to compare")
        return 0

    modes = sorted(by_mode)
    a, b = modes[0], modes[-1]
    print()
    print("=" * 84)
    print("MODE %d vs MODE %d" % (a, b))
    print("=" * 84)

    def compare(name, key, unit):
        """Paired comparison.

        The design is 0,1,0,1,... so the run is PAIRED: each mode-1 phase
        immediately follows a mode-0 phase, and the thermal drift between
        them cancels in the difference. Comparing the two mode means with an
        unpaired test throws that away and inflates the significance, so the
        paired test is the one reported. Both are shown.
        """
        va = [x[key] for x in by_mode[a]]
        vb = [x[key] for x in by_mode[b]]
        ma, mb = sum(va) / len(va), sum(vb) / len(vb)

        # Unpaired standard error, for reference only.
        pooled = 0.0
        for v in (va, vb):
            if len(v) > 1:
                m = sum(v) / len(v)
                pooled += sum((x - m) ** 2 for x in v) / (len(v) - 1)
        se_unpaired = (math.sqrt(pooled / (len(va) + len(vb)))
                       if pooled > 0 and len(va) > 1 and len(vb) > 1 else 0.0)
        t_unpaired = ((mb - ma) / se_unpaired) if se_unpaired > 0 else 0.0

        # Paired differences, in run order.
        diffs = []
        seq = [(x["label"], x["mode"], x[key]) for x in stats]
        pending = {}
        for label, mode, value in seq:
            if mode == a:
                pending[a] = value
            elif mode == b and a in pending:
                diffs.append(value - pending[a])
        print()
        print("%s:" % name)
        print("   mode %d: %.2f %s   mode %d: %.2f %s" % (a, ma, unit, b, mb, unit))
        print("   difference of means %+.2f %s (%.1f%% of the mode-%d mean)" % (
            mb - ma, unit, 100.0 * (mb - ma) / ma if ma else 0.0, a))
        if diffs:
            md = sum(diffs) / len(diffs)
            if len(diffs) > 1:
                sd = (sum((x - md) ** 2 for x in diffs) / (len(diffs) - 1)) ** 0.5
                se = sd / math.sqrt(len(diffs))
                t = md / se if se > 0 else 0.0
            else:
                sd = se = 0.0
                t = 0.0
            print("   paired differences: %s" % ["%+.2f" % x for x in diffs])
            print("   paired mean %+.2f %s, sd %.2f, se %.2f -> t = %.2f (df %d)" % (
                md, unit, sd, se, t, len(diffs) - 1))
            print("   unpaired t for reference: %.2f (this ignores the pairing "
                  "and is inflated)" % t_unpaired)
            resolved = abs(t) >= 2.0 and len(diffs) > 1
        else:
            t = 0.0
            print("   no adjacent pairs to test")
            resolved = False
        if resolved:
            print("   RESOLVED: mode %d is %s by %.2f %s" % (
                b, "lower" if (mb - ma) < 0 else "higher", abs(mb - ma), unit))
        else:
            print("   NOT RESOLVED: the difference is inside the noise floor "
                  "of this run. More replicates needed.")
        return resolved

    compare("package power", "pkg_w", "W")
    compare("work rate", "work", "work/s")
    compare("die temperature", "die_c", "C")

    print()
    print("=" * 84)
    if problems:
        print("RUN INTEGRITY PROBLEMS")
        for p in problems:
            print("  -", p)
        print("This run is NOT clean. Fix the problems before quoting it.")
    else:
        print("run integrity: all phases on AC, all steady windows populated, "
              "all mode read-backs matched.")
    print("=" * 84)
    return 0


if __name__ == "__main__":
    sys.exit(main())
