#!/usr/bin/env python3
"""
Lambda case: energy, fatigue, and capacity at an air-cooled GPU cloud.

Public anchors (sources in LAMBDA-CASE.md):
  18,000 GPUs leased to Nvidia, Sep 2025 (The Information / DCD)
  Atlanta ATL02: up to 14 MW, air-cooled (EdgeConneX)
  Chicago: 23 MW single-tenant build, hybrid; two air-cooled sites (EdgeConneX)
  H100 SXM: $3.99/GPU-hr (Lambda pricing, 2026)
  DGX/HGX H100: 10.2 kW/node (NVIDIA spec)

Legs
----
1. energy   saved fan watts x hours x tariff x PUE
2. fatigue  afr x share x (1 - 1/R) x replacement, capped at afr x share x replacement
3. capacity saved watts / node power -> extra nodes -> revenue at Lambda's list price

The capacity leg is *revenue capacity*, not a cost saving: it needs capex for the
additional GPUs and demand to fill them. It is reported separately for that
reason.

Every output is a function of the printed inputs. `--selftest` checks the
algebra against hand-computed values.

    uv run python code/lambda_case.py --selftest
    uv run python code/lambda_case.py
    uv run python code/lambda_case.py --fan-w 500 --tariff 0.12 --pue 1.5
"""
from __future__ import annotations

import argparse
import math
import fanlaw
import thermal_model

# The throughput-safe operating point, DERIVED from the thermal solve rather
# than hard-coded. A change to the thermal model moves the fleet numbers
# with it, which is the whole point of computing it.
DUTY_CTRL = thermal_model.shipped_duty()


HOURS = 8760.0
GPUS_PER_NODE = 8
NODE_KW = 10.2
FAN_W = 1000.0
DUTY_BASE = 0.95
TARIFF = 0.08
PUE = 1.35
AFR = 0.03
SHARE = 0.35
REPLACEMENT = 60_000.0
LIFE_RATIO = 36.0
GPU_PRICE = 3.99
UTIL = 0.60


def saved_watts(fan_w: float, duty_base: float = DUTY_BASE,
                duty_ctrl: float = DUTY_CTRL) -> float:
    """Fan watts removed by the duty cut, using the calibrated fan law.

    The pure affinity law (duty_ctrl/duty_base)^3 overstates this: it predicts
    a 95% cut where a real server measures 87.5%. fanlaw.fan_power is fitted
    to that measurement, and the loss floor it carries is why the saving
    here is smaller than the naive number.
    """
    if fan_w < 0:
        raise ValueError("fan_w must be non-negative")
    if not (0.0 < duty_ctrl <= duty_base <= 1.0):
        raise ValueError("require 0 < duty_ctrl <= duty_base <= 1")
    return fanlaw.fan_power(duty_base, fan_w) - fanlaw.fan_power(duty_ctrl, fan_w)


def energy_per_node(fan_w: float = FAN_W, tariff: float = TARIFF,
                    pue: float = PUE, duty_base: float = DUTY_BASE,
                    duty_ctrl: float = DUTY_CTRL) -> float:
    if tariff < 0:
        raise ValueError("tariff must be non-negative")
    if pue <= 0:
        raise ValueError("PUE must be positive")
    return saved_watts(fan_w, duty_base, duty_ctrl) * HOURS / 1000.0 * tariff * pue


def fatigue_per_node(afr: float = AFR, share: float = SHARE,
                     replacement: float = REPLACEMENT,
                     ratio: float = LIFE_RATIO) -> float:
    if ratio <= 0:
        raise ValueError("life ratio must be positive")
    if afr < 0 or replacement < 0:
        raise ValueError("afr and replacement must be non-negative")
    if not (0.0 <= share <= 1.0):
        raise ValueError("share must be in [0, 1]")
    return afr * share * (1.0 - 1.0 / ratio) * replacement


def legs(gpus: int, fan_w: float = FAN_W, tariff: float = TARIFF,
         pue: float = PUE, util: float = UTIL, gpu_price: float = GPU_PRICE,
         afr: float = AFR, share: float = SHARE,
         replacement: float = REPLACEMENT, ratio: float = LIFE_RATIO,
         node_kw: float = NODE_KW) -> dict:
    if gpus <= 0 or gpus % GPUS_PER_NODE:
        raise ValueError(f"{gpus} is not a positive multiple of {GPUS_PER_NODE}")
    if node_kw <= 0:
        raise ValueError("node_kw must be positive")
    if not (0.0 <= util <= 1.0):
        raise ValueError("util must be in [0, 1]")
    if gpu_price < 0:
        raise ValueError("gpu_price must be non-negative")
    nodes = gpus // GPUS_PER_NODE
    e_node = energy_per_node(fan_w, tariff, pue)
    f_node = fatigue_per_node(afr, share, replacement, ratio)
    cap_w = nodes * saved_watts(fan_w)
    extra_nodes = int(cap_w / (node_kw * 1000.0))
    extra_gpus = extra_nodes * GPUS_PER_NODE
    revenue = extra_gpus * gpu_price * HOURS * util
    return {
        "gpus": gpus,
        "nodes": nodes,
        "energy_node": e_node,
        "energy": nodes * e_node,
        "fatigue_node": f_node,
        "fatigue": nodes * f_node,
        "saving": nodes * (e_node + f_node),
        "capacity_mw": cap_w / 1e6,
        "extra_nodes": extra_nodes,
        "extra_gpus": extra_gpus,
        "revenue": revenue,
    }


def site(mw: float, **kwargs) -> dict:
    if mw <= 0:
        raise ValueError("mw must be positive")
    node_kw = kwargs.get("node_kw", NODE_KW)
    if node_kw <= 0:
        raise ValueError("node_kw must be positive")
    nodes = int(mw * 1000.0 / node_kw)
    r = legs(nodes * GPUS_PER_NODE, **kwargs)
    r["mw"] = mw
    return r


def selftest() -> int:
    failures = 0

    def near(name: str, got: float, want: float, tol: float = 1e-6) -> None:
        nonlocal failures
        ok = abs(got - want) <= tol
        if not ok:
            failures += 1
        print(f"  {'pass' if ok else 'FAIL'}  {name}"
              + ("" if ok else f"  got {got!r} want {want!r}"))

    print("self-test: algebra")
    near("1 kW node at $0.09 / PUE 1.4",
         energy_per_node(1000, 0.09, 1.4), 702.08, 0.01)
    near("500 W node at $0.09 / PUE 1.4",
         energy_per_node(500, 0.09, 1.4), 351.04, 0.01)
    near("8-GPU fatigue at R=36", fatigue_per_node(), 612.50, 0.01)
    near("fatigue ceiling", fatigue_per_node(ratio=1e12), 630.00, 0.01)

    print("self-test: 18,000-GPU lease")
    l = legs(18_000, 1000, 0.09, 1.4)
    near("nodes", l["nodes"], 2250)
    near("energy", l["energy"], 1_579_670, 10)
    near("fatigue", l["fatigue"], 1_378_125, 1)
    near("capacity MW", l["capacity_mw"], 1.43117, 1e-4)
    near("extra GPUs (floor)", l["extra_gpus"], 1120)
    near("revenue at 60%", l["revenue"], 23_488_013, 10)

    print("self-test: sites")
    near("12 MW nodes", site(12)["nodes"], 1176)
    near("14 MW nodes", site(14)["nodes"], 1372)
    near("30 MW nodes", site(30)["nodes"], 2941)

    print(f"\n{13 - failures}/13 checks passed")
    return 1 if failures else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gpus", type=int, default=18_000)
    ap.add_argument("--fan-w", type=float, default=FAN_W)
    ap.add_argument("--tariff", type=float, default=TARIFF)
    ap.add_argument("--pue", type=float, default=PUE)
    ap.add_argument("--util", type=float, default=UTIL)
    ap.add_argument("--gpu-price", type=float, default=GPU_PRICE)
    ap.add_argument("--ratio", type=float, default=LIFE_RATIO,
                    help="swing damage ratio; 36 is the best case, 1.3-1.8 is the simulator range")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    kw = dict(fan_w=args.fan_w, tariff=args.tariff, pue=args.pue,
              util=args.util, gpu_price=args.gpu_price, ratio=args.ratio)

    print("LAMBDA  -  air-cooled GPU cloud, three legs")
    print(f"fan {args.fan_w:,.0f} W/node, duty {DUTY_BASE:.0%}->{DUTY_CTRL:.0%}, "
          f"${args.tariff}/kWh, PUE {args.pue}, H100 ${args.gpu_price}/GPU-hr, "
          f"{args.util:.0%} util")
    print(f"fatigue: R={args.ratio:g} swing scenario; cycle simulator 1.3-1.8x Coffin-Manson\n")

    print(f"{'GPUs':>7} {'nodes':>6} {'energy $/yr':>13} {'fatigue $/yr':>14} "
          f"{'saving $/yr':>13} {'MW freed':>9}")
    for gpus in (args.gpus, 12_000, 8_000):
        r = legs(gpus, **kw)
        print(f"{r['gpus']:>7,} {r['nodes']:>6,} {r['energy']:>13,.0f} "
              f"{r['fatigue']:>14,.0f} {r['saving']:>13,.0f} "
              f"{r['capacity_mw']:>9,.2f}")

    print("\ncapacity leg (revenue capacity, not a saving)")
    r = legs(args.gpus, **kw)
    print(f"  {r['capacity_mw']:,.2f} MW freed -> {r['extra_nodes']:,} extra nodes "
          f"= {r['extra_gpus']:,} GPUs")
    print(f"  ${r['revenue']:,.0f}/yr at {args.util:.0%} utilization "
          f"and ${args.gpu_price}/GPU-hr")
    print(f"  (gross revenue; needs capex for the GPUs and demand to fill them)")

    print("\nair-cooled site scenarios (10.2 kW/node)")
    for mw in (12, 14, 30):
        s = site(mw, **kw)
        print(f"  {mw:>2} MW -> {s['nodes']:>5,} nodes / {s['gpus']:>6,} GPUs  "
              f"energy ${s['energy']:>10,.0f}  fatigue ${s['fatigue']:>10,.0f}  "
              f"total ${s['saving']:>10,.0f}")

    print("\nfan-wattage sensitivity (18,000 GPUs)")
    for fan_w in (1000, 500, 300):
        r = legs(args.gpus, **dict(kw, fan_w=fan_w))
        print(f"  {fan_w:>4} W/node -> energy ${r['energy']:>11,.0f}  "
              f"total ${r['saving']:>11,.0f}  "
              f"capacity ${r['revenue']:>12,.0f}/yr")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
