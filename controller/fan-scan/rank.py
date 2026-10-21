#!/usr/bin/env python3
"""
rank.py - decide whether any readable surface is the fan.

A probe is only a candidate if it satisfies all three:

    rise   : load mean differs from idle mean by more than the idle noise
    return : it comes back toward the idle value during cooldown
    repeat : it does the same thing on the next cycle (when there are two)

Correlation alone is not enough. A monotone counter rises with every phase and
correlates beautifully with time; the return test kills it. A register that
tracks package power but not temperature is a power rail, not a fan.

Usage:
    python rank.py --dir fan-scan/run-20261020-153000
    python rank.py --dir ... --top 40
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys

META = {"t", "phase", "cycle", "sample_ms", "msr_ms", "ec_ms", "wmi_ms"}
REF = {"t_pkg", "t_max", "t_mean", "pkg_w", "cpu_load"}


def load_jsonl(path):
    rows = []
    with open(path, "r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip().lstrip("\ufeff")
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return rows


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def stdev(xs):
    xs = [x for x in xs if x is not None]
    if len(xs) < 2:
        return 0.0
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def pearson(pairs):
    pairs = [(a, b) for a, b in pairs if a is not None and b is not None]
    n = len(pairs)
    if n < 4:
        return 0.0
    mx = sum(a for a, _ in pairs) / n
    my = sum(b for _, b in pairs) / n
    sx = math.sqrt(sum((a - mx) ** 2 for a, _ in pairs))
    sy = math.sqrt(sum((b - my) ** 2 for _, b in pairs))
    if sx == 0 or sy == 0:
        return 0.0
    return sum((a - mx) * (b - my) for a, b in pairs) / (sx * sy)


def lag_corr(x, y, max_lag):
    best_c, best_lag = 0.0, 0
    n = min(len(x), len(y))
    for lag in range(max_lag + 1):
        pairs = [(x[i], y[i - lag]) for i in range(lag, n)]
        c = pearson(pairs)
        if abs(c) > abs(best_c):
            best_c, best_lag = c, lag
    return best_c, best_lag


def phase_vals(rows, phase, cycle=None):
    return [r.get("probe") for r in rows
            if r.get("phase") == phase and (cycle is None or r.get("cycle") == cycle)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--top", type=int, default=25)
    ap.add_argument("--max-lag", type=int, default=6)
    args = ap.parse_args()

    d = args.dir
    jsonl = os.path.join(d, "samples.jsonl")
    if not os.path.exists(jsonl):
        print("no samples.jsonl in %s" % d)
        raise SystemExit(1)

    rows = load_jsonl(jsonl)
    if not rows:
        print("samples.jsonl is empty")
        raise SystemExit(1)

    with open(os.path.join(d, "preflight.json"), "r", encoding="utf-8-sig") as f:
        pf = json.load(f)
    with open(os.path.join(d, "meta.json"), "r", encoding="utf-8-sig") as f:
        meta = json.load(f)

    phases = {}
    for r in rows:
        phases.setdefault((r.get("cycle"), r.get("phase")), 0)
        phases[(r.get("cycle"), r.get("phase"))] += 1

    print("=" * 78)
    print("DIFFERENTIAL SURFACE SCAN  %s" % os.path.basename(d))
    print("=" * 78)
    print("model %s   bios %s" % (meta.get("model"), meta.get("bios")))
    print("elevated=%s  cores=%s  tjMax=%s" % (pf.get("elevated"), pf.get("cores"), pf.get("tjMax")))
    print("msr=%s  ec=%s  asus_wmi=%s" % (pf.get("msr"), pf.get("ec"), pf.get("asus_kind")))
    ecnz = pf.get("ec_nonzero")
    ecnz_n = len(ecnz) if isinstance(ecnz, list) else (ecnz or 0)
    sup = pf.get("wmi_supported")
    sup_n = len(sup) if isinstance(sup, list) else (sup or 0)
    print("battery=%s%%  ac=%s" % (pf.get("battery"), pf.get("ac")))
    print("wmi sweep %sms -> %s supported of %s ids   ec sweep %sms -> %s non-zero" % (
        pf.get("wmi_sweep_ms"), sup_n, pf.get("wmi_ids"),
        pf.get("ec_sweep_ms"), ecnz_n))
    if isinstance(sup, list) and sup:
        print("  live ids: %s" % " ".join(str(x) for x in sup))
    print("ec non-zero: %s" % (ecnz if ecnz_n <= 12 else "%d registers" % ecnz_n))
    if pf.get("asus_errors"):
        for e in pf["asus_errors"][:4]:
            print("  asus error: %s" % e)
    print("samples %d   phases %s" % (len(rows), sorted(phases.items(), key=lambda kv: str(kv[0]))))
    print("load observed: %s" % meta.get("load_observed"))
    print()

    if ecnz_n <= 1:
        print("!! the EC is effectively unreachable: %d non-zero register(s)." % ecnz_n)
        print("   That is not an idle EC; the reader is not reaching it.")
        print()
    if sup_n == 0:
        print("!! no DSTS device id is implemented on this machine.")
        print()

    # reference series: per-core max is the validated sensor; the package MSR
    # reads a constant 100 on this part and is not usable.
    t_ref = [r.get("t_max") if r.get("t_max") is not None else r.get("t_pkg") for r in rows]
    pkg_w = [r.get("pkg_w") for r in rows]
    cycles = sorted({r.get("cycle") for r in rows if r.get("cycle")})

    probes = []
    for k in rows[0].keys():
        if k in META or k in REF:
            continue
        vals = [r.get(k) for r in rows]
        non_null = [v for v in vals if v is not None]
        if len(non_null) < max(4, len(rows) // 3):
            continue
        probes.append(k)

    results = []
    for k in probes:
        vals = [r.get(k) for r in rows]
        idle = [v for v, r in zip(vals, rows) if r.get("phase") == "idle" and v is not None]
        load = [v for v, r in zip(vals, rows) if r.get("phase") == "load" and v is not None]
        cool = [v for v, r in zip(vals, rows) if r.get("phase") == "cooldown" and v is not None]
        if not idle or not load:
            continue
        mi, ml = mean(idle), mean(load)
        mc = mean(cool) if cool else None
        noise = stdev(idle)
        if noise == 0:
            noise = stdev([v for v in vals if v is not None]) * 0.05
        noise = max(noise, 1e-9)
        rise = ml - mi
        step_sigma = abs(rise) / noise

        # return test: last cooldown sample should move back toward idle
        cool_last = next((v for v, r in reversed(list(zip(vals, rows)))
                          if r.get("phase") == "cooldown" and v is not None), None)
        returned = False
        if cool_last is not None:
            returned = abs(cool_last - mi) < abs(ml - mi) * 0.75

        # per-cycle direction, for reproducibility
        dirs = []
        for c in cycles:
            i_c = [v for v, r in zip(vals, rows) if r.get("cycle") == c and r.get("phase") == "idle" and v is not None]
            l_c = [v for v, r in zip(vals, rows) if r.get("cycle") == c and r.get("phase") == "load" and v is not None]
            if i_c and l_c:
                dirs.append(mean(l_c) - mean(i_c))
        repro = None
        if len(dirs) >= 2:
            same = all((x > 0) == (dirs[0] > 0) for x in dirs)
            mags = [abs(x) for x in dirs]
            stable = min(mags) >= 0.5 * max(mags) if max(mags) > 0 else False
            repro = bool(same and stable)

        ct, lag_t = lag_corr(vals, t_ref, args.max_lag)
        cw, lag_w = lag_corr(vals, pkg_w, args.max_lag)

        # A register that is an exact rescaling of package power is a power
        # reading, not a fan. Fans lag temperature; rails do not.
        power_image = False
        pairs = [(v, w) for v, w in zip(vals, pkg_w) if v is not None and w not in (None, 0)]
        if len(pairs) >= 5 and abs(cw) > 0.999:
            ratios = [v / w for v, w in pairs]
            m = mean(ratios)
            if m not in (None, 0):
                cv = stdev(ratios) / abs(m)
                power_image = cv < 0.01

        score = (1.0 + min(step_sigma, 20.0) / 20.0) * (1.0 + abs(ct))
        if repro is True:
            score *= 1.25
        elif repro is False:
            score *= 0.5
        if power_image:
            score *= 0.2

        results.append({
            "probe": k, "idle": mi, "load": ml, "cool": mc,
            "rise": rise, "step_sigma": step_sigma, "returned": returned,
            "corr_t": ct, "lag_t": lag_t, "corr_w": cw, "lag_w": lag_w,
            "repro": repro, "score": score, "power_image": power_image,
            "range": (max(v for v in vals if v is not None) -
                      min(v for v in vals if v is not None)),
        })

    results.sort(key=lambda r: -r["score"])

    def verdict(r):
        if r["range"] == 0:
            return "-"
        if r["power_image"]:
            return "rail"
        if r["step_sigma"] >= 3 and r["returned"] and r["repro"] is not False:
            return "STRONG"
        if r["step_sigma"] >= 2 and r["returned"]:
            return "weak"
        return "-"

    hdr = "%-14s %8s %8s %8s %9s %6s %7s %5s %6s %s" % (
        "probe", "idle", "load", "cool", "step/sig", "corrT", "lag", "ret", "repro", "verdict")
    print(hdr)
    print("-" * len(hdr))
    shown = 0
    for r in results:
        if r["range"] == 0:
            continue
        if shown >= args.top:
            break
        print("%-14s %8.2f %8.2f %8.2f %9.1f %6.2f %7d %5s %6s %s" % (
            r["probe"], r["idle"], r["load"],
            (r["cool"] if r["cool"] is not None else float("nan")),
            r["step_sigma"], r["corr_t"], r["lag_t"],
            "yes" if r["returned"] else "no",
            ("?" if r["repro"] is None else ("yes" if r["repro"] else "no")), verdict(r)))
        shown += 1

    strong = [r for r in results if verdict(r) == "STRONG"]
    changing = [r for r in results if r["range"] > 0]
    print()
    print("probes with any change: %d / %d" % (len(changing), len(results)))
    print("strong candidates: %d" % len(strong))
    if strong:
        for r in strong[:10]:
            print("  -> %s  idle=%.2f load=%.2f  corrT=%.2f lag=%d  step=%.1f sigma"
                  % (r["probe"], r["idle"], r["load"], r["corr_t"], r["lag_t"], r["step_sigma"]))
    else:
        print("  none. No readable surface satisfied rise + return + repeat.")
        print("  That is a real result: it means the fan is not observable through")
        print("  the surfaces probed, not that the fan does not exist.")

    out = os.path.join(d, "ranked.csv")
    keys = ["probe", "idle", "load", "cool", "rise", "step_sigma", "returned",
            "corr_t", "lag_t", "corr_w", "lag_w", "repro", "score", "range", "verdict"]
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in results:
            r["verdict"] = verdict(r)
            w.writerow({k: r[k] for k in keys})
    print("\nwrote %s" % out)


if __name__ == "__main__":
    main()
