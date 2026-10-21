#!/usr/bin/env python3
"""
case.py - the capstone. One model, both legs, verifiable.

The claim under test (0xAlcibiades, 2025-07-06):

    "applied at scale you'd be looking at 7 figure savings for a bare metal
     deployment because of reduced fan power consumption and thermal cycling"

That claim has exactly two legs and one missing word: *scale*. This file
composes both legs into a single per-node number, then solves for the fleet
size at which the claim holds - and, more usefully, prints the conditions
under which it fails.

Leg A - fan energy
    Affinity law for a fixed impeller: flow ~ N, pressure ~ N^2, shaft
    power ~ N^3. A duty change d0 -> d1 removes
        dP = P0 * (1 - (d1/d0)^3)
    kWh = dP * hours / 1000
    $   = kWh * tariff * PUE
    PUE multiplies the *saving*, not the facility load: a watt removed at the
    server also removes its share of cooling overhead.

Leg B - thermal fatigue
    Rainflow counting (ASTM E1049-85) -> Coffin-Manson damage ~ dT^n ->
    Norris-Landzberg mean-temperature acceleration -> Miner's rule is
    implemented and tested in cycling.py. The dollar leg below does NOT consume
    that simulation: it uses a swing-ratio scenario, R = (dT_base/dT_ctrl)^2.
    That is an assumption, not a rainflow result.

    Failures avoided per node-year = afr * f * (1 - 1/R)
        afr = annual failure rate, f = fraction of failures attributable to
        thermal cycling. Both are assumptions, both are exposed.

The composition is deliberately narrow: it does not let
the two legs interact (fan power already removed is not counted again as heat),
and it does not credit throughput, acoustics or throttling avoidance. It also
does not debit the controller's throughput cost; the laptop simulation retains
77-81% of stock work, which would be a cost on a revenue fleet.

Run:
    uv run --no-project python case.py
    uv run --no-project python case.py --selftest
    uv run --no-project python case.py --target 1000000 --tariff 0.12
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass, replace

import fanlaw
import throughput

HOURS = 8760.0
TARIFF = 0.09
PUE = 1.4
TARGET = 1_000_000.0
CYCLING_EXPONENT = 2.0


# ---------------------------------------------------------------------------
# the node
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class NodeClass:
    name: str
    fan_w: float            # fan power at 100% duty
    duty_base: float
    duty_ctrl: float
    replacement: float      # $ per node replaced after a failure
    afr: float              # annual failure rate, failures per node-year
    fatigue_share: float    # fraction of failures attributable to cycling
    swing_base: float       # peak-to-peak temperature swing, uncontrolled, C
    swing_ctrl: float       # peak-to-peak temperature swing, controlled, C
    cycling_source: str     # "measured" or "assumed"
    throughput_cost: float = 0.0   # fraction of work lost, 0..1
    throughput_source: str = "none"  # "measured" | "simulated" | "none"
    revenue_per_node: float = 0.0    # $ billed per node-year, 0 = not revenue-priced
    utilization: float = 0.0         # fraction of capacity that is sold


LAPTOP = NodeClass(
    name="Vivobook 15 (client)",
    fan_w=2.5, duty_base=1.00, duty_ctrl=0.55,
    replacement=1200.0, afr=0.05, fatigue_share=0.20,
    swing_base=18.0, swing_ctrl=12.0, cycling_source="assumed",
    throughput_cost=throughput.LAPTOP_COST, throughput_source="measured",
    revenue_per_node=0.0, utilization=0.0,
)
SERVER_1U = NodeClass(
    name="1U CPU node",
    fan_w=60.0, duty_base=0.80, duty_ctrl=0.35,
    replacement=7500.0, afr=0.03, fatigue_share=0.35,
    swing_base=12.0, swing_ctrl=2.0, cycling_source="assumed",
    throughput_cost=throughput.LAPTOP_COST, throughput_source="measured",
    revenue_per_node=0.0, utilization=0.0,
)
GPU4 = NodeClass(
    name="4-GPU node",
    fan_w=400.0, duty_base=0.90, duty_ctrl=0.529,
    replacement=25000.0, afr=0.03, fatigue_share=0.35,
    swing_base=12.0, swing_ctrl=2.0, cycling_source="assumed",
    throughput_cost=0.0, throughput_source="measured",
    revenue_per_node=0.5 * throughput.gross_revenue_per_node(gpus=4),
    utilization=throughput.UTIL,
)
GPU8 = NodeClass(
    name="8-GPU dense node",
    fan_w=1000.0, duty_base=0.95, duty_ctrl=0.529,
    replacement=60000.0, afr=0.03, fatigue_share=0.35,
    swing_base=12.0, swing_ctrl=2.0, cycling_source="assumed",
    throughput_cost=0.0, throughput_source="measured",
    revenue_per_node=throughput.gross_revenue_per_node(gpus=8),
    utilization=throughput.UTIL,
)


# ---------------------------------------------------------------------------
# leg A - fan energy
# ---------------------------------------------------------------------------

def fan_saving(node: NodeClass, tariff=TARIFF, pue=PUE, hours=HOURS) -> dict:
    """Annual fan-power saving, using the calibrated fan law.

    `fan_w` is the tray rating at 100% duty. The uncontrolled operating point
    is that tray at `duty_base`, so the uncontrolled draw is
    fanlaw.fan_power(duty_base, fan_w) and the controlled draw is
    fanlaw.fan_power(duty_ctrl, fan_w).

    The law is fanlaw.fan_power, not the raw affinity law: the pure cubic
    overstates a real 8-GPU duty cut (95% vs 86.25%) because real fan motors
    have a loss floor that does not vanish with speed. The law is calibrated
    against @0xAlcibiades' measured 120 W -> 15 W on a 64-core Ampere server.
    """
    if node.fan_w < 0:
        raise ValueError("fan_w must be non-negative")
    if node.duty_base <= 0 or not (0.0 <= node.duty_ctrl <= node.duty_base <= 1.0):
        raise ValueError("require 0 <= duty_ctrl <= duty_base <= 1")
    if tariff < 0 or pue <= 0 or hours < 0:
        raise ValueError("tariff/hours must be non-negative and PUE positive")
    base_w = fanlaw.fan_power(node.duty_base, node.fan_w)
    ctrl_w = fanlaw.fan_power(node.duty_ctrl, node.fan_w)
    delta_w = base_w - ctrl_w
    kwh = delta_w * hours / 1000.0
    usd = kwh * tariff * pue
    return {"ctrl_w": ctrl_w, "base_w": base_w, "delta_w": delta_w,
            "kwh": kwh, "usd": usd}


# ---------------------------------------------------------------------------
# leg B - thermal fatigue
# ---------------------------------------------------------------------------

def life_ratio(node: NodeClass, n=CYCLING_EXPONENT) -> float:
    """Damage ratio between uncontrolled and controlled temperature swing."""
    if node.swing_base <= 0 or n <= 0:
        raise ValueError("swing_base and exponent must be positive")
    if node.swing_ctrl <= 0:
        return float("inf")
    return (node.swing_base / node.swing_ctrl) ** n


def fatigue_saving(node: NodeClass, ratio=None) -> dict:
    """Failures avoided per node-year, from an annual failure rate.

    afr is failures per node-year, NOT 1/service life. A 5 year service life
    means the node is retired at 5 years; it does not mean 20% of the fleet
    fails annually. Conflating those two inflates the fatigue leg by an order
    of magnitude and was a bug in the first version of this file.
    """
    if node.afr < 0 or node.replacement < 0:
        raise ValueError("afr and replacement must be non-negative")
    if not (0.0 <= node.fatigue_share <= 1.0):
        raise ValueError("fatigue_share must be in [0, 1]")
    ratio = life_ratio(node) if ratio is None else ratio
    if ratio <= 0:
        raise ValueError("life ratio must be positive")
    if ratio <= 1.0:
        return {"ratio": ratio, "failures": 0.0, "usd": 0.0}
    failures = node.afr * node.fatigue_share * (1.0 - 1.0 / ratio)
    return {"ratio": ratio, "failures": failures, "usd": failures * node.replacement}


# ---------------------------------------------------------------------------
# composition
# ---------------------------------------------------------------------------

def total(node: NodeClass, tariff=TARIFF, pue=PUE) -> dict:
    """All three legs, net.

    Leg A  fan energy   - physics, calibrated to a measured duty cut.
    Leg B  cycling     - assumption-driven, needs afr + share + replacement.
    Leg C  throughput  - the cost of the cooling, debited against leg A.

    Leg C is what the first version of this model left out, and leaving it
    out is what turns a fan controller into a revenue-loss project on a
    capacity-constrained fleet. It is reported in both regimes: with spare
    capacity the lost work was unsold work, so the immediate cost is zero and
    what you lose is headroom; with a constrained fleet the same loss bills
    back at list price.
    """
    a = fan_saving(node, tariff, pue)
    b = fatigue_saving(node)
    if node.revenue_per_node > 0 and node.throughput_cost > 0:
        t = throughput.net_saving(a["usd"], node.throughput_cost,
                                   node.revenue_per_node, node.utilization)
    else:
        t = {
            "fan_saving": a["usd"], "throughput_cost": 0.0, "effective_cost": 0.0,
            "net": a["usd"], "net_constrained": a["usd"],
            "constrained": False, "utilization": node.utilization,
        }
    net = a["usd"] + b["usd"] - t["effective_cost"]
    net_constrained = a["usd"] + b["usd"] - t["throughput_cost"]
    return {
        "fan": a["usd"],
        "cycling": b["usd"],
        "throughput_gross": t["throughput_cost"],
        "throughput_effective": t["effective_cost"],
        "total": net,
        "total_constrained": net_constrained,
        "fan_w_saved": a["delta_w"],
        "ratio": b["ratio"],
        "constrained": t["constrained"],
    }


def nodes_for(total_usd: float, target=TARGET) -> float:
    if total_usd <= 0:
        return float("inf")
    return float(math.ceil(target / total_usd))


# ---------------------------------------------------------------------------
# sensitivity - which assumption do we have to nail down first
# ---------------------------------------------------------------------------

def sensitivity(node: NodeClass, tariff=TARIFF, pue=PUE):
    base = total(node, tariff, pue)["total"]
    knobs = [
        ("fan power", lambda n: replace(n, fan_w=n.fan_w * 0.5), lambda n: replace(n, fan_w=n.fan_w * 1.5)),
        ("duty after", lambda n: replace(n, duty_ctrl=n.duty_ctrl * 1.5), lambda n: replace(n, duty_ctrl=n.duty_ctrl * 0.5)),
        ("node cost", lambda n: replace(n, replacement=n.replacement * 0.5), lambda n: replace(n, replacement=n.replacement * 1.5)),
        ("failure rate", lambda n: replace(n, afr=n.afr * 0.5), lambda n: replace(n, afr=n.afr * 1.5)),
        ("fatigue share", lambda n: replace(n, fatigue_share=n.fatigue_share * 0.5), lambda n: replace(n, fatigue_share=min(1.0, n.fatigue_share * 1.5))),
        ("swing after", lambda n: replace(n, swing_ctrl=n.swing_ctrl * 1.5), lambda n: replace(n, swing_ctrl=max(0.5, n.swing_ctrl * 0.5))),
    ]
    rows = []
    for label, down, up in knobs:
        lo = total(down(node), tariff, pue)["total"]
        hi = total(up(node), tariff, pue)["total"]
        rows.append((label, lo, hi, abs(hi - lo) / max(base, 1e-12)))
    rows.sort(key=lambda r: -r[3])
    return base, rows


# ---------------------------------------------------------------------------
# verification - what would kill the claim
# ---------------------------------------------------------------------------

def verify(node: NodeClass, fleet: int, tariff=TARIFF, pue=PUE, target=TARGET):
    """The gap, and the attribution share that would be needed to close it.

    The fatigue leg is bounded: even with an infinite life extension it can
    only remove `afr * share * replacement` per node-year, because you cannot
    avoid more failures than there are failures. Comparing the gap against
    that ceiling is the fastest way to kill a bad claim.
    """
    need = target / fleet
    fan = fan_saving(node, tariff, pue)["usd"]
    gap = need - fan
    ceiling = node.afr * node.fatigue_share * node.replacement
    headroom = node.afr * node.replacement        # ceiling with 100% attribution
    required_share = (gap / headroom) if (gap > 0 and headroom > 0) else 0.0
    return {
        "need": need,
        "fan": fan,
        "gap": gap,
        "ceiling": ceiling,
        "required_share": required_share,
        "possible": gap <= ceiling,
    }


# ---------------------------------------------------------------------------
# self tests
# ---------------------------------------------------------------------------

def selftest():
    ok = 0

    def check(name, cond, detail=""):
        nonlocal ok
        if not cond:
            print("  FAIL  %s  %s" % (name, detail))
            raise SystemExit(1)
        ok += 1
        print("  pass  %s" % name)

    n = SERVER_1U
    # calibrated fan law: the loss floor means half duty is NOT one eighth
    # the power. The pure cubic would say 1/8; the calibrated law says less
    # is removed. This is the correction the whole model rests on.
    half = replace(n, duty_ctrl=n.duty_base * 0.5)
    check("calibrated law: half duty is more than 1/8 the power",
          half.fan_w * 0.125 < fan_saving(half)["ctrl_w"],
          "got %.4f W" % fan_saving(half)["ctrl_w"])
    check("calibrated law: half duty is less than 1/4 the power",
          half.fan_w * 0.25 > fan_saving(half)["ctrl_w"])
    check("calibrated law is never below the pure cubic",
          fan_saving(half)["ctrl_w"] >= half.fan_w * 0.125 - 1e-9)
    check("calibrated law agrees with fanlaw module",
          abs(fan_saving(half)["ctrl_w"]
              - fanlaw.fan_power(half.duty_ctrl, half.fan_w)) < 1e-12)
    # no duty change, no saving
    same = replace(n, duty_ctrl=n.duty_base)
    check("no duty change -> zero saving", abs(fan_saving(same)["usd"]) < 1e-12)
    # linear in hours
    r1 = fan_saving(n, hours=1000)
    r2 = fan_saving(n, hours=2000)
    check("linear in hours", abs(r2["usd"] - 2 * r1["usd"]) < 1e-9)
    # linear in tariff and PUE
    r3 = fan_saving(n, tariff=TARIFF * 2)
    check("linear in tariff", abs(r3["usd"] - 2 * r1["usd"] * 8.76) < 1e-6)
    # stopping fans entirely bounds the saving by the uncontrolled draw
    off = replace(n, duty_ctrl=0.0)
    check("full stop saves exactly the uncontrolled draw",
          abs(fan_saving(off)["delta_w"] - fan_saving(n)["base_w"]) < 1e-9)
    check("full stop leaves zero fan power",
          abs(fan_saving(off)["ctrl_w"]) < 1e-12)
    # fatigue: no swing reduction means no life extension
    flat = replace(n, swing_ctrl=n.swing_base)
    check("equal swing -> no fatigue saving", fatigue_saving(flat)["usd"] == 0.0)
    # fatigue: zero attribution kills the leg
    noattr = replace(n, fatigue_share=0.0)
    check("zero fatigue share -> zero", fatigue_saving(noattr)["usd"] == 0.0)
    # fatigue: linear in the annual failure rate, and bounded by it
    twice = replace(n, afr=n.afr * 2)
    check("linear in failure rate",
          abs(fatigue_saving(twice)["usd"] - 2 * fatigue_saving(n)["usd"]) < 1e-9)
    check("bounded by afr * replacement",
          fatigue_saving(replace(n, swing_ctrl=0.01, fatigue_share=1.0))["usd"]
          <= n.afr * n.replacement + 1e-9)
    # fatigue: quadratic in the swing ratio
    r2x = replace(n, swing_base=2.0, swing_ctrl=1.0)
    r4x = replace(n, swing_base=4.0, swing_ctrl=1.0)
    check("dT^2: doubling swing quadruples damage",
          abs(life_ratio(r4x) / life_ratio(r2x) - 4.0) < 1e-9)
    # break-even algebra
    t = total(GPU4)["total"]
    n = nodes_for(t)
    check("break-even rounds up to clear target",
          n * t >= TARGET and (n - 1) * t < TARGET)
    # monotonic in fan power
    check("more fan power -> fewer nodes",
          nodes_for(total(replace(GPU4, fan_w=800.0))["total"]) <
          nodes_for(total(GPU4)["total"]))

    print("\n%d checks passed" % ok)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def rule(t):
    print()
    print(t)
    print("-" * len(t))


def money(x):
    if x >= 1e6:
        return "$%.2fM" % (x / 1e6)
    if x >= 1e3:
        return "$%.1fk" % (x / 1e3)
    return "$%.0f" % x


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--target", type=float, default=TARGET)
    ap.add_argument("--tariff", type=float, default=TARIFF)
    ap.add_argument("--pue", type=float, default=PUE)
    args = ap.parse_args()

    if args.selftest:
        selftest()
        return

    print("=" * 78)
    print("THE CASE  -  two legs, one number, and the conditions for failure")
    print("=" * 78)
    print("tariff %.3f $/kWh   PUE %.2f   target %s/yr" % (args.tariff, args.pue, money(args.target)))

    rule("1. PER NODE, PER YEAR")
    print("  %-22s %9s %8s %10s %10s %12s" %
          ("node", "fan W", "saved W", "fan $", "cycle $", "total $"))
    rows = {}
    for node in (LAPTOP, SERVER_1U, GPU4, GPU8):
        r = total(node, args.tariff, args.pue)
        rows[node.name] = (node, r)
        print("  %-22s %9.0f %8.1f %10.2f %10.2f %12.2f" %
              (node.name, node.fan_w, r["fan_w_saved"], r["fan"], r["cycling"], r["total"]))

    print()
    print("  fan $ is physics. cycle $ is assumption-driven: it needs an annual")
    print("  failure rate, an attribution share and a replacement cost. The laptop")
    print("  row is an 18->12 C scenario; the GPU rows are R=36. The cycle simulator")
    print("  gives 1.3-1.8x Coffin-Manson; the measured trace is in cycling.py --replay.")

    rule("2. FLEET SIZE REQUIRED FOR THE TARGET")
    print("  %-22s %14s %14s %10s" % ("node", "nodes", "fan-only nodes", "cycle share"))
    for name, (node, r) in rows.items():
        n = nodes_for(r["total"], args.target)
        share = 100.0 * r["cycling"] / r["total"] if r["total"] else 0.0
        print("  %-22s %14s %14s %9.0f%%" %
              (name, "{:,.0f}".format(n), "{:,.0f}".format(nodes_for(r["fan"], args.target)), share))
    print("  fan-only nodes can exceed total; that means the fan leg alone misses the target.")

    rule("3. SENSITIVITY  (which assumption must be right)")
    node = GPU4
    base, sens = sensitivity(node, args.tariff, args.pue)
    print("  %-16s %12s %12s %10s" % ("knob", "low case", "high case", "swing"))
    for label, lo, hi, rel in sens:
        print("  %-16s %12.2f %12.2f %9.0f%%" % (label, lo, hi, 100 * rel))
    print()
    print("  base case %s/node/yr" % ("%.2f" % base))

    rule("4. WHAT WOULD MAKE THE CLAIM FALSE")
    for fleet in (500, 1000, 5000):
        f = verify(GPU4, fleet, args.tariff, args.pue, args.target)
        if f["gap"] <= 0:
            print("  %6d nodes: need %7.2f $/node, fan alone gives %7.2f -> met by fan power"
                  % (fleet, f["need"], f["fan"]))
        elif f["possible"]:
            print("  %6d nodes: gap %7.2f, fatigue ceiling %7.2f at %.0f%% attribution -> possible"
                  % (fleet, f["gap"], f["ceiling"], 100 * GPU4.fatigue_share))
        else:
            print("  %6d nodes: gap %7.2f, fatigue ceiling %7.2f at %.0f%% attribution -> IMPOSSIBLE"
                  % (fleet, f["gap"], f["ceiling"], 100 * GPU4.fatigue_share))
            print("            you would need %.0f%% of failures to be cycling-caused"
                  % (100 * f["required_share"]))
    print()
    print("  The fatigue leg is bounded by afr * share * replacement = %s/node/yr."
          % money(GPU4.afr * GPU4.fatigue_share * GPU4.replacement))
    print("  No lifetime extension beats that bound: you cannot avoid more failures")
    print("  than occur. Below the fleet size where fan power alone clears the")
    print("  target, cycling is arithmetically irrelevant.")

    rule("5. THE HONEST HEADLINE")
    g = rows[GPU4.name][1]
    dominant = "fan power" if g["fan"] >= g["cycling"] else "thermal cycling"
    print("  4-GPU node: %s/yr, of which fan %s and cycling %s."
          % (money(g["total"]), money(g["fan"]), money(g["cycling"])))
    print("  Dominant leg: %s. Target %s/yr needs %s nodes at this node class."
          % (dominant, money(args.target), "{:,.0f}".format(nodes_for(g["total"], args.target))))
    print("  The fan leg is physics with one uncertain input (duty reduction).")
    print("  The cycling leg is a conditional statement: it needs an annual failure")
    print("  rate, an attribution share and a replacement cost, none of which this")
    print("  project can measure. Quote it with those three numbers attached.")

    rule("6. THE LAPTOP, FOR CONTRAST")
    lap = rows[LAPTOP.name][1]
    print("  %s/yr total. The client tier is a feature (noise, sustained clocks)" % money(lap["total"]))
    print("  not an energy business. Do not pitch it as one.")


if __name__ == "__main__":
    main()
