#!/usr/bin/env python3
"""
Modal case: the fan bill Modal cannot capture.

Public anchors (sources in MODAL-CASE.md):
  $1B annualized run rate, $750M Series D at $15.75B (Oct 2026)
  capacity pool across 20+ clouds; 13 cloud partners (DCD, Oct 2026)
  Modal does not own or operate data centers (DCD; CTO on Latent Space, 2026)
  H100 SXM5 $0.001097/sec = $3.95/GPU-hr; B200 $0.001736/sec = $6.25/GPU-hr

Modal is a serverless platform on top of other people's capacity. It schedules
GPUs; it does not own the node, the BMC, or the fan. The fan bill is real, but
it lands on the 13 capacity providers' P&L, not on Modal's.

This case therefore answers a different question from the Lambda and Together
cases:

    what would the claim be worth to Modal if it owned the fleet?
    what does Modal already do that is worth more?

The first number is derived from ARR and list price, not from a published GPU
count. The second is the utilization lever, which is Modal's actual business.

    uv run python code/modal_case.py --selftest
    uv run python code/modal_case.py
    uv run python code/modal_case.py --arr 2e9 --provider-share 0.5
"""
from __future__ import annotations

import argparse
import math

HOURS = 8760.0
GPUS_PER_NODE = 8
NODE_KW = 10.2
FAN_W = 1000.0
DUTY_BASE = 0.95
DUTY_CTRL = 0.35
TARIFF = 0.08
PUE = 1.35
AFR = 0.03
SHARE = 0.35
REPLACEMENT = 60_000.0
LIFE_RATIO = 36.0
GPU_PRICE = 3.9492
UTIL = 0.60
PROVIDER_SHARE = 1.0
PROVIDERS = 13


def saved_watts(fan_w: float, duty_base: float = DUTY_BASE,
                duty_ctrl: float = DUTY_CTRL) -> float:
    if fan_w < 0:
        raise ValueError("fan_w must be non-negative")
    if not (0.0 < duty_ctrl <= duty_base <= 1.0):
        raise ValueError("require 0 < duty_ctrl <= duty_base <= 1")
    return fan_w * (1.0 - (duty_ctrl / duty_base) ** 3)


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


def active_gpus(arr: float, price: float = GPU_PRICE,
                util: float = UTIL) -> float:
    """Average active GPU-equivalents implied by ARR at a list price.

    This is a scale estimate, not an upper bound. Non-GPU revenue pushes the
    true count down; a lower realized price or lower utilization pushes it up.
    The direction of the error is not known, so the output is a scenario.
    """
    if arr <= 0 or price <= 0 or not (0.0 < util <= 1.0):
        raise ValueError("arr, price and util must be positive; util <= 1")
    return arr / (price * HOURS * util)


def fan_bill(gpus: float, fan_w: float = FAN_W, tariff: float = TARIFF,
             pue: float = PUE, util: float = UTIL,
             gpu_price: float = GPU_PRICE, afr: float = AFR,
             share: float = SHARE, replacement: float = REPLACEMENT,
             ratio: float = LIFE_RATIO, node_kw: float = NODE_KW) -> dict:
    if gpus <= 0:
        raise ValueError("gpus must be positive")
    if node_kw <= 0:
        raise ValueError("node_kw must be positive")
    if not (0.0 <= util <= 1.0):
        raise ValueError("util must be in [0, 1]")
    if gpu_price < 0:
        raise ValueError("gpu_price must be non-negative")
    nodes = int(gpus // GPUS_PER_NODE)
    if nodes == 0:
        raise ValueError("fewer than one 8-GPU node")
    e_node = energy_per_node(fan_w, tariff, pue)
    f_node = fatigue_per_node(afr, share, replacement, ratio)
    cap_w = nodes * saved_watts(fan_w)
    extra_nodes = int(cap_w / (node_kw * 1000.0))
    extra_gpus = extra_nodes * GPUS_PER_NODE
    revenue = extra_gpus * gpu_price * HOURS * util
    return {
        "gpus": nodes * GPUS_PER_NODE,
        "nodes": nodes,
        "energy_node": e_node,
        "fatigue_node": f_node,
        "energy": nodes * e_node,
        "fatigue": nodes * f_node,
        "total": nodes * (e_node + f_node),
        "capacity_mw": cap_w / 1e6,
        "extra_nodes": extra_nodes,
        "extra_gpus": extra_gpus,
        "revenue": revenue,
    }


def pass_through(total: float, provider_share: float = PROVIDER_SHARE) -> dict:
    """Split a fan saving between the capacity providers and Modal.

    provider_share = 1.0  the providers pay the meter and keep the saving.
    provider_share = 0.0  Modal has a full power-indexed contract.
    """
    if not (0.0 <= provider_share <= 1.0):
        raise ValueError("provider share must be in [0, 1]")
    return {
        "provider": total * provider_share,
        "platform": total * (1.0 - provider_share),
    }


def utilization_gain(gpus: float, util_base: float = 0.35,
                     util_ctrl: float = 0.60,
                     price: float = GPU_PRICE) -> dict:
    """Billable GPU-hours gained by packing the same fleet harder."""
    if not (0.0 < util_base <= util_ctrl <= 1.0):
        raise ValueError("require 0 < util_base <= util_ctrl <= 1")
    extra_hours = gpus * HOURS * (util_ctrl - util_base)
    return {
        "extra_hours": extra_hours,
        "revenue": extra_hours * price,
        "multiplier": util_ctrl / util_base,
    }


def qualification(owns_datacenter: bool, owns_nodes: bool,
                  controls_bmc: bool, pays_power: bool) -> str:
    """The four questions that decide whether the claim routes to a target.

    Building and node ownership are context, not gates: a lessee can control
    the BMC and pay the meter (Lambda). The decisive pair is access and
    payment. A target with access but no power bill is conditional, because
    the saving exists but belongs to the landlord.
    """
    if controls_bmc and pays_power:
        return "qualified"
    if controls_bmc and not pays_power:
        return "conditional"
    return "disqualified"


def breakeven_gpus(target: float = 1_000_000.0, **kwargs) -> int:
    if target <= 0:
        raise ValueError("target must be positive")
    per_node = energy_per_node(
        kwargs.get("fan_w", FAN_W),
        kwargs.get("tariff", TARIFF),
        kwargs.get("pue", PUE),
    ) + fatigue_per_node(
        kwargs.get("afr", AFR),
        kwargs.get("share", SHARE),
        kwargs.get("replacement", REPLACEMENT),
        kwargs.get("ratio", LIFE_RATIO),
    )
    return math.ceil(target / per_node) * GPUS_PER_NODE


def selftest() -> int:
    failures = 0

    def near(name: str, got: float, want: float, tol: float = 1e-6) -> None:
        nonlocal failures
        ok = abs(got - want) <= tol
        if not ok:
            failures += 1
        print(f"  {'pass' if ok else 'FAIL'}  {name}"
              + ("" if ok else f"  got {got!r} want {want!r}"))

    print("self-test: derived fleet")
    g = active_gpus(1e9)
    near("active GPUs at $1B / $3.9492 / 60%", g, 48_176.5, 1.0)
    near("nodes", int(g // GPUS_PER_NODE), 6_022, 0)

    print("self-test: the fan bill behind the fleet")
    b = fan_bill(g)
    near("energy", b["energy"], 5_412_388, 1)
    near("fatigue", b["fatigue"], 3_688_475, 1)
    near("total", b["total"], 9_100_863, 1)
    near("capacity MW", b["capacity_mw"], 5.720856, 1e-5)
    near("extra nodes", b["extra_nodes"], 560, 0)
    near("extra GPUs", b["extra_gpus"], 4_480, 0)
    near("capacity revenue", b["revenue"], 92_991_339, 1)
    near("share of $1B ARR", b["total"] / 1e9, 0.00910086, 1e-7)

    print("self-test: pass-through and qualification")
    p = pass_through(b["total"], 1.0)
    near("providers keep", p["provider"], 9_100_863, 1)
    near("Modal keeps", p["platform"], 0.0, 1e-9)
    near("GPUs for $1M, anyone", breakeven_gpus(), 5_296, 0)
    near("qualification: no ownership",
         qualification(False, False, False, False) == "disqualified", 1, 0)
    near("qualification: landlord pays",
         qualification(True, True, True, False) == "conditional", 1, 0)
    near("qualification: full ownership",
         qualification(True, True, True, True) == "qualified", 1, 0)

    print("self-test: the lever Modal actually has")
    u = utilization_gain(g, 0.35, 0.60)
    near("extra GPU-hours", u["extra_hours"], 105_506_600, 1)
    near("gross revenue", u["revenue"], 416_666_667, 1)
    near("utilization multiplier", u["multiplier"], 1.714286, 1e-5)

    print(f"\n{17 - failures}/17 checks passed")
    return 1 if failures else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--arr", type=float, default=1e9)
    ap.add_argument("--provider-share", type=float, default=PROVIDER_SHARE)
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

    print("MODAL  -  the platform that does not own the fans")
    print(f"${args.arr/1e9:.2f}B ARR, H100 ${args.gpu_price}/GPU-hr, "
          f"{args.util:.0%} utilization, fan {args.fan_w:,.0f} W/node, "
          f"${args.tariff}/kWh, PUE {args.pue}")
    print(f"fatigue: R={args.ratio:g} swing scenario; cycle simulator 1.3-1.8x Coffin-Manson\n")

    g = active_gpus(args.arr, args.gpu_price, args.util)
    b = fan_bill(g, **kw)
    print(f"derived active fleet: {g:,.0f} H100-equivalents "
          f"= {b['nodes']:,} modeled nodes ({b['gpus']:,} GPUs)")
    print("(scale estimate, not an upper bound: non-GPU revenue lowers it;")
    print(" lower realized price or utilization raises it)\n")

    print(f"{'ARR':>8} {'active GPUs':>12} {'nodes':>7} {'fan $/yr':>11} "
          f"{'% of ARR':>9}")
    for arr in (250e6, 500e6, 1e9, 2e9):
        gg = active_gpus(arr, args.gpu_price, args.util)
        bb = fan_bill(gg, **kw)
        print(f"{arr/1e9:>7.2f}B {gg:>12,.0f} {bb['nodes']:>7,} "
              f"{bb['total']:>11,.0f} {bb['total']/arr:>9.3%}")

    print("\nthe fan bill is real, but it is not Modal's")
    print(f"  energy            ${b['energy']:>14,.0f}/yr")
    print(f"  fatigue           ${b['fatigue']:>14,.0f}/yr")
    print(f"  total             ${b['total']:>14,.0f}/yr "
          f"({b['total']/args.arr:.2%} of ARR)")
    print(f"  capacity          ${b['revenue']:>14,.0f}/yr gross "
          f"({b['capacity_mw']:.2f} MW freed)")

    print(f"\npass-through across {PROVIDERS} providers "
          f"(provider share {args.provider_share:.0%})")
    p = pass_through(b["total"], args.provider_share)
    print(f"  providers keep    ${p['provider']:>14,.0f}/yr")
    print(f"  Modal keeps       ${p['platform']:>14,.0f}/yr")

    print("\nthe lever Modal actually has: utilization")
    u = utilization_gain(g, 0.35, 0.60, args.gpu_price)
    print(f"  35% -> 60% on the same fleet = {u['multiplier']:.2f}x billable "
          f"GPU-hours")
    print(f"  +{u['extra_hours']:,.0f} GPU-hours/yr "
          f"= ${u['revenue']:,.0f}/yr gross at list")
    print("  (this is the business model, not a fan saving)")

    print("\nqualification test")
    q = qualification(False, False, False, False)
    print(f"  owns data center: no | owns nodes: no | controls BMC: no | "
          f"pays power: no")
    print(f"  verdict: {q.upper()}")
    print(f"  to capture $1M directly Modal would need {breakeven_gpus():,} "
          f"GPUs it owns; it owns 0.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
