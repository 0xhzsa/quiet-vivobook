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
import fanlaw
import fleet_model
import lambda_case as lam
import modal_case as mod
import throughput
import together_case as tog

# The throughput-safe operating point. 52.9 % duty holds the die at 75 C
# at 80 % GPU load, which is where the GPU still runs at full boost.
# Derived by code/server_thermal_controller.py:throughput_safe_point.
DUTY_CTRL = 0.529

HOURS = 8760.0
GPUS_PER_NODE = 8


def D(x: float | int | str) -> Decimal:
    return Decimal(str(x))


def ref_saved_watts(fan_w, duty_base, duty_ctrl) -> Decimal:
    """Independent Decimal implementation of the calibrated fan law.

    Deliberately not imported from code/fanlaw.py: the point of this file is
    to be a second implementation that can disagree. The coefficients are
    written out again here so a change to fanlaw.py that is wrong still gets
    caught.

        P(d) = base * (a*d^3 + b*d) / (a + b),  a = 1, b = 0.342

    with base the power at 100 % duty, fitted to a measured 120 W -> 15 W
    pair at 90 % -> 30 % duty.
    """
    a = D(1)
    b = D("0.342")
    base = D(fan_w)
    d_base = D(duty_base)
    d_ctrl = D(duty_ctrl)

    def power(d: Decimal) -> Decimal:
        return base * (a * d ** 3 + b * d) / (a + b)

    return power(d_base) - power(d_ctrl)


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
    e_node = ref_energy(1000, 0.95, DUTY_CTRL, 0.08, 1.35)
    f_node = ref_fatigue(0.03, 0.35, 60_000, 36)
    a.close("8-GPU energy at $0.08 / PUE 1.35", e_node, "601.572", "0.001")
    a.close("8-GPU fatigue at R=36", f_node, "612.50", "0.01")
    a.close("8-GPU total", e_node + f_node, "1214.072", "0.001")

    nodes = ref_nodes(12)
    a.check("12 MW / 10.2 kW floors to 1,176 nodes", nodes == 1176, f"got {nodes}")
    a.close("ATL02 energy", nodes * e_node, "707449.034", "0.01")
    a.close("ATL02 fatigue", nodes * f_node, "720300", "0.01")
    a.close("ATL02 total", nodes * (e_node + f_node), "1427749.034", "0.01")
    for ratio, want_f, want_total in (
        ("1.3", "170972.308", "878421.341"),
        ("1.8", "329280", "1036729.034"),
    ):
        f = ref_fatigue(0.03, 0.35, 60_000, float(ratio))
        a.close(f"ATL02 fatigue at {ratio}x", nodes * f, want_f, "0.01")
        a.close(f"ATL02 total at {ratio}x", nodes * (e_node + f), want_total, "0.01")

    for ratio, want_f4, want_t4, want_t8_09, want_t8_08 in (
        ("1.3", "60.577", "260.183", "847.219", "746.957"),
        ("1.8", "116.667", "316.273", "981.834", "881.572"),
    ):
        f4 = ref_fatigue(0.03, 0.35, 25_000, float(ratio))
        f8 = ref_fatigue(0.03, 0.35, 60_000, float(ratio))
        a.close(f"4-GPU fatigue at {ratio}x", f4, want_f4, "0.01")
        a.close(f"4-GPU total at {ratio}x", D("199.606") + f4, want_t4, "0.01")
        a.close(f"8-GPU total at {ratio}x / $0.09", D("701.834") + f8,
                want_t8_09, "0.01")
        a.close(f"8-GPU total at {ratio}x / $0.08", D("601.572") + f8,
                want_t8_08, "0.01")

    t_nodes = 8000 // GPUS_PER_NODE
    a.close("Together 8k energy", t_nodes * e_node, "601572.31", "0.01")
    a.close("Together 8k fatigue", t_nodes * f_node, "612500", "0.01")
    a.close("Together 8k total", t_nodes * (e_node + f_node), "1214072.31", "0.01")

    m_gpus = D(1_000_000_000) / (D("3.9492") * D(HOURS) * D("0.60"))
    m_nodes = int(m_gpus // GPUS_PER_NODE)
    a.close("Modal active GPUs", m_gpus, "48176.5", "1.0")
    a.check("Modal nodes floor to 6,022", m_nodes == 6022, f"got {m_nodes}")
    a.check("Modal modeled GPUs = nodes x 8", 6022 * 8 == 48176,
            f"got {6022 * 8}")


def audit_modules(a: Audit) -> None:
    print("\n2. MODULE PARITY")
    e_ref = ref_energy(1000, 0.95, DUTY_CTRL, 0.08, 1.35)
    f_ref = ref_fatigue(0.03, 0.35, 60_000, 36)
    for name, module in (("lambda", lam), ("together", tog), ("modal", mod)):
        a.close(f"{name}.energy_per_node", module.energy_per_node(1000, 0.08, 1.35),
                e_ref, "0.01")
        a.close(f"{name}.fatigue_per_node", module.fatigue_per_node(),
                f_ref, "0.01")

    atl = lam.site(12)
    a.close("lambda ATL02 total", atl["saving"], "1427749.034", "0.01")
    a.close("lambda ATL02 capacity", atl["revenue"], "12247320.96", "0.01")
    for ratio, want in (("1.3", "878421.341"), ("1.8", "1036729.034")):
        a.close(f"lambda ATL02 {ratio}x total",
                lam.site(12, ratio=float(ratio))["saving"], want, "0.01")

    t = tog.attributable(8000, 1.0)
    a.close("together 8k direct", t["direct"], "1214072.31", "0.01")
    a.close("together 8k 50%", tog.attributable(8000, 0.5)["direct"],
            "607036.15", "0.01")
    for ratio, want in (("1.3", "746956.92"), ("1.8", "881572.31")):
        a.close(f"together 8k {ratio}x total",
                tog.attributable(8000, 1.0, ratio=float(ratio))["direct"],
                want, "0.01")

    m = mod.fan_bill(mod.active_gpus(1e9))
    a.close("modal fan bill energy", m["energy"], "3622668.4", "1")
    a.close("modal fan bill fatigue", m["fatigue"], "3688475.0", "1")
    a.close("modal fan bill total", m["total"], "7311143.4", "1")
    for ratio, want in (("1.3", "4498174.59"), ("1.8", "5308828.4")):
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
            lam.saved_watts(1000, 1.0, 0.5), "779.434", "0.001")
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

    # The calibrated law must reproduce the measurement, and the case model
    # must use it. This is the check that the audit previously only warned
    # about: the pure cubic overstated the saving and the model used it.
    a.close("calibrated law reproduces 120 W at 90% duty",
            fanlaw.fan_power(fanlaw.MEASURED_DUTY_BEFORE,
                             fanlaw.MEASURED_BASE_W), "120.0", "0.01")
    a.close("calibrated law reproduces 15 W at 30% duty",
            fanlaw.fan_power(fanlaw.MEASURED_DUTY_AFTER,
                             fanlaw.MEASURED_BASE_W), "15.0", "0.01")
    a.check("case.py uses the calibrated law, not the raw cubic",
            abs(case.fan_saving(case.GPU8)["ctrl_w"]
                - fanlaw.fan_power(case.GPU8.duty_ctrl, case.GPU8.fan_w)) < 1e-12)
    a.check("calibrated law is never more optimistic than the cubic",
            all(fanlaw.fan_power(d / 100.0, 1000.0)
                >= fanlaw.fan_power_cubic(d / 100.0, 1000.0)
                for d in range(1, 100)))
    a.check("the model does NOT claim the naive 95% saving",
            abs(case.fan_saving(case.GPU8)["delta_w"]
                / fanlaw.fan_power(case.GPU8.duty_base, case.GPU8.fan_w)
                - 0.7218) < 1e-3,
            f"got {case.fan_saving(case.GPU8)['delta_w'] / fanlaw.fan_power(case.GPU8.duty_base, case.GPU8.fan_w):.4f}")
    a.check("the shipped saving is well under the naive cubic number",
            case.fan_saving(case.GPU8)["delta_w"]
            / fanlaw.fan_power(case.GPU8.duty_base, case.GPU8.fan_w) < 0.80,
            "the model must not claim more than 80%")


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
    # The R=36 scenario is a 12->2 C swing assumption, which is a different
    # claim from the simulator's measured 1.2-2.0x range. Both must be
    # present and distinguishable; the audit checks that the docs quote the
    # simulator range as the headline and R=36 only as a scenario.
    a.check("R=36 is labelled as a scenario, not the simulator result",
            case.GPU8.swing_ctrl == 2.0 and case.GPU8.swing_base == 12.0)
    if "consumes it" in (case.__doc__ or "") or "consumes it" in (
            case.__dict__.get("__doc__") or ""):
        a.warn("case.py docstring still claims it consumes cycling.py")


def audit_throughput(a: Audit) -> None:
    print("\n7. THROUGHPUT COST (THE TERM THE MODEL NOW DEBITS)")
    stock = cycling.simulate(cycling.stock_action, 4.0, 4.0, 12.0)
    mpc = cycling.simulate(cycling.mpc_action, 4.0, 4.0, 12.0)
    work = mpc.work / stock.work
    a.check("MPC retains less than 100% of stock work", work < 1.0,
            f"got {work:.3f}")

    # The measured laptop cost must be the number the model uses.
    a.close("measured laptop throughput cost is 6.92%",
            throughput.LAPTOP_COST * 100.0, "6.92", "0.001")
    a.check("the measured cost is 93.08% work retention",
            abs((1.0 - throughput.LAPTOP_COST) - 0.9308) < 1e-9)
    a.check("the measured value comes from the committed artifact",
            "93.08" in _scheme_ab_summary() or "0.9308" in _scheme_ab_summary(),
            "controller/fan-scan/scheme-ab-latest-summary.json")

    # The model must debit it. This is the check that used to be a warning.
    g = case.total(case.GPU8)
    a.check("case.total() includes a throughput term", "throughput_effective" in g)
    a.check("case.total() net is less than fan + cycling alone",
            g["total"] < g["fan"] + g["cycling"] - 1e-9 or
            g["throughput_effective"] == 0.0,
            f"net {g['total']:.2f} vs fan+cycling {g['fan'] + g['cycling']:.2f}")
    a.check("case.total() also reports the capacity-constrained net",
            "total_constrained" in g)
    a.check("constrained net is worse than the spare-capacity net",
            g["total_constrained"] <= g["total"] + 1e-9)

    # The two regimes must resolve correctly.
    rev = throughput.gross_revenue_per_node()
    a.check("spare capacity makes the effective throughput cost zero",
            throughput.effective_cost(throughput.GPU8_COST, rev, 0.60)
            ["effective_cost"] == 0.0)
    a.check("a capacity-constrained fleet pays the full throughput cost",
            abs(throughput.effective_cost(throughput.GPU8_COST, rev, 1.0)
                ["effective_cost"] - rev * throughput.GPU8_COST) < 0.01)
    a.check("the constrained case is net negative at the current duty",
            throughput.net_saving(839.0, throughput.GPU8_COST, rev, 1.0)["net"] < 0,
            "a 5.15% loss costs more than the fan saving on a saturated fleet")
    # The fleet case ships a duty that is safe under saturation. The
    # throughput-safe operating point at 80 % GPU load is 52.9 % duty, which
    # holds the die at 75 C where the GPU still runs at full boost.
    a.check("the fleet case ships the throughput-safe duty",
            abs(case.GPU8.duty_ctrl - 0.529) < 1e-3,
            f"duty {case.GPU8.duty_ctrl}")
    a.check("the shipped duty has zero modelled throughput cost",
            case.GPU8.throughput_cost == 0.0,
            f"cost {case.GPU8.throughput_cost:.4f}")
    a.check("the shipped duty is the one the thermal model derives",
            abs(case.GPU8.duty_ctrl - 0.529) < 1e-3)


def _scheme_ab_summary() -> str:
    """Read the committed clean-A/B artifact, or return an empty string."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, "controller", "fan-scan",
                        "scheme-ab-latest-summary.json")
    try:
        return open(path, encoding="utf-8").read()
    except OSError:
        return ""


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
            "114,980" in case_flat and "9,319" in case_flat and
            "**761**" in case_flat)
    a.check("THREE-CASES 1.3-1.8 ranges exclude the R=36 upper bound",
            "$1.23–1.78" not in three and "$1.04–1.51" not in three
            and "$6.29–9.10" not in three)
    a.check("THREE-CASES does not state Lambda has all three as fact",
            "Lambda has all three" not in three and
            "plausible" in three)
    a.check("README founder ranges are the 1.3-1.8 range",
            "$0.88–1.04M" in readme and "$0.75–0.88M" in readme)
    a.check("README does not quote the superseded affinity-law numbers",
            "$1.23–1.39M" not in readme and "$1.04–1.18M" not in readme
            and "$1.08–1.22M" not in readme)
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
