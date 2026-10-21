#!/usr/bin/env python3
"""
Independent audit of the quiet-vivobook arithmetic.

This is deliberately not another snapshot test. It recomputes the headline
numbers from first principles in Decimal, then checks the modules against the
reference. It also checks the claims the modules cannot prove:

  * does the "quiet-lab published" case reproduce the upstream 120 W -> 15 W
    measurement, or does it reproduce an ideal cubic extrapolation?
  * does case.py consume cycling.py, or does it use a different fatigue model?
  * does the controller retain throughput while it saves fan power?

Hard arithmetic failures exit 1. Provenance failures are warnings unless
--strict is passed, because they are claims about the model, not float errors.

    uv run --no-project python code/audit.py
    uv run --no-project python code/audit.py --strict
"""
from __future__ import annotations

import argparse
import os
import sys
from decimal import Decimal, getcontext

getcontext().prec = 40

import case
import cycling
import fleet_model
import lambda_case as lam
import modal_case as mod
import together_case as tog

HOURS = 8760.0
GPUS_PER_NODE = 8


def D(x: float | int | str) -> Decimal:
    return Decimal(str(x))


def ref_saved_watts(fan_w, duty_base, duty_ctrl) -> Decimal:
    return D(fan_w) * (D(1) - (D(duty_ctrl) / D(duty_base)) ** 3)


def ref_energy(fan_w, duty_base, duty_ctrl, tariff, pue, hours=HOURS) -> Decimal:
    return ref_saved_watts(fan_w, duty_base, duty_ctrl) * D(hours) / D(1000) * D(tariff) * D(pue)


def ref_fatigue(afr, share, replacement, ratio) -> Decimal:
    if ratio <= 0:
        raise ValueError("ratio must be positive")
    return D(afr) * D(share) * (D(1) - D(1) / D(ratio)) * D(replacement)


def ref_nodes(mw, node_kw=10.2) -> int:
    return int(D(mw) * D(1000) / D(node_kw))


class Audit:
    def __init__(self) -> None:
        self.failures = 0
        self.warnings = 0

    def check(self, name: str, cond: bool, detail: str = "") -> None:
        if cond:
            print(f"  pass  {name}")
        else:
            self.failures += 1
            print(f"  FAIL  {name}" + (f"  {detail}" if detail else ""))

    def close(self, name: str, got, want, tolerance="0.01") -> None:
        ok = abs(D(got) - D(want)) <= D(tolerance)
        self.check(name, ok, f"got {got!r}, want {want!r} +/- {tolerance}")

    def warn(self, name: str, detail: str = "") -> None:
        self.warnings += 1
        print(f"  WARN  {name}" + (f"  {detail}" if detail else ""))


def raises(fn) -> bool:
    try:
        fn()
    except (ValueError, ZeroDivisionError):
        return True
    return False


def audit_reference(a: Audit) -> None:
    print("\n1. INDEPENDENT DECIMAL REFERENCE")
    e_node = ref_energy(1000, 0.95, 0.35, 0.08, 1.35)
    f_node = ref_fatigue(0.03, 0.35, 60_000, 36)
    a.close("8-GPU energy at $0.08 / PUE 1.35", e_node, "898.769", "0.001")
    a.close("8-GPU fatigue at R=36", f_node, "612.50", "0.01")
    a.close("8-GPU total", e_node + f_node, "1511.269", "0.001")

    nodes = ref_nodes(12)
    a.check("12 MW / 10.2 kW floors to 1,176 nodes", nodes == 1176, f"got {nodes}")
    a.close("ATL02 energy", nodes * e_node, "1056952.466", "0.01")
    a.close("ATL02 fatigue", nodes * f_node, "720300", "0.01")
    a.close("ATL02 total", nodes * (e_node + f_node), "1777252.466", "0.01")
    for ratio, want_f, want_total in (
        ("1.3", "170972.308", "1227924.773"),
        ("1.8", "329280", "1386232.466"),
    ):
        f = ref_fatigue(0.03, 0.35, 60_000, float(ratio))
        a.close(f"ATL02 fatigue at {ratio}x", nodes * f, want_f, "0.01")
        a.close(f"ATL02 total at {ratio}x", nodes * (e_node + f), want_total, "0.01")

    for ratio, want_f4, want_t4, want_t8_09, want_t8_08 in (
        ("1.3", "60.577", "476.117", "1193.945", "1044.154"),
        ("1.8", "116.667", "532.207", "1328.560", "1178.769"),
    ):
        f4 = ref_fatigue(0.03, 0.35, 25_000, float(ratio))
        f8 = ref_fatigue(0.03, 0.35, 60_000, float(ratio))
        a.close(f"4-GPU fatigue at {ratio}x", f4, want_f4, "0.01")
        a.close(f"4-GPU total at {ratio}x", D("415.54") + f4, want_t4, "0.01")
        a.close(f"8-GPU total at {ratio}x / $0.09", D("1048.56") + f8,
                want_t8_09, "0.01")
        a.close(f"8-GPU total at {ratio}x / $0.08", D("898.77") + f8,
                want_t8_08, "0.01")

    t_nodes = 8000 // GPUS_PER_NODE
    a.close("Together 8k energy", t_nodes * e_node, "898769.10", "0.01")
    a.close("Together 8k fatigue", t_nodes * f_node, "612500", "0.01")
    a.close("Together 8k total", t_nodes * (e_node + f_node), "1511269.10", "0.01")

    m_gpus = D(1_000_000_000) / (D("3.9492") * D(HOURS) * D("0.60"))
    m_nodes = int(m_gpus // GPUS_PER_NODE)
    a.close("Modal active GPUs", m_gpus, "48176.5", "1.0")
    a.check("Modal nodes floor to 6,022", m_nodes == 6022, f"got {m_nodes}")
    a.check("Modal modeled GPUs = nodes x 8", 6022 * 8 == 48176,
            f"got {6022 * 8}")


def audit_modules(a: Audit) -> None:
    print("\n2. MODULE PARITY")
    e_ref = ref_energy(1000, 0.95, 0.35, 0.08, 1.35)
    f_ref = ref_fatigue(0.03, 0.35, 60_000, 36)
    for name, module in (("lambda", lam), ("together", tog), ("modal", mod)):
        a.close(f"{name}.energy_per_node", module.energy_per_node(1000, 0.08, 1.35),
                e_ref, "0.01")
        a.close(f"{name}.fatigue_per_node", module.fatigue_per_node(),
                f_ref, "0.01")

    atl = lam.site(12)
    a.close("lambda ATL02 total", atl["saving"], "1777252.466", "0.01")
    a.close("lambda ATL02 capacity", atl["revenue"], "18287095.68", "0.01")
    for ratio, want in (("1.3", "1227924.773"), ("1.8", "1386232.466")):
        a.close(f"lambda ATL02 {ratio}x total",
                lam.site(12, ratio=float(ratio))["saving"], want, "0.01")

    t = tog.attributable(8000, 1.0)
    a.close("together 8k direct", t["direct"], "1511269.10", "0.01")
    a.close("together 8k 50%", tog.attributable(8000, 0.5)["direct"],
            "755634.55", "0.01")
    for ratio, want in (("1.3", "1044153.719"), ("1.8", "1178769.103")):
        a.close(f"together 8k {ratio}x total",
                tog.attributable(8000, 1.0, ratio=float(ratio))["direct"],
                want, "0.01")

    m = mod.fan_bill(mod.active_gpus(1e9))
    a.close("modal fan bill energy", m["energy"], "5412388.4", "1")
    a.close("modal fan bill fatigue", m["fatigue"], "3688475.0", "1")
    a.close("modal fan bill total", m["total"], "9100863.4", "1")
    for ratio, want in (("1.3", "6287894.554"), ("1.8", "7098548.4")):
        a.close(f"modal fan bill {ratio}x total",
                mod.fan_bill(mod.active_gpus(1e9), ratio=float(ratio))["total"],
                want, "1")

    a.close("case 1U CPU nodes", case.nodes_for(137.24), "7287", "0.01")
    a.close("case 8-GPU nodes", case.nodes_for(1661.06), "603", "0.01")
    a.check("case nodes_for rounds up to clear the target",
            case.nodes_for(137.24) * 137.24 >= 1_000_000)


def audit_scaling(a: Audit) -> None:
    print("\n3. SCALING AND INVARIANTS")
    base = lam.legs(8000)
    double = lam.legs(16000)
    a.close("Lambda direct saving doubles with GPUs", double["saving"],
            2 * base["saving"], "0.01")
    a.close("Lambda energy doubles with GPUs", double["energy"],
            2 * base["energy"], "0.01")

    a.check("saved watts are zero at equal duty",
            lam.saved_watts(1000, 0.95, 0.95) == 0.0)
    a.close("half duty leaves one eighth fan power",
            lam.saved_watts(1000, 1.0, 0.5), "875.0", "0.001")
    a.check("saved watts increase monotonically with duty cut",
            lam.saved_watts(1000, 0.95, 0.35) >
            lam.saved_watts(1000, 0.95, 0.60))

    a.check("capacity extra GPUs are a whole number of nodes",
            base["extra_gpus"] % 8 == 0)
    a.check("capacity extra GPUs do not exceed freed watts",
            base["extra_nodes"] * 10.2 * 1000 <= base["capacity_mw"] * 1e6)

    a.check("Together ownership sum is conserved",
            abs(tog.attributable(8000, 0.5)["direct"]
                + tog.attributable(8000, 0.5)["partner_direct"]
                - tog.legs(8000)["saving"]) < 0.01)

    a.check("Modal modeled GPUs are nodes x 8",
            mod.fan_bill(48176.5)["gpus"] == 48176)


def audit_invalid(a: Audit) -> None:
    print("\n4. INVALID INPUTS")
    cases = [
        ("lambda zero GPUs", lambda: lam.legs(0)),
        ("lambda negative GPUs", lambda: lam.legs(-8000)),
        ("lambda zero MW", lambda: lam.site(0)),
        ("lambda negative MW", lambda: lam.site(-12)),
        ("lambda negative tariff", lambda: lam.energy_per_node(tariff=-0.08)),
        ("lambda zero PUE", lambda: lam.energy_per_node(pue=0)),
        ("together negative tariff", lambda: tog.energy_per_node(tariff=-0.08)),
        ("modal negative tariff", lambda: mod.energy_per_node(tariff=-0.08)),
        ("case negative fan power", lambda: case.fan_saving(
            case.replace(case.GPU8, fan_w=-1))),
        ("case negative failure rate", lambda: case.fatigue_saving(
            case.replace(case.GPU8, afr=-0.03))),
    ]
    for name, fn in cases:
        a.check(name + " raises", raises(fn))


def audit_upstream(a: Audit) -> None:
    print("\n5. UPSTREAM PARITY (THE 120 W -> 15 W MEASUREMENT)")
    measured = fleet_model.per_node_saving(
        fleet_model.Case("upstream measured wattage", 120.0, 1.00, 0.50),
        0.09, 1.4, 8760)
    ideal = fleet_model.per_node_saving(
        fleet_model.Case("ideal 95->35", 120.0, 0.95, 0.35),
        0.09, 1.4, 8760)
    cubic30 = fleet_model.per_node_saving(
        fleet_model.Case("cubic at 30%", 120.0, 0.90, 0.30),
        0.09, 1.4, 8760)
    a.close("120 W -> 15 W back-solves to 50% cubic duty",
            measured["ctrl_w"], "15.0", "0.01")
    a.check("measured 120 W -> 15 W is an 87.5% cut",
            abs(measured["delta_w"] / 120.0 - 0.875) < 1e-9)
    a.close("cubic 90% -> 30% leaves 4.44 W", cubic30["ctrl_w"], "4.44", "0.01")
    a.check("the 30% cubic is NOT the measured 15 W result",
            abs(cubic30["ctrl_w"] - 15.0) > 1.0,
            f"cubic={cubic30['ctrl_w']:.2f} W, measured=15.0 W")
    a.warn("affinity law overstates the measured saving",
           f"ideal cubic 95->35 saves {ideal['delta_w']:.1f} W; upstream measured "
           f"{measured['delta_w']:.1f} W")


def audit_fatigue(a: Audit) -> None:
    print("\n6. FATIGUE PROVENANCE")
    stock = cycling.simulate(cycling.stock_action, 4.0, 4.0, 12.0)
    mpc = cycling.simulate(cycling.mpc_action, 4.0, 4.0, 12.0)
    ratio = stock.cm / mpc.cm
    a.check("cycle simulator runs", stock.cm > 0 and mpc.cm > 0)
    a.check("simulator damage reduction is 1.2-2.0x", 1.2 < ratio < 2.0,
            f"got {ratio:.3f}x")
    a.check("case.py uses R=36", case.life_ratio(case.GPU8) == 36.0,
            f"got {case.life_ratio(case.GPU8)}")
    if abs(case.life_ratio(case.GPU8) - ratio) > 5.0:
        a.warn("case.py R=36 is not the simulator's ratio",
               f"simulator {ratio:.2f}x, case {case.life_ratio(case.GPU8):.0f}x")
    if "consumes it" in (case.__doc__ or "") or "consumes it" in (
            case.__dict__.get("__doc__") or ""):
        a.warn("case.py docstring still claims it consumes cycling.py")


def audit_throughput(a: Audit) -> None:
    print("\n7. THROUGHPUT COST (THE TERM THE MODEL DOES NOT DEBIT)")
    stock = cycling.simulate(cycling.stock_action, 4.0, 4.0, 12.0)
    mpc = cycling.simulate(cycling.mpc_action, 4.0, 4.0, 12.0)
    work = mpc.work / stock.work
    a.check("MPC retains less than 100% of stock work", work < 1.0,
            f"got {work:.3f}")
    gross_node = 8 * 3.99 * 8760 * 0.60
    lost = gross_node * (1.0 - work)
    a.warn("throughput loss is not in the fan/fatigue model",
           f"MPC work {100 * work:.1f}%, gross revenue at risk "
           f"${lost:,.0f}/node/yr vs ~$1,511 saved")
    if lost > 1511.27:
        a.warn("throughput loss exceeds the modeled saving",
               f"${lost:,.0f} > $1,511")


def audit_docs(a: Audit) -> None:
    print("\n8. DOCUMENTATION CLAIMS")
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    readme = open(os.path.join(root, "README.md"), encoding="utf-8").read()
    modal = open(os.path.join(root, "MODAL-CASE.md"), encoding="utf-8").read()
    case_doc = open(os.path.join(root, "CASE-STUDY.md"), encoding="utf-8").read()
    three = open(os.path.join(root, "THREE-CASES.md"), encoding="utf-8").read()
    a.check("README no longer calls the Modal count an upper bound",
            "derived from ARR** — upper bound" not in readme)
    a.check("MODAL-CASE no longer calls the count an upper bound",
            "This is an upper bound" not in modal)
    case_flat = " ".join(case_doc.split())
    a.check("CASE-STUDY labels the fatigue dollar leg honestly",
            "R=36 is an assumption" in case_flat and
            "1.3–1.8× Coffin-Manson" in case_flat)
    a.check("CASE-STUDY separates client and server swing scenarios",
            "client row uses 5 %/yr failure rate" in case_flat and
            "20 % cycling" in case_flat and
            "18→12 °C (R=2.25)" in case_flat and
            "$7,500 for the 1U CPU node" in case_flat)
    a.check("CASE-STUDY node counts are ceilinged",
            "111,521" in case_flat and "7,287" in case_flat and
            "**603**" in case_flat)
    a.check("THREE-CASES 1.3-1.8 ranges exclude the R=36 upper bound",
            "$1.23–1.78" not in three and "$1.04–1.51" not in three
            and "$6.29–9.10" not in three)
    a.check("THREE-CASES does not state Lambda has all three as fact",
            "Lambda has all three" not in three and
            "plausible" in three)
    a.check("README founder ranges are the 1.3-1.8 range",
            "$1.23–1.39" in readme and "$1.04–1.18" in readme)
    a.check("Modal ARR share is split by scenario",
            "0.63–0.91" not in modal and "0.63–0.71" in modal)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--strict", action="store_true",
                    help="treat provenance warnings as failures")
    args = ap.parse_args()

    a = Audit()
    audit_reference(a)
    audit_modules(a)
    audit_scaling(a)
    audit_invalid(a)
    audit_upstream(a)
    audit_fatigue(a)
    audit_throughput(a)
    audit_docs(a)

    print(f"\n{a.failures} hard failure(s), {a.warnings} warning(s)")
    if a.failures:
        return 1
    if args.strict and a.warnings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
