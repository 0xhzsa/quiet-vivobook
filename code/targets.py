#!/usr/bin/env python3
"""
Target arithmetic for the fan-power leg.

Given a fleet's GPU count and a fan tray wattage, compute the annual fan-power
saving at a stated duty reduction. Every number is a function of the inputs
printed with it.

    saved_w   = fan_w * (1 - (duty_ctrl / duty_base)^3)
    $/node/yr = saved_w * 8760 / 1000 * tariff * pue

The affinity law is cubic because airflow ~ N, pressure ~ N^2, shaft power ~ N^3
for a fixed impeller. PUE multiplies the *saving*: a watt removed at the server
also removes its share of cooling overhead.

    uv run python code/targets.py --selftest
    uv run python code/targets.py
    uv run python code/targets.py --gpus 12000 --fan-w 500
"""
from __future__ import annotations

import argparse
import math

HOURS = 8760.0
DUTY_BASE = 0.95
DUTY_CTRL = 0.35
TARIFF = 0.09
PUE = 1.4
TARGET = 1_000_000.0
GPUS_PER_NODE = 8

# Public fleet counts. The fan wattage is an assumption for all of them; that is
# the input the ask exists to replace with a BMC reading.
FLEETS = [
    ("Voltage Park (2024 count)", 24_000),
    ("Voltage Park (2026 count)", 12_000),
    ("Lambda (NVIDIA lease)", 18_000),
    ("Together (assumed 8,000 air-cooled)", 8_000),
]


def saved_watts(fan_w: float, duty_base: float = DUTY_BASE,
                duty_ctrl: float = DUTY_CTRL) -> float:
    if not (0.0 < duty_ctrl <= duty_base <= 1.0):
        raise ValueError("require 0 < duty_ctrl <= duty_base <= 1")
    return fan_w * (1.0 - (duty_ctrl / duty_base) ** 3)


def dollars_per_node_year(saved: float, tariff: float = TARIFF,
                          pue: float = PUE, hours: float = HOURS) -> float:
    return saved * hours / 1000.0 * tariff * pue


def nodes_for(target: float, per_node: float) -> int:
    if per_node <= 0:
        raise ValueError("per-node saving must be positive")
    return math.ceil(target / per_node)


def fleet(gpus: int, gpus_per_node: int, fan_w: float, tariff: float = TARIFF,
          pue: float = PUE, duty_base: float = DUTY_BASE,
          duty_ctrl: float = DUTY_CTRL) -> dict:
    if gpus % gpus_per_node:
        raise ValueError(f"{gpus} GPUs is not a whole number of {gpus_per_node}-GPU nodes")
    nodes = gpus // gpus_per_node
    per_node = dollars_per_node_year(
        saved_watts(fan_w, duty_base, duty_ctrl), tariff, pue)
    return {
        "gpus": gpus,
        "nodes": nodes,
        "fan_w": fan_w,
        "per_node": per_node,
        "total": nodes * per_node,
        "clears": nodes * per_node >= TARGET,
    }


def selftest() -> int:
    failures = 0

    def near(name: str, got: float, want: float, tol: float = 1e-6) -> None:
        nonlocal failures
        ok = abs(got - want) <= tol
        if not ok:
            failures += 1
        print(f"  {'pass' if ok else 'FAIL'}  {name}"
              + ("" if ok else f"  got {got!r} want {want!r}"))

    print("self-test: affinity and dollars")
    near("95->35 duty saves 94.9993% of fan power",
         saved_watts(1000.0) / 1000.0, 1.0 - (7.0 / 19.0) ** 3)
    near("half duty -> 1/8 power remaining",
         1000.0 - saved_watts(1000.0, 1.0, 0.5), 125.0)
    near("no duty change -> zero saving", saved_watts(1000.0, 0.9, 0.9), 0.0)
    near("linear in fan watts", saved_watts(2000.0), 2 * saved_watts(1000.0))
    near("1 kW node $/yr", dollars_per_node_year(saved_watts(1000.0)), 1048.56, 0.01)
    near("500 W node $/yr", dollars_per_node_year(saved_watts(500.0)), 524.28, 0.01)
    near("300 W node $/yr", dollars_per_node_year(saved_watts(300.0)), 314.57, 0.01)
    near("PUE is linear", dollars_per_node_year(saved_watts(1000.0), pue=1.1),
         1048.56 * 1.1 / 1.4, 0.01)

    print("self-test: fleet arithmetic")
    near("$1M at 1 kW needs 954 nodes",
         nodes_for(TARGET, dollars_per_node_year(saved_watts(1000.0))), 954)
    near("1,500 nodes at 1 kW", fleet(12_000, 8, 1000.0)["total"], 1_572_840.0, 10.0)
    near("1,500 nodes at 500 W", fleet(12_000, 8, 500.0)["total"], 786_423.0, 20.0)
    near("1,500 nodes at 300 W", fleet(12_000, 8, 300.0)["total"], 471_854.0, 20.0)
    near("3,000 nodes at 1 kW", fleet(24_000, 8, 1000.0)["total"], 3_145_680.0, 20.0)

    print(f"\n{12 - failures}/12 checks passed")
    return 1 if failures else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gpus", type=int)
    ap.add_argument("--gpus-per-node", type=int, default=GPUS_PER_NODE)
    ap.add_argument("--fan-w", type=float, default=1000.0)
    ap.add_argument("--tariff", type=float, default=TARIFF)
    ap.add_argument("--pue", type=float, default=PUE)
    ap.add_argument("--duty-base", type=float, default=DUTY_BASE)
    ap.add_argument("--duty-ctrl", type=float, default=DUTY_CTRL)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    def row(gpus: int, fan_w: float) -> dict:
        return fleet(gpus, args.gpus_per_node, fan_w, args.tariff, args.pue,
                     args.duty_base, args.duty_ctrl)

    if args.gpus:
        r = row(args.gpus, args.fan_w)
        print(f"{r['gpus']:,} GPUs = {r['nodes']:,} x {args.gpus_per_node}-GPU nodes")
        print(f"fan {r['fan_w']:,.0f} W, duty {args.duty_base:.0%} -> {args.duty_ctrl:.0%}, "
              f"${args.tariff}/kWh, PUE {args.pue}")
        print(f"  ${r['per_node']:,.2f}/node/yr")
        print(f"  ${r['total']:,.0f}/yr  "
              f"({'clears' if r['clears'] else 'does not clear'} $1M)")
        return 0

    print(f"duty {args.duty_base:.0%} -> {args.duty_ctrl:.0%}, "
          f"${args.tariff}/kWh, PUE {args.pue}, target $1M/yr\n")
    print(f"{'fleet':32} {'GPUs':>7} {'nodes':>6} {'fan W':>6} "
          f"{'$/node/yr':>10} {'$/yr':>12}  $1M")
    for name, gpus in FLEETS:
        r = row(gpus, args.fan_w)
        print(f"{name:32} {r['gpus']:>7,} {r['nodes']:>6,} {r['fan_w']:>6,.0f} "
              f"{r['per_node']:>10,.2f} {r['total']:>12,.0f}  "
              f"{'yes' if r['clears'] else 'no'}")

    print("\nfan-wattage sensitivity (Voltage Park 2026 count, 12,000 GPUs):")
    for fan_w in (1000.0, 500.0, 300.0):
        r = row(12_000, fan_w)
        print(f"  {fan_w:>5,.0f} W/node -> ${r['per_node']:>9,.2f}/node/yr  "
              f"${r['total']:>11,.0f}/yr  "
              f"{'clears' if r['clears'] else 'does not clear'} $1M")

    per_node = dollars_per_node_year(
        saved_watts(args.fan_w, args.duty_base, args.duty_ctrl),
        args.tariff, args.pue)
    print(f"\n$1M/yr at {args.fan_w:,.0f} W/node needs "
          f"{nodes_for(TARGET, per_node):,} nodes "
          f"({nodes_for(TARGET, per_node) * args.gpus_per_node:,} GPUs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
