#!/usr/bin/env python3
"""
Three founder-led cases in one place.

    Lambda    qualified      leases the site, operates the nodes, pays the meter*
    Together  conditional    operates the clusters; partner owns part of the bill
    Modal     disqualified   no data centers, no nodes, no fans

    * Lambda's power payment is an assumption, not a public disclosure. The
      verdict is conditional on it, even though the model treats it as true.

The point of the portfolio is not that three companies save seven figures. It
is that the same arithmetic produces three different verdicts once ownership is
treated as a first-class term.

    uv run python code/portfolio.py --selftest
    uv run python code/portfolio.py
"""
from __future__ import annotations

import argparse

import lambda_case as lam
import together_case as tog
import modal_case as mod


def verdict(owns_datacenter: bool, owns_nodes: bool,
            controls_bmc: bool, pays_power: bool) -> str:
    return mod.qualification(owns_datacenter, owns_nodes, controls_bmc, pays_power)


def rows() -> list[dict]:
    atl = lam.site(12)
    lease = lam.legs(18_000)
    t8 = tog.attributable(8_000, 1.0)
    t8_half = tog.attributable(8_000, 0.5)
    m = mod.fan_bill(mod.active_gpus(1e9))
    return [
        {
            "name": "Lambda",
            "anchor": "ATL02 12 MW, 9,408 GPUs",
            "direct": atl["saving"],
            "capacity": atl["revenue"],
            "verdict": verdict(False, True, True, True),
            "note": f"18,000-GPU lease: ${lease['saving']:,.0f}/yr",
        },
        {
            "name": "Together",
            "anchor": "8,000 H100/H200, 1,000 nodes",
            "direct": t8["direct"],
            "capacity": t8["capacity"],
            "verdict": verdict(False, True, True, False),
            "note": f"at 50% owned: ${t8_half['direct']:,.0f}/yr",
        },
        {
            "name": "Modal",
            "anchor": "48,176 modeled, 6,022 nodes",
            "direct": 0.0,
            "capacity": 0.0,
            "verdict": verdict(False, False, False, False),
            "note": f"underlying fan bill ${m['total']:,.0f}/yr, kept by providers",
        },
    ]


def selftest() -> int:
    failures = 0

    def near(name: str, got: float, want: float, tol: float = 1e-6) -> None:
        nonlocal failures
        ok = abs(got - want) <= tol
        if not ok:
            failures += 1
        print(f"  {'pass' if ok else 'FAIL'}  {name}"
              + ("" if ok else f"  got {got!r} want {want!r}"))

    print("self-test: the three headlines")
    atl = lam.site(12)
    near("Lambda ATL02 direct", atl["saving"], 1_427_749, 1)
    near("Lambda ATL02 capacity", atl["revenue"], 12_247_321, 1)
    near("Together 8k at 100%", tog.attributable(8_000, 1.0)["direct"],
         1_214_072, 1)
    near("Together 8k at 50%", tog.attributable(8_000, 0.5)["direct"],
         607_036, 1)
    near("Modal underlying fan bill",
         mod.fan_bill(mod.active_gpus(1e9))["total"], 7_311_143, 1)

    print("self-test: the verdict matrix")
    near("Lambda", verdict(False, True, True, True) == "qualified", 1, 0)
    near("Together", verdict(False, True, True, False) == "conditional", 1, 0)
    near("Modal", verdict(False, False, False, False) == "disqualified", 1, 0)

    print("self-test: the Together boundary")
    near("ownership needed at 8k",
         1_000_000 / tog.legs(8_000)["saving"], 0.8237, 1e-4)
    near("ownership needed at 16k",
         1_000_000 / tog.legs(16_000)["saving"], 0.4118, 1e-4)

    print(f"\n{10 - failures}/10 checks passed")
    return 1 if failures else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    print("THREE FOUNDER-LED CASES  -  same arithmetic, three verdicts\n")
    print(f"{'target':<10} {'anchor':<30} {'direct $/yr':>13} "
          f"{'capacity $/yr':>15} {'verdict':>13}")
    for r in rows():
        print(f"{r['name']:<10} {r['anchor']:<30} {r['direct']:>13,.0f} "
              f"{r['capacity']:>15,.0f} {r['verdict'].upper():>13}")

    print("\nnotes")
    for r in rows():
        print(f"  {r['name']:<10} {r['note']}")

    print("\nthe four questions")
    print(f"{'target':<10} {'site':>8} {'nodes':>6} {'BMC':>5} "
          f"{'pay power':>10}")
    matrix = [
        ("Lambda", "lease", "yes", "yes*", "yes*"),
        ("Together", "partner", "part", "yes*", "part"),
        ("Modal", "none", "no", "no", "no"),
    ]
    for name, site, nodes, bmc, power in matrix:
        print(f"{name:<10} {site:>8} {nodes:>6} {bmc:>5} {power:>10}")
    print("  * assumed, not publicly disclosed; confirm before quoting")

    print("\nwhat each case proves")
    print("  Lambda   7 figures at an operating air-cooled site at R=36 "
          f"(${lam.site(12)['saving']:,.0f}/yr); "
          f"energy alone ${lam.site(12)['energy']:,.0f}/yr")
    print("  Together 7 figures only above 5,296 owned air-cooled GPUs at R=36; "
          "at the simulator's 1.3-1.8x the boundary is ~6,800-7,700")
    m = mod.fan_bill(mod.active_gpus(1e9))
    u = mod.utilization_gain(mod.active_gpus(1e9), 0.35, 0.60)
    print(f"  Modal    not a target: the ${m['total']:,.0f}/yr fan bill at R=36 "
          f"is 0.91% of ARR (0.63-0.71% at 1.3-1.8x) and belongs to 13 providers")
    print(f"           its utilization lever is ${u['revenue']:,.0f}/yr gross, "
          "not a fan saving")

    print("\nread next")
    print("  THREE-CASES.md      the comparison and the verification")
    print("  LAMBDA-CASE.md      qualified")
    print("  TOGETHER-CASE.md    conditional")
    print("  MODAL-CASE.md       disqualified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
