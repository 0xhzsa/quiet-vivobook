#!/usr/bin/env python3
"""
thermal_model.py - the 8-GPU node's thermal behaviour, with its uncertainty.

This is separated from server_thermal_controller.py so that the fleet models
can IMPORT the operating point from it instead of hard-coding a number. The
previous version had the safe duty written as the literal 0.529 in four
files, and the audit asserted that the literal equalled itself. That is how a
model silently stops matching its own physics.

What is measured and what is assumed
------------------------------------
MEASURED, elsewhere:  120 W -> 15 W fan power on a 64-core Ampere server
                      (@0xAlcibiades, quiet-lab, MIT). This is the only fan
                      measurement in the project.

ASSUMED HERE:        1 kW fan tray on a dense 8x700W node. No source. It
                      scales every dollar figure in the repository.
ASSUMED HERE:        die-to-heatsink, heatsink-to-air and case-to-ambient
                      thermal resistances. Chosen so a full-duty node sits at
                      a plausible die temperature. One anchor, three free
                      parameters, no residual.
ASSUMED HERE:        ambient 25 C, with no band. A real node sees 18-30 C
                      inlet and the answer moves a lot across that range.
ASSUMED HERE:        the throttle curve. THROTTLE_START_C is a number picked
                      for a plausible full-boost point, not a citation.

The honest output of this module is a BAND, not a point. `operating_point()`
returns one, and `operating_envelope()` returns the answer across ambient.

    uv run --no-project python code/thermal_model.py --selftest
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass

import fanlaw

# --- assumptions, all named -----------------------------------------------
FAN_TRAY_W = 1000.0            # ASSUMED. The biggest input in the repo.
GPU_TDP_W = 700.0              # public H100 SXM TDP
GPUS_PER_NODE = 8
AMBIENT_C = 25.0               # ASSUMED. See ambient_band().

# Full-boost die temperature: below this the GPU is not throttling.
# ASSUMED. See the module docstring; this number moves the headline a lot.
THROTTLE_START_C = 75.0
THROTTLE_FLOOR_C = 90.0
THROTTLE_FLOOR_FRACTION = 0.50

# The H100 thermal throttle point. This one is closer to a datasheet number
# than THROTTLE_START_C, but it is still a chosen threshold.
THROTTLE_KNEE_C = 83.0

# Inlet ambient band for a real air-cooled row: 18-30 C is the usual range.
AMBIENT_BAND_C = (18.0, 30.0)


@dataclass
class ThermalNode:
    name: str
    mass_kg: float
    c_p: float
    temp: float
    warning_temp: float
    critical_temp: float


@dataclass
class ServerThermalModel:
    """Lumped-parameter thermal model for an air-cooled server node.

    Three nodes in series, each with a real thermal mass, plus a case air path:

        GPU die  --(TIM)-->  heatsink  --(convection)-->  inlet  -->  ambient

    Calibrated so that a dense 8x700W node at 95 % fan duty and full GPU load
    holds a die temperature near 77 C, which is where an H100 sits under
    sustained load. Every other number in this file falls out of that single
    anchor.

    The convection term scales with airflow: the heat-transfer coefficient
    goes as duty^0.8, the usual correlation for forced convection over a fin
    array in the turbulent regime.

    The inlet is a real node with a real thermal mass and a conduction path to
    ambient, not an integrator. An integrator has no equilibrium: the exhaust
    heat accumulates without bound, the model never converges, and every
    "steady state" number taken from it is a fiction.
    """
    name: str
    n_gpus: int
    gpu_tdp_w: float
    fan_base_w: float
    ambient_temp: float
    r_die_hs: float = 0.0050    # die to heatsink (TIM + copper spreader)
    r_hs_air: float = 0.0028    # heatsink to air (fin array, 8 fans)
    r_air_amb: float = 0.0015   # case exhaust path to ambient
    die_mass: float = 2.0       # kg (die + cold plate)
    die_cp: float = 900.0
    hs_mass: float = 8.0        # kg (heatsink assembly)
    hs_cp: float = 900.0
    air_mass: float = 5.0       # kg (case air + chassis)
    air_cp: float = 1000.0
    die_temp: float = 25.0
    hs_temp: float = 25.0
    inlet_temp: float = 25.0
    dt: float = 1.0

    def step(self, fan_duty: float, gpu_power_w: float) -> dict:
        airflow = max(0.15, fan_duty)
        h = airflow ** 0.8

        # Only the convection path scales with airflow. The TIM and spreader
        # path does not, and neither does the case exhaust path: both are
        # fixed conduction, not forced convection over a fin array.
        r_dh = self.r_die_hs
        r_ha = self.r_hs_air / h

        # Die -> heatsink
        q_dh = (self.die_temp - self.hs_temp) / r_dh
        self.die_temp += (gpu_power_w - q_dh) * self.dt / (self.die_mass * self.die_cp)

        # Heatsink -> air
        q_ha = (self.hs_temp - self.inlet_temp) / r_ha
        self.hs_temp += (q_dh - q_ha) * self.dt / (self.hs_mass * self.hs_cp)

        # Case air: receives the exhaust heat, loses it to ambient
        q_amb = (self.inlet_temp - self.ambient_temp) / self.r_air_amb
        self.inlet_temp += (q_ha - q_amb) * self.dt / (self.air_mass * self.air_cp)

        return {
            "die_temp": round(self.die_temp, 2),
            "hs_temp": round(self.hs_temp, 2),
            "inlet_temp": round(self.inlet_temp, 2),
            "fan_duty": round(fan_duty, 3),
            "fan_power_w": round(fanlaw.fan_power(fan_duty, self.fan_base_w), 2),
            "gpu_power_w": round(gpu_power_w, 1),
        }

    def reset(self, ambient: float = None):
        if ambient is not None:
            self.ambient_temp = ambient
        self.die_temp = self.ambient_temp
        self.hs_temp = self.ambient_temp
        self.inlet_temp = self.ambient_temp


def make_gpu8(ambient: float = AMBIENT_C, fan_w: float = FAN_TRAY_W) -> ServerThermalModel:
    return ServerThermalModel(
        name="8-GPU dense (H100 class)", n_gpus=GPUS_PER_NODE, gpu_tdp_w=GPU_TDP_W,
        fan_base_w=fan_w, ambient_temp=ambient,
    )


def steady_state(node: ServerThermalModel, duty: float, gpu_power_w: float,
                 max_seconds: float = 3000.0, tol: float = 0.05,
                 verify: bool = True) -> dict:
    """Solve the thermal model to steady state, then verify by time domain.

    A fan controller is asked to hold a temperature forever, not for two
    minutes. Every duty point in this project must therefore be a steady
    state point: a 120 s run at low duty has not settled and reports a die
    temperature several degrees below the real one.

    At steady state every path carries the same power P, because the only
    source is the GPU and the only sink is ambient. The three resistances are
    in series:

        die - hs     = P * r_die_hs
        hs  - inlet  = P * r_hs_air / h
        inlet - amb  = P * r_air_amb

    with h = duty^0.8 scaling only the convection path.
    """
    airflow = max(0.15, duty)
    h = airflow ** 0.8
    p = gpu_power_w

    inlet_ss = node.ambient_temp + p * node.r_air_amb
    hs_ss = inlet_ss + p * node.r_hs_air / h
    die_ss = hs_ss + p * node.r_die_hs

    drift = 0.0
    if verify:
        probe = ServerThermalModel(
            name=node.name, n_gpus=node.n_gpus, gpu_tdp_w=node.gpu_tdp_w,
            fan_base_w=node.fan_base_w, ambient_temp=node.ambient_temp,
            r_die_hs=node.r_die_hs, r_hs_air=node.r_hs_air,
            r_air_amb=node.r_air_amb,
            die_mass=node.die_mass, die_cp=node.die_cp,
            hs_mass=node.hs_mass, hs_cp=node.hs_cp,
            air_mass=node.air_mass, air_cp=node.air_cp, dt=node.dt)
        probe.reset(node.ambient_temp)
        temps = []
        for _ in range(int(max_seconds)):
            s = probe.step(duty, p)
            temps.append(s["die_temp"])
        drift = abs(temps[-1] - temps[int(len(temps) * 0.8)])

    return {
        "duty": duty,
        "die_temp": round(die_ss, 2),
        "hs_temp": round(hs_ss, 2),
        "inlet_temp": round(inlet_ss, 2),
        "drift_over_last_20pct": round(drift, 4),
        "converged": drift < tol,
        "fan_power_w": round(fanlaw.fan_power(duty, node.fan_base_w), 2),
        "h_ratio": round(h, 4),
    }


def min_duty_for_temp(node: ServerThermalModel, gpu_power_w: float,
                      max_die_temp: float) -> dict:
    """Lowest fan duty that holds the die at or below a target temperature.

    This is the number a fleet operator actually needs. It is not the duty
    that maximizes the fan saving; it is the duty that is actually safe.
    """
    best = steady_state(node, 1.0, gpu_power_w, verify=False)
    if best["die_temp"] > max_die_temp:
        # Even at full speed the target cannot be held. The node needs a
        # bigger tray, less GPU load, or liquid. That is a real finding, not
        # a solver failure, so it is reported rather than silently clamped.
        best["feasible"] = False
        return best
    lo, hi = 0.15, 1.0
    for _ in range(30):
        mid = (lo + hi) / 2.0
        r = steady_state(node, mid, gpu_power_w, verify=False)
        if r["die_temp"] <= max_die_temp:
            best = r
            hi = mid
        else:
            lo = mid
    best["feasible"] = True
    return best


def throttle_work(die_temp: float) -> float:
    """Fraction of peak throughput a GPU delivers at a given die temperature.

    ASSUMED CURVE. Full boost to THROTTLE_START_C, then a linear decline
    through the throttle band, with a floor around half of peak clock.

    This is the term that turns a fan saving into a throughput cost, and the
    thresholds are chosen rather than cited. It is exposed so the assumption
    is visible, and `sensitivity()` in the audit shows what it does to the
    headline.
    """
    if die_temp <= THROTTLE_START_C:
        return 1.0
    if die_temp >= THROTTLE_FLOOR_C:
        return THROTTLE_FLOOR_FRACTION
    span = THROTTLE_FLOOR_C - THROTTLE_START_C
    frac = (die_temp - THROTTLE_START_C) / span
    return 1.0 - frac * (1.0 - THROTTLE_FLOOR_FRACTION)


def operating_point(node: ServerThermalModel, gpu_power_w: float,
                    max_die_temp: float = THROTTLE_START_C) -> dict:
    """The duty that holds a temperature, and what it is worth.

    This is the number a fleet operator needs, and it is not a constant. The
    minimum safe duty depends on GPU load and on inlet temperature, so the
    fan saving is a function of the environment, not a property of the tray.
    """
    r = min_duty_for_temp(node, gpu_power_w, max_die_temp)
    duty = r["duty"]
    base_duty = 0.95
    base_w = fanlaw.fan_power(base_duty, node.fan_base_w)
    ctrl_w = fanlaw.fan_power(duty, node.fan_base_w)
    saved_w = base_w - ctrl_w
    work = throttle_work(r["die_temp"])
    band = fanlaw.saving_band(base_duty, min(duty, base_duty))
    return {
        "gpu_power_w": gpu_power_w,
        "max_die_temp": max_die_temp,
        "feasible": r.get("feasible", True),
        "min_duty": duty,
        "die_temp": r["die_temp"],
        "hs_temp": r["hs_temp"],
        "inlet_temp": r["inlet_temp"],
        "base_duty": base_duty,
        "base_fan_w": base_w,
        "ctrl_fan_w": ctrl_w,
        "saved_w": saved_w,
        "saved_pct": 100.0 * saved_w / base_w if base_w else 0.0,
        "saved_pct_band": (100.0 * band.low, 100.0 * band.high),
        "work_fraction": work,
        "throughput_cost": 1.0 - work,
    }


def throughput_safe_point(node: ServerThermalModel, gpu_power_w: float,
                          max_die_temp: float = THROTTLE_START_C) -> dict:
    """The duty that holds full boost with zero throughput loss.

    Targeting the throttle knee maximizes the fan saving and destroys
    throughput. A real deployment has to pick the other end of the trade:
    hold the die at or below the point where the GPU still runs at full
    boost, and take whatever fan saving that allows.

    This is the number an operator should ship, and it is much smaller than
    the headline saving. Reporting only the knee number is how a fan
    controller becomes a revenue-loss project.
    """
    r = min_duty_for_temp(node, gpu_power_w, max_die_temp)
    base_w = fanlaw.fan_power(0.95, node.fan_base_w)
    ctrl_w = fanlaw.fan_power(r["duty"], node.fan_base_w)
    saved_w = base_w - ctrl_w
    band = fanlaw.saving_band(0.95, min(r["duty"], 0.95))
    return {
        "gpu_power_w": gpu_power_w,
        "max_die_temp": max_die_temp,
        "min_duty": r["duty"],
        "die_temp": r["die_temp"],
        "base_fan_w": base_w,
        "ctrl_fan_w": ctrl_w,
        "saved_w": saved_w,
        "saved_pct": 100.0 * saved_w / base_w if base_w else 0.0,
        "saved_pct_band": (100.0 * band.low, 100.0 * band.high),
        "throughput_cost": 1.0 - throttle_work(r["die_temp"]),
        "feasible": r.get("feasible", True),
    }


def operating_envelope(ambient_band=AMBIENT_BAND_C,
                       load_band=(0.6, 1.0)) -> dict:
    """The answer across inlet temperature and GPU load.

    This is the honest shape of the result. At 30 C inlet the node can only
    give back about 44 % of its fan power; at 18 C it gives back 85 %. A
    single number without this table is a number without a meaning.
    """
    out = {"ambient_band_c": ambient_band, "load_band": load_band, "points": []}
    for ambient in (18.0, 21.0, 24.0, 27.0, 30.0):
        for load in (0.6, 0.8, 1.0):
            node = make_gpu8(ambient=ambient)
            p = node.n_gpus * node.gpu_tdp_w * load
            r = operating_point(node, p)
            out["points"].append({
                "ambient_c": ambient,
                "load": load,
                "gpu_power_w": p,
                "min_duty": r["min_duty"],
                "die_temp": r["die_temp"],
                "saved_pct": r["saved_pct"],
                "saved_pct_band": r["saved_pct_band"],
                "feasible": r["feasible"],
            })
    return out


def shipped_duty(load: float = 0.8, ambient: float = AMBIENT_C,
                 fan_w: float = FAN_TRAY_W) -> float:
    """The duty the fleet models should use.

    Derived, not hard-coded. The fleet modules import this so that a change
    to the thermal model moves the fleet numbers with it.
    """
    node = make_gpu8(ambient=ambient, fan_w=fan_w)
    p = node.n_gpus * node.gpu_tdp_w * load
    return throughput_safe_point(node, p)["min_duty"]


def selftest() -> int:
    ok = 0

    def check(name: str, cond: bool, detail: str = "") -> None:
        nonlocal ok
        if not cond:
            print("  FAIL  %s  %s" % (name, detail))
            raise SystemExit(1)
        ok += 1
        print("  pass  %s" % name)

    node = make_gpu8()
    p = node.n_gpus * node.gpu_tdp_w * 0.8

    # 1. The model converges. A model that never settles cannot produce a
    #    steady-state duty point.
    r = steady_state(node, 0.35, p)
    check("thermal model converges at steady state", r["converged"],
          "drift %.3f" % r["drift_over_last_20pct"])

    # 2. The closed form agrees with the time domain.
    probe = make_gpu8()
    probe.reset(node.ambient_temp)
    for _ in range(3000):
        probe.step(0.35, p)
    check("closed form matches the time-domain model",
          abs(probe.die_temp - r["die_temp"]) < 1.0,
          "closed %.2f vs time %.2f" % (r["die_temp"], probe.die_temp))

    # 3. Monotonicity.
    temps = [steady_state(node, d, p, verify=False)["die_temp"]
             for d in (0.35, 0.5, 0.65, 0.8, 0.95)]
    check("die temperature falls monotonically with duty",
          all(temps[i] > temps[i + 1] for i in range(len(temps) - 1)),
          str(temps))

    # 4. The safe duty must rise with GPU load.
    duties = [operating_point(make_gpu8(), node.n_gpus * node.gpu_tdp_w * load)["min_duty"]
              for load in (0.5, 0.7, 0.9)]
    check("minimum safe duty rises with GPU load",
          duties[0] < duties[1] < duties[2], str(duties))

    # 5. The safe duty must RISE with inlet temperature. This is the
    #    sensitivity that was missing from the shipped numbers.
    amb_duties = [operating_point(make_gpu8(ambient=a), p)["min_duty"]
                  for a in (18.0, 25.0, 30.0)]
    check("minimum safe duty rises with inlet temperature",
          amb_duties[0] < amb_duties[1] < amb_duties[2], str(amb_duties))

    # 6. The band must be reported and must be wide.
    op = operating_point(node, p)
    lo, hi = op["saved_pct_band"]
    check("the operating point reports a saving band", hi > lo)
    check("the saving band is wider than 5 points", (hi - lo) > 5.0,
          "band %.2f wide" % (hi - lo))
    check("the point estimate lies inside the band",
          lo <= op["saved_pct"] <= hi,
          "point %.2f band [%.2f, %.2f]" % (op["saved_pct"], lo, hi))

    # 7. The shipped duty is derived, and matches the thermal solve.
    sd = shipped_duty(0.8)
    check("shipped_duty matches the thermal solve",
          abs(sd - throughput_safe_point(node, p)["min_duty"]) < 1e-9)
    check("the shipped duty is not a magic constant",
          0.40 < sd < 0.70, "got %.4f" % sd)

    # 8. The two operating points are ordered correctly.
    knee = operating_point(node, p, THROTTLE_KNEE_C)
    safe = throughput_safe_point(node, p)
    check("the knee duty is lower than the throughput-safe duty",
          knee["min_duty"] < safe["min_duty"])
    check("the knee saves more fan power than the safe point",
          knee["saved_pct"] > safe["saved_pct"])
    check("the knee costs more throughput than the safe point",
          knee["throughput_cost"] > safe["throughput_cost"])
    check("the throughput-safe point costs no throughput",
          abs(safe["throughput_cost"]) < 1e-12,
          "got %.6f" % safe["throughput_cost"])

    # 9. The throttle curve is monotonic and bounded.
    check("throttle curve is 1.0 at or below the start threshold",
          throttle_work(70.0) == 1.0 and throttle_work(THROTTLE_START_C) == 1.0)
    check("throttle curve reaches the floor at 90 C",
          abs(throttle_work(90.0) - THROTTLE_FLOOR_FRACTION) < 1e-9)
    check("throttle curve is monotonically decreasing",
          all(throttle_work(t) >= throttle_work(t + 1)
              for t in range(int(THROTTLE_START_C), 90)))

    # 10. The envelope must show a wide spread. If it does not, the
    #     sensitivity analysis is broken.
    env = operating_envelope()
    saved = [pt["saved_pct"] for pt in env["points"]]
    check("the envelope spans more than 30 points of fan saving",
          max(saved) - min(saved) > 30.0,
          "spread %.1f" % (max(saved) - min(saved)))
    check("some envelope points are infeasible at full duty",
          any(not pt["feasible"] for pt in env["points"]))

    print("\n%d checks passed" % ok)
    return ok


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--load", type=float, default=0.8)
    ap.add_argument("--ambient", type=float, default=AMBIENT_C)
    args = ap.parse_args()

    if args.selftest:
        selftest()
        return

    print("=" * 78)
    print("8-GPU NODE - the answer, and how much it depends on the assumptions")
    print("=" * 78)
    print("fan tray      %.0f W  (ASSUMED, no source)" % FAN_TRAY_W)
    print("GPU           %d x %d W" % (GPUS_PER_NODE, GPU_TDP_W))
    print("throttle      full boost to %.0f C (ASSUMED threshold)" % THROTTLE_START_C)
    print()

    env = operating_envelope()
    print("  %-8s %-7s %-10s %-8s %-14s %s" %
          ("ambient", "load", "min_duty", "die_C", "fan_saved", "band"))
    print("  " + "-" * 72)
    for pt in env["points"]:
        if pt["load"] != 0.8:
            continue
        lo, hi = pt["saved_pct_band"]
        print("  %-8.0fC %-7.0f%% %-10.1f%% %-8.1f %6.1f%%%-10s %.1f-%.1f%%" %
              (pt["ambient_c"], 100 * pt["load"], 100 * pt["min_duty"],
               pt["die_temp"], pt["saved_pct"], "", lo, hi))
    print()
    lo80 = min(pt["saved_pct"] for pt in env["points"] if pt["load"] == 0.8)
    hi80 = max(pt["saved_pct"] for pt in env["points"] if pt["load"] == 0.8)
    print("  At 80 %% GPU load the saving runs from %.1f %% to %.1f %% across a" % (lo80, hi80))
    print("  realistic inlet range, before the fan-law band is even applied.")
    print()
    op = operating_point(make_gpu8(ambient=args.ambient),
                         GPUS_PER_NODE * GPU_TDP_W * args.load)
    lo, hi = op["saved_pct_band"]
    print("  At %.0f C ambient, %.0f %% GPU load:" % (args.ambient, 100 * args.load))
    print("    duty            %.1f %%" % (100 * op["min_duty"]))
    print("    die temp        %.1f C" % op["die_temp"])
    print("    fan saved       %.1f W = %.1f %% (band %.1f-%.1f %%)" %
          (op["saved_w"], op["saved_pct"], lo, hi))
    print("    throughput cost %.2f %%" % (100 * op["throughput_cost"]))
    print()
    print("  Two independent bands multiply: the fan law's duty-midpoint")
    print("  uncertainty and the inlet temperature. Quote the combined range")


if __name__ == "__main__":
    main()
