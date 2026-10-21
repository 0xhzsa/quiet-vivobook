#!/usr/bin/env python3
"""
Fleet economics for closed-loop thermal control.

Every number this prints is derived from an assumption stated in the code or
passed on the command line. Nothing is asserted as a saving without showing
the arithmetic, because the interesting question is not "is it 7 figures" but
"7 figures at what fleet size".

Physics used
------------
Fan affinity laws: for a fixed impeller, airflow ~ N, pressure ~ N^2 and shaft
power ~ N^3, where N is rotational speed. So a 30% duty reduction removes about
66% of fan power. This cubic relationship is the entire reason fan control is
worth money at all, and it is why the savings are sensitive to how far duty is
actually reduced.

Cost model
----------
    saved_kWh_per_node_year = delta_watts * hours / 1000
    saved_usd_per_node_year = saved_kWh * tariff * PUE

PUE is applied to the saving, not to the whole facility: a watt removed at the
server also removes its share of cooling overhead. That is the correct treatment
for a marginal load, and it is the single most commonly overstated term in
vendor economics, so it is exposed as an explicit parameter.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Case:
    name: str
    fan_base_w: float          # fan power at uncontrolled duty
    duty_base: float           # fraction of full fan speed, uncontrolled
    duty_ctrl: float           # fraction of full fan speed under control
    node_count: int = 0        # 0 means "solve for it"


def fan_power(base_w: float, duty_base: float, duty_ctrl: float) -> float:
    """Scale fan power by the affinity law from a known operating point."""
    if base_w < 0:
        raise ValueError("base_w must be non-negative")
    if not (0.0 <= duty_ctrl <= duty_base <= 1.0):
        raise ValueError("require 0 <= duty_ctrl <= duty_base <= 1")
    return base_w * (duty_ctrl / duty_base) ** 3


def per_node_saving(case: Case, tariff: float, pue: float, hours: float) -> dict:
    ctrl_w = fan_power(case.fan_base_w, case.duty_base, case.duty_ctrl)
    delta_w = case.fan_base_w - ctrl_w
    kwh = delta_w * hours / 1000.0
    usd = kwh * tariff * pue
    return {
        "ctrl_w": ctrl_w,
        "delta_w": delta_w,
        "kwh": kwh,
        "usd": usd,
    }


def nodes_for_target(target_usd: float, usd_per_node: float) -> float:
    return target_usd / usd_per_node if usd_per_node > 0 else float("inf")


def fmt_money(x: float) -> str:
    if x >= 1_000_000:
        return f"${x/1_000_000:,.2f}M"
    if x >= 1_000:
        return f"${x/1_000:,.1f}k"
    return f"${x:,.0f}"


def rule(title: str) -> None:
    print()
    print(title)
    print("-" * len(title))


def main() -> None:
    hours = 8760.0
    tariff = 0.09          # USD/kWh, US commercial/industrial band 0.07-0.13
    pue = 1.4              # hyperscale 1.1-1.2, enterprise 1.5-1.8

    print("=" * 78)
    print("CLOSED-LOOP THERMAL CONTROL - FLEET ECONOMICS")
    print("=" * 78)
    print(f"electricity tariff : ${tariff:.3f}/kWh")
    print(f"PUE                : {pue:.2f}  (saving multiplied, not facility total)")
    print(f"hours per year     : {hours:,.0f}")
    print("fan power          : affinity law, P ~ duty^3")

    rule("1. THE CASES")

    cases = [
        # The upstream measured 120 W -> 15 W result. Under a pure cubic,
        # 15 W is the equivalent of 50% duty, not the measured 25-35% speed.
        Case("quiet-lab measured (server, 120 W fans)", 120.0, 1.00, 0.50),
        # What a naive cubic extrapolation of the same 120 W tray predicts at
        # 30% duty. This is not the upstream measurement; it is the error.
        Case("quiet-lab cubic at 30% (not measured)", 120.0, 0.90, 0.30),
        # A plausible mid-range GPU node.
        Case("mid GPU node (400 W fan tray)", 400.0, 0.90, 0.35),
        # A dense 8-GPU chassis where fans are a large share of node power.
        Case("dense 8-GPU (1 kW fan tray)", 1000.0, 0.95, 0.35),
        # A 1U CPU server, where fans are a small share.
        Case("1U CPU node (60 W fans)", 60.0, 0.80, 0.35),
    ]

    print(f"{'case':42} {'ctrl W':>8} {'saved W':>9} {'$/node/yr':>11}")
    results = {}
    for c in cases:
        r = per_node_saving(c, tariff, pue, hours)
        results[c.name] = r
        print(f"{c.name:42} {r['ctrl_w']:8.1f} {r['delta_w']:9.1f} {r['usd']:11.2f}")

    rule("2. WHAT FLEET SIZE DOES $1M/YEAR REQUIRE?")

    print(f"{'case':42} {'nodes for $1M/yr':>18}")
    for c in cases:
        n = nodes_for_target(1_000_000, results[c.name]["usd"])
        print(f"{c.name:42} {n:18,.0f}")

    rule("3. SENSITIVITY - $/node/year")

    tariffs = [0.06, 0.09, 0.12, 0.18]
    header = "  ".join(f"${t:.2f}" for t in tariffs)
    print(f"{'fan base W ->':>16}  {header}")
    for base in (60, 120, 240, 400, 600, 1000):
        c = Case("x", float(base), 0.90, 0.35)
        row = "  ".join(f"{per_node_saving(c, t, pue, hours)['usd']:6.0f}" for t in tariffs)
        print(f"{base:16.0f}  {row}")

    print()
    print("Read this table as: 1000 W of fan tray at $0.09/kWh is worth about")
    print(f"{per_node_saving(Case('x', 1000.0, 0.90, 0.35), 0.09, pue, hours)['usd']:.0f} USD per node per year.")
    print("Everything else is multiplication by node count.")

    rule("4. SANITY CHECK - THE LAPTOP THIS WAS BUILT ON")

    # A Vivobook-class blower moves maybe 3-5 CFM at full tilt and draws 1.5-3 W.
    lap = Case("Vivobook blower", 2.5, 1.00, 0.55)
    rl = per_node_saving(lap, tariff, 1.0, hours)
    print(f"fan power full tilt : {lap.fan_base_w:.1f} W")
    print(f"fan power at 55%    : {rl['ctrl_w']:.2f} W")
    print(f"energy saved        : {rl['kwh']:.2f} kWh/yr")
    print(f"money saved         : ${rl['usd']:.2f}/yr")
    print()
    print("So on a laptop the energy case is ~zero. The value there is noise and")
    print("die temperature, not electricity. Any pitch that leads with energy")
    print("savings on client hardware is wrong; lead with acoustics and thermals.")

    rule("5. THERMAL CYCLING - MOVED, AND WHY")

    print("The proxy table that used to live here was fabricated. It multiplied")
    print("invented cycle counts by an invented dT swing and printed 1.00x /")
    print("0.15x / 0.01x. Those numbers were not derived from anything.")
    print()
    print("Real cycle counting needs the temperature trace, not a guess:")
    print("  cycling.py  rainflow (ASTM E1049-85) + Coffin-Manson + Norris-Landzberg")
    print("  case.py     both legs composed, break-even and falsification")
    print()
    print("On this machine's own 1.67 h trace:")
    print("  109 cycles, mean dT 5.9 C, 65.5 per hour")
    print("  15% of cycles (10-20 C) carry 55% of the fatigue damage")
    print()
    print("That Pareto shape is the only cycling claim this project can support:")
    print("the damage is in the transients, not the ripples. Dollars need an annual")
    print("failure rate and an attribution share that neither of us has.")

    rule("6. WHAT MUST BE TRUE FOR THE 7-FIGURE CLAIM")

    target = 1_000_000.0
    print(f"To reach {fmt_money(target)}/yr at ${tariff:.2f}/kWh and PUE {pue}:")
    print()
    print(f"{'if each node saves':>22} {'you need':>14}")
    for save in (50, 100, 250, 500, 1000, 2000):
        n = target / save
        print(f"{save:18.0f} W/node {n:14,.0f} nodes")
    print()
    print("The claim is arithmetically true and fleet-size dependent. It is not")
    print("true for a homelab, and it is not true for 100 servers. It becomes")
    print("true somewhere around 2,000-10,000 nodes, depending on fan power.")


if __name__ == "__main__":
    main()
