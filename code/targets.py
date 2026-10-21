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

import fanlaw

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
    """Fan watts removed by the duty cut, using the calibrated fan law.

    The pure affinity law overstates this: it predicts a 95 % cut where a
    real server measures 87.5 %. fanlaw.fan_power is fitted to that
    measurement. One law, one module, one import - the previous version of
    this file carried a second, disagreeing law.
    """
    if fan_w < 0:
        raise ValueError("fan_w must be non-negative")
    if not (0.0 < duty_ctrl <= duty_base <= 1.0):
        raise ValueError("require 0 < duty_ctrl <= duty_base <= 1")
    return (fanlaw.fan_power(duty_base, fan_w)
            - fanlaw.fan_power(duty_ctrl, fan_w))


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


def selftest():
    """Algebra checks.

    The percentage BASE is stated explicitly in each label, because a fan
    saving can be quoted against full speed or against the uncontrolled draw
    and the two differ by ten points here. The pure cubic is checked too:
    the point of the calibrated law is that it does NOT reproduce it.
    """
    failures = 0

    def near(name: str, got: float, want: float, tol: float = 0.01) -> None:
        nonlocal failures
        ok = abs(got - want) <= tol
        if not ok:
            failures += 1
        print(f"  {'pass' if ok else 'FAIL'}  {name}"
              + ("" if ok else f"  got {got!r} want {want!r}"))

    def below(name: str, got: float, limit: float) -> None:
        nonlocal failures
        ok = got < limit
        if not ok:
            failures += 1
        print(f"  {'pass' if ok else 'FAIL'}  {name}"
              + ("" if ok else f"  got {got!r} not below {limit!r}"))

    saved = saved_watts(1000.0)
    full = fanlaw.fan_power(DUTY_BASE, 1000.0)

    near("95->35 saves 0.759836 of FULL-SPEED fan power" % (),
         saved / 1000.0, 0.759836, 1e-5)
    near("95->35 saves 0.862490 of the UNCONTROLLED draw" % (),
         saved / full, 0.862490, 1e-5)
    near("the pure cubic would have claimed 0.949993" % (),
         1.0 - (DUTY_CTRL / DUTY_BASE) ** 3, 0.949993, 1e-6)
    below("the calibrated law is BELOW the cubic claim",
          saved / full, 1.0 - (DUTY_CTRL / DUTY_BASE) ** 3)

    half = saved_watts(1000.0, DUTY_BASE, DUTY_BASE * 0.5)
    near("half duty leaves 0.319931 of full-speed fan power" % (),
         1.0 - half / 1000.0, 0.319931, 1e-5)
    below("half duty saves MORE than the cubic would claim", half, 1000.0 * 0.875)

    near("no duty change -> zero saving",
         saved_watts(1000.0, DUTY_BASE, DUTY_BASE), 0.0, 1e-12)

    near("1 kW node $/yr", dollars_per_node_year(saved), 838.68, 0.01)
    near("500 W node $/yr", dollars_per_node_year(saved_watts(500.0)), 419.34, 0.01)
    near("300 W node $/yr", dollars_per_node_year(saved_watts(300.0)), 251.60, 0.01)

    near("PUE is linear",
         dollars_per_node_year(saved, pue=2.0),
         2 * dollars_per_node_year(saved, pue=1.0), 1e-9)

    near("$1M at 1 kW needs 1193 nodes" % (),
         nodes_for(1_000_000.0, dollars_per_node_year(saved)), 1193, 0)
    near("1,500 nodes at 1 kW",
         nodes_for(1_500_000.0, dollars_per_node_year(saved)), 1789.00, 0.01)
    near("1,500 nodes at 500 W",
         nodes_for(1_500_000.0, dollars_per_node_year(saved_watts(500.0))), 3578.00, 0.01)
    near("1,500 nodes at 300 W",
         nodes_for(1_500_000.0, dollars_per_node_year(saved_watts(300.0))), 5962.00, 0.01)
    near("3,000 nodes at 1 kW",
         nodes_for(3_000_000.0, dollars_per_node_year(saved)), 3578.00, 0.01)

    for bad, name in ((lambda: saved_watts(-1.0), "negative fan power"),
                      (lambda: saved_watts(1000.0, 0.5, 0.9), "duty out of range")):
        try:
            bad()
        except ValueError:
            print(f"  pass  {name} raises")
        else:
            failures += 1
            print(f"  FAIL  {name} did not raise")

    print(f"\n{14 - failures}/14 checks passed")
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
