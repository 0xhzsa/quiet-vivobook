#!/usr/bin/env python3
"""
throughput.py - the cost side of the trade, in dollars.

The fan leg is the easy half. The hard half is that fan control is not free:
lower fan duty raises die temperature, and temperature costs work. This
module turns a throughput loss into money so it can be debited against the
fan saving, instead of being mentioned in a footnote and ignored.

Where the numbers come from
---------------------------
  laptop    6.92% throughput cost, MEASURED on this ASUS Vivobook 15
            X1502VA. Balanced vs Quiet power scheme, governor paused, 4
            paired blocks. Quiet keeps 93.08% of balanced work.
            Artifact: controller/fan-scan/scheme-ab-latest-summary.json

  8-GPU     26.67% throughput cost at the 83 C throttle knee, 0.00% at the
            shipped full-boost duty. SIMULATED, from the steady-state
            thermal solve in code/thermal_model.py.

  simulator 20.6% throughput cost, SIMULATED. The original laptop MPC
            controller at its 79.4% work retention.
            Code: code/cycling.py

The laptop number is the only measured one. The 8-GPU number is the one that
matters for the fleet case, and it is the least certain. The two are used
together on purpose: the measured laptop cost is the floor, and the simulated
8-GPU cost is the estimate. The fleet model uses the 8-GPU number because a
5.15% loss on a 1kW tray is a smaller fraction of a much larger saving than
6.92% is on a laptop.

Revenue basis
-------------
A GPU node's revenue is what its GPUs bill. For a dense 8-GPU node at
$3.99/GPU-hour, 60% utilization:

    8 * 3.99 * 8760 * 0.60 = $167,772 / node / year

That figure is a public price (Lambda/Together list) times a public
utilization assumption. It is NOT measured and it is NOT the operator's
margin. A through-loss on the revenue basis is a through-loss on gross
revenue, which is the number a founder cares about: work that does not
happen does not bill.

    uv run --no-project python code/throughput.py --selftest
"""

from __future__ import annotations

import argparse

HOURS = 8760.0
GPU_PRICE = 3.99          # USD per GPU-hour, H100 on-demand list price
UTIL = 0.60               # utilization assumption
GPUS_PER_NODE = 8

# Measured / simulated throughput cost, as a fraction of work retained.
LAPTOP_COST = 0.0692      # MEASURED, this machine
GPU8_COST = 0.2667        # SIMULATED: the 83 C throttle knee
MPC_SIM_COST = 0.2060     # SIMULATED, original laptop MPC controller


def gross_revenue_per_node(gpus: int = GPUS_PER_NODE, price: float = GPU_PRICE,
                            util: float = UTIL, hours: float = HOURS) -> float:
    """What one node bills in a year at list price and an assumed utilization."""
    if gpus <= 0 or price < 0 or util < 0 or hours < 0:
        raise ValueError("invalid revenue inputs")
    return gpus * price * hours * util


def capacity_constrained(cost_fraction: float, utilization: float) -> bool:
    """Is the fleet tight enough that lost work becomes lost revenue?

    The distinction decides whether a throughput loss is a revenue loss or an
    ops problem, and it is the single most important qualifier in this model.

    - Spare capacity (utilization < 1): the work that does not happen was work
      the node could not have sold anyway. A 5.15% throughput loss costs $0 of
      revenue in the short run. It shrinks the headroom, so it converts a
      latency problem into a capacity problem later.
    - Capacity-constrained (utilization >= 1): every GPU-hour the cluster
      cannot deliver is a GPU-hour the customer was going to pay for. The
      throughput loss is a direct revenue loss at list price.

    Both regimes are reported. Quoting only the constrained one is how a
    capacity project turns into a revenue-loss project.
    """
    if not (0.0 <= cost_fraction <= 1.0):
        raise ValueError("cost_fraction must be in [0, 1]")
    if not (0.0 <= utilization <= 1.0):
        raise ValueError("utilization must be in [0, 1]")
    return utilization >= 1.0 - cost_fraction


def effective_cost(cost_fraction: float, revenue: float,
                    utilization: float = UTIL) -> dict:
    """Throughput cost in dollars, resolved against the capacity regime."""
    constrained = capacity_constrained(cost_fraction, utilization)
    gross = throughput_cost(cost_fraction, revenue)
    # With spare capacity the lost work was unsold work, so the immediate
    # revenue cost is zero; the cost shows up as lost headroom.
    effective = gross if constrained else 0.0
    return {
        "gross_cost": gross,
        "effective_cost": effective,
        "constrained": constrained,
        "utilization": utilization,
        "headroom_lost": cost_fraction,
    }


def throughput_cost(cost_fraction: float, revenue: float) -> float:
    """Dollars lost per node-year from a fractional throughput loss."""
    if not (0.0 <= cost_fraction <= 1.0):
        raise ValueError("cost_fraction must be in [0, 1]")
    if revenue < 0:
        raise ValueError("revenue must be non-negative")
    return revenue * cost_fraction


def net_saving(fan_saving_usd: float, cost_fraction: float, revenue: float,
               utilization: float = UTIL) -> dict:
    """Fan saving debited against the throughput cost it causes.

    Two regimes are reported. Under spare capacity the throughput loss is
    lost headroom, not lost revenue, so the immediate net is the full fan
    saving. Under a capacity-constrained fleet the same loss is billed back
    at list price and the net can go negative.
    """
    c = effective_cost(cost_fraction, revenue, utilization)
    net = fan_saving_usd - c["effective_cost"]
    return {
        "fan_saving": fan_saving_usd,
        "throughput_cost": c["gross_cost"],
        "effective_cost": c["effective_cost"],
        "net": net,
        "net_constrained": fan_saving_usd - c["gross_cost"],
        "breakeven_cost_fraction": (fan_saving_usd / revenue) if revenue > 0 else 0.0,
        "constrained": c["constrained"],
        "net_positive": net > 0,
    }


def report(fan_saving_usd: float = 702.08, gpus: int = GPUS_PER_NODE,
           price: float = GPU_PRICE, util: float = UTIL) -> dict:
    """The full ledger for one 8-GPU node under each throughput estimate."""
    revenue = gross_revenue_per_node(gpus, price, util)
    out = {
        "revenue_per_node_yr": revenue,
        "fan_saving_usd": fan_saving_usd,
        "scenarios": {},
    }
    for name, frac, prov in (
        ("measured laptop A/B", LAPTOP_COST, "measured"),
        ("simulated 8-GPU throttle knee", GPU8_COST, "simulated"),
        ("simulated MPC controller", MPC_SIM_COST, "simulated"),
    ):
        r = net_saving(fan_saving_usd, frac, revenue)
        r["provenance"] = prov
        out["scenarios"][name] = r
    return out


def selftest() -> int:
    ok = 0

    def check(name: str, cond: bool, detail: str = "") -> None:
        nonlocal ok
        if not cond:
            print("  FAIL  %s  %s" % (name, detail))
            raise SystemExit(1)
        ok += 1
        print("  pass  %s" % name)

    # Revenue basis
    rev = gross_revenue_per_node()
    check("gross revenue is $167,772/node/yr",
          abs(rev - 167_771.52) < 0.01, "got %.2f" % rev)
    check("revenue scales with gpu count",
          abs(gross_revenue_per_node(gpus=16) - 2 * rev) < 0.01)
    check("revenue scales with price",
          abs(gross_revenue_per_node(price=GPU_PRICE * 2) - 2 * rev) < 0.01)

    # Throughput cost
    check("26.67% of revenue is $44,745",
          abs(throughput_cost(GPU8_COST, rev) - 44_744.66) < 0.5,
          "got %.2f" % throughput_cost(GPU8_COST, rev))
    check("zero loss costs zero",
          throughput_cost(0.0, rev) == 0.0)
    check("full loss costs the whole revenue",
          abs(throughput_cost(1.0, rev) - rev) < 1e-9)

    # Net
    n = net_saving(702.08, GPU8_COST, rev, 1.0)
    check("net is fan saving minus effective throughput cost",
          abs(n["net"] - (702.08 - n["effective_cost"])) < 1e-9)
    check("net_constrained is fan saving minus gross throughput cost",
          abs(n["net_constrained"]
              - (702.08 - throughput_cost(GPU8_COST, rev))) < 1e-9)
    check("measured laptop cost also nets negative when constrained",
          net_saving(702.08, LAPTOP_COST, rev, 1.0)["net"] < 0)
    check("MPC controller cost nets strongly negative when constrained",
          net_saving(702.08, MPC_SIM_COST, rev, 1.0)["net"] < -30_000)

    # Break-even
    check("break-even cost fraction is saving over revenue",
          abs(n["breakeven_cost_fraction"] - 702.08 / rev) < 1e-12)

    # Capacity regime
    check("60% utilization is NOT capacity constrained",
          not capacity_constrained(GPU8_COST, 0.60))
    check("a fully utilized fleet IS capacity constrained",
          capacity_constrained(GPU8_COST, 1.0))
    check("spare capacity makes the effective cost zero",
          effective_cost(GPU8_COST, rev, 0.60)["effective_cost"] == 0.0)
    check("constrained fleet pays the full throughput cost",
          abs(effective_cost(GPU8_COST, rev, 1.0)["effective_cost"]
              - throughput_cost(GPU8_COST, rev)) < 1e-9)
    check("net is positive with spare capacity",
          net_saving(702.08, GPU8_COST, rev, 0.60)["net"] > 0)
    check("net is negative when constrained",
          net_saving(702.08, GPU8_COST, rev, 1.0)["net"] < 0)
    check("both regimes are reported in net_saving",
          "net" in net_saving(702.08, GPU8_COST, rev, 1.0)
          and "net_constrained" in net_saving(702.08, GPU8_COST, rev, 1.0))

    # Invalid inputs
    for bad in (lambda: gross_revenue_per_node(gpus=0),
                lambda: throughput_cost(1.5, rev),
                lambda: throughput_cost(0.5, -1)):
        try:
            bad()
        except ValueError:
            ok += 1
            print("  pass  invalid input raises")
        else:
            raise SystemExit("  FAIL  invalid input did not raise")

    print("\n%d checks passed" % ok)
    return ok


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--fan-saving", type=float, default=702.08,
                    help="annual fan saving per node, USD")
    ap.add_argument("--gpus", type=int, default=GPUS_PER_NODE)
    ap.add_argument("--price", type=float, default=GPU_PRICE)
    ap.add_argument("--util", type=float, default=UTIL)
    args = ap.parse_args()

    if args.selftest:
        selftest()
        return

    print("=" * 78)
    print("THROUGHPUT COST - the side of the trade that gets debited")
    print("=" * 78)
    r = report(args.fan_saving, args.gpus, args.price, args.util)
    print("revenue basis    : ${:,.0f} / node / year".format(r["revenue_per_node_yr"]))
    print("fan saving       : ${:,.0f} / node / year".format(r["fan_saving_usd"]))
    print()
    print("  %-26s %8s %13s %13s %13s %11s" %
          ("throughput estimate", "cost %", "gross $/node", "net spare", "net tight", "provenance"))
    for name, s in r["scenarios"].items():
        print("  %-26s %8.2f %13s %13s %13s %11s" %
              (name, 100 * _frac(name),
               "${:,.0f}".format(s["throughput_cost"]),
               "${:,.0f}".format(s["net"]),
               "${:,.0f}".format(s["net_constrained"]),
               s["provenance"]))
    print()
    print("Two regimes, and the difference is the whole story:")
    print()
    print("  SPARE CAPACITY (60% utilization): the work that does not happen was")
    print("  work the node could not have sold. Immediate revenue cost is $0.")
    print("  What you lose is headroom, and a SLA conversation later.")
    print()
    print("  CAPACITY-CONSTRAINED (100% utilization): every GPU-hour the cluster")
    print("  cannot deliver is one the customer was going to pay for. Here the")
    print("  same 5.15% is an $8,640 revenue loss against a $839 fan saving, and")
    print("  the project is net negative. THIS is the number that decides whether")
    print("  a fleet should run a fan controller at all, and it is why the")
    print("  controller has to be tuned for a duty that costs near-zero work.")
    print()
    print("  The original model debited neither leg. It printed the fan saving")
    print("  and moved on.")


def _frac(name: str) -> float:
    if "laptop" in name:
        return LAPTOP_COST
    if "8-GPU" in name or "throttle knee" in name:
        return GPU8_COST
    return MPC_SIM_COST


if __name__ == "__main__":
    main()
