#!/usr/bin/env python3
"""
Together AI case: the fan bill behind "thousands" of H100/H200 GPUs.

Public anchors (sources in TOGETHER-CASE.md):
  36,000 GB200 NVL72 GPUs co-built with Hypertec, liquid-cooled (Nov 2024)
  "thousands of existing H100 and H200 GPUs across North America" (Nov 2024)
  "secured data center capacity for over 100,000 GPUs throughout 2025"
  H100 $3.99/GPU-hr, H200 $5.99/GPU-hr on-demand clusters (2026)
  ClusterMAX Gold (Mar 2025); 500 MW of commitments (Series C, Jul 2026)

The 36,000-GPU headline is liquid and contributes zero fan watts. The case is
therefore built on the air-cooled H100/H200 fleet, whose size is public only as
"thousands". The base scenario is 8,000 GPUs, with 2,000 / 4,000 / 16,000 as
the range.

Legs
----
1. energy   saved fan watts x hours x tariff x PUE
2. fatigue  afr x share x (1 - 1/R) x replacement, capped at afr x share x replacement
3. capacity saved watts / node power -> extra nodes -> revenue at list price

The fourth term is ownership. Together operates clusters but also co-builds
with partners. A dollar saved on a node whose power bill is paid by Hypertec is
Hypertec's dollar, not Together's. `attributable()` splits every leg by the
share of the fleet whose fan power Together actually pays for.

    uv run python code/together_case.py --selftest
    uv run python code/together_case.py
    uv run python code/together_case.py --gpus 16000 --owned 0.75
"""
from __future__ import annotations

import argparse
import math

import fanlaw

HOURS = 8760.0
GPUS_PER_NODE = 8
NODE_KW = 10.2
FAN_W = 1000.0
DUTY_BASE = 0.95
DUTY_CTRL = 0.529
TARIFF = 0.08
PUE = 1.35
AFR = 0.03
SHARE = 0.35
REPLACEMENT = 60_000.0
LIFE_RATIO = 36.0
GPU_PRICE = 3.99
UTIL = 0.60
OWNED = 1.0


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
        "fatigue_node": f_node,
        "energy": nodes * e_node,
        "fatigue": nodes * f_node,
        "saving": nodes * (e_node + f_node),
        "capacity_mw": cap_w / 1e6,
        "extra_nodes": extra_nodes,
        "extra_gpus": extra_gpus,
        "revenue": revenue,
    }


def attributable(gpus: int, owned: float = OWNED, **kwargs) -> dict:
    """Split the three legs by the share of fan power Together pays for.

    owned = 1.0  Together owns the node and pays the meter.
    owned = 0.5  half the fleet is partner-hosted and the partner captures it.
    owned = 0.0  the whole claim belongs to the landlord.
    """
    if not (0.0 <= owned <= 1.0):
        raise ValueError("owned share must be in [0, 1]")
    r = legs(gpus, **kwargs)
    r["owned"] = owned
    r["direct"] = r["saving"] * owned
    r["capacity"] = r["revenue"] * owned
    r["partner_direct"] = r["saving"] * (1.0 - owned)
    r["partner_capacity"] = r["revenue"] * (1.0 - owned)
    r["seven_figures"] = r["direct"] >= 1_000_000.0
    return r


def breakeven_gpus(target: float = 1_000_000.0, energy_only: bool = False,
                   **kwargs) -> int:
    if target <= 0:
        raise ValueError("target must be positive")
    per_node = energy_per_node(
        kwargs.get("fan_w", FAN_W),
        kwargs.get("tariff", TARIFF),
        kwargs.get("pue", PUE),
    )
    if not energy_only:
        per_node += fatigue_per_node(
            kwargs.get("afr", AFR),
            kwargs.get("share", SHARE),
            kwargs.get("replacement", REPLACEMENT),
            kwargs.get("ratio", LIFE_RATIO),
        )
    nodes = math.ceil(target / per_node)
    return nodes * GPUS_PER_NODE


def selftest() -> int:
    failures = 0

    def near(name: str, got: float, want: float, tol: float = 1e-6) -> None:
        nonlocal failures
        ok = abs(got - want) <= tol
        if not ok:
            failures += 1
        print(f"  {'pass' if ok else 'FAIL'}  {name}"
              + ("" if ok else f"  got {got!r} want {want!r}"))

    print("self-test: per-node algebra")
    near("1 kW node at $0.08 / PUE 1.35",
         energy_per_node(1000, 0.08, 1.35), 601.57, 0.01)
    near("500 W node at $0.08 / PUE 1.35",
         energy_per_node(500, 0.08, 1.35), 300.79, 0.01)
    near("8-GPU fatigue at R=36", fatigue_per_node(), 612.50, 0.01)
    near("fatigue ceiling", fatigue_per_node(ratio=1e12), 630.00, 0.01)
    near("total per node", energy_per_node() + fatigue_per_node(), 1214.07, 0.01)

    print("self-test: 8,000-GPU base scenario")
    r = legs(8_000)
    near("nodes", r["nodes"], 1000)
    near("energy", r["energy"], 601_572, 1)
    near("fatigue", r["fatigue"], 612_500, 0.5)
    near("total", r["saving"], 1_214_072, 1)
    near("capacity MW", r["capacity_mw"], 0.635858, 1e-5)
    near("extra nodes (floor)", r["extra_nodes"], 62)
    near("extra GPUs", r["extra_gpus"], 496)
    near("capacity revenue", r["revenue"], 10_401_834, 1)

    print("self-test: boundaries and attribution")
    near("GPUs for $1M, total", breakeven_gpus(), 6_592, 0)
    near("GPUs for $1M, energy only", breakeven_gpus(energy_only=True), 13_304, 0)
    a = attributable(8_000, 0.5)
    near("50% owned, direct", a["direct"], 607_036, 0.5)
    near("50% owned, capacity", a["capacity"], 5_200_917, 1)
    near("36k naive total (liquid trap)", legs(36_000)["saving"], 5_463_325, 1)

    print(f"\n{16 - failures}/16 checks passed")
    return 1 if failures else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gpus", type=int, default=8_000)
    ap.add_argument("--owned", type=float, default=OWNED,
                    help="share of fan power Together pays for (0..1)")
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

    print("TOGETHER AI  -  air-cooled H100/H200 fleet, three legs")
    print(f"fan {args.fan_w:,.0f} W/node, duty {DUTY_BASE:.0%}->{DUTY_CTRL:.0%}, "
          f"${args.tariff}/kWh, PUE {args.pue}, H100 ${args.gpu_price}/GPU-hr, "
          f"{args.util:.0%} util")
    print(f"fatigue: R={args.ratio:g} swing scenario; cycle simulator 1.3-1.8x Coffin-Manson\n")

    print(f"{'GPUs':>7} {'nodes':>6} {'energy $/yr':>13} {'fatigue $/yr':>14} "
          f"{'saving $/yr':>13} {'MW freed':>9}")
    for gpus in (2_000, 4_000, args.gpus, 16_000):
        r = legs(gpus, **kw)
        print(f"{r['gpus']:>7,} {r['nodes']:>6,} {r['energy']:>13,.0f} "
              f"{r['fatigue']:>14,.0f} {r['saving']:>13,.0f} "
              f"{r['capacity_mw']:>9,.2f}")

    print("\nownership split (who actually pays the fan power)")
    print(f"{'owned':>6} {'Together direct':>16} {'Together capacity':>18} "
          f"{'partner direct':>15}")
    for owned in (1.0, 0.75, 0.5, 0.25, 0.0):
        a = attributable(args.gpus, owned, **kw)
        print(f"{owned:>6.0%} {a['direct']:>16,.0f} {a['capacity']:>18,.0f} "
              f"{a['partner_direct']:>15,.0f}")

    print("\ncapacity leg at 100% ownership (revenue capacity, not a saving)")
    r = legs(args.gpus, **kw)
    print(f"  {r['capacity_mw']:,.2f} MW freed -> {r['extra_nodes']:,} extra nodes "
          f"= {r['extra_gpus']:,} GPUs")
    print(f"  ${r['revenue']:,.0f}/yr at {args.util:.0%} utilization "
          f"and ${args.gpu_price}/GPU-hr")
    print("  (gross revenue; needs capex, demand, and a power constraint)")

    print("\nfan-wattage sensitivity (8,000 GPUs, 100% owned)")
    for fan_w in (1000, 500, 300):
        rr = legs(8_000, **dict(kw, fan_w=fan_w))
        print(f"  {fan_w:>4} W/node -> energy ${rr['energy']:>11,.0f}  "
              f"total ${rr['saving']:>11,.0f}  "
              f"capacity ${rr['revenue']:>12,.0f}/yr")

    print("\nboundaries")
    print(f"  GPUs for $1M total:       {breakeven_gpus(**kw):>7,}")
    print(f"  GPUs for $1M energy-only: {breakeven_gpus(energy_only=True, **kw):>7,}")
    need = 1_000_000.0 / legs(args.gpus, **kw)["saving"]
    print(f"  ownership needed at {args.gpus:,} GPUs: {need:>6.1%}")

    print("\nliquid trap")
    trap = legs(36_000, **kw)
    print(f"  36,000 GB200 NVL72 GPUs are liquid: fan saving $0, not "
          f"${trap['saving']:,.0f}/yr")
    print(f"  the naive capacity number would be ${trap['revenue']:,.0f}/yr")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
