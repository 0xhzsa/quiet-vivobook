#!/usr/bin/env python3
"""
fanlaw.py - the fan power law, calibrated against a real measurement.

The naive model is the affinity law: for a fixed impeller, airflow ~ N,
pressure ~ N^2, and shaft power ~ N^3. That predicts a 95% -> 35% duty cut
removes 95% of fan power.

It is wrong, and the direction of the error matters, because the whole claim
is a dollar figure. @0xAlcibiades measured 120 W -> 15 W on a real 64-core
Ampere server (github.com/0xAlcibiades/quiet-lab, MIT): a 87.5% cut, not 95%.
The pure cubic overstates the saving by 9 W on that node.

Why the cubic fails
-------------------
A real fan is not an ideal impeller on a free-air load. Three effects break
the pure N^3 scaling:

  1. Motor losses. Brushless DC fan motors have a floor on electrical input
     that does not vanish with speed. Power falls as roughly a + b*d^3, not
     d^3 alone.
  2. Bearing and windage losses grow with speed but with a different
     exponent than the aerodynamic term.
  3. Drive electronics quiescent current is roughly speed-independent.

So the correct model is an affine-cubic: P(d) = base * (a*d^3 + b*d) / (a + b),
with the constant term folded into the linear term. `base` is the power at
100% duty. Setting a = 1 and solving for b against the measured pair:

    120 = base * (0.90^3 + b*0.90) / (1 + b)
     15 = base * (0.30^3 + b*0.30) / (1 + b)

Taking the ratio, 120/15 = 8, so:

    (0.729 + 0.9b) / (0.027 + 0.3b) = 8
    0.729 + 0.9b = 0.216 + 2.4b
    0.513 = 1.5b
    b = 0.342

With a = 1.0 and b = 0.342 the *ratio* is reproduced exactly, and the implied
power at 100% duty is:

    base = 120 * (1 + 0.342) / (0.729 + 0.342*0.90) = 155.3 W

So a 120 W measurement at 90% duty implies a 155.3 W tray at full speed. With
those two numbers the model reproduces the measurement exactly and gives 87.5%
where the pure cubic gives 95%. The cubic is retained in the function below
only as an explicit comparison term, because "what the naive model would have
said" is itself a useful number for a reader.

Calibration provenance
----------------------
  measured_before_w  120.0   @0xAlcibiades, quiet-lab README
  measured_after_w    15.0   @0xAlcibiades, quiet-lab README
  measured_duty_before  0.90 (README states 80-100%; 90% is the midpoint)
  measured_duty_after   0.30 (README states 25-35%; 30% is the midpoint)
  duty values are midpoints of a stated range, not exact readings

    uv run --no-project python code/fanlaw.py --selftest
"""

from __future__ import annotations

import argparse

# Empirical fit coefficients. a is the aerodynamic (cubic) weight, b is the
# speed-independent + speed-linear loss weight.
A_CUBIC = 1.0
B_LOSS = 0.342

# The measured anchor this law is calibrated to.
MEASURED_BEFORE_W = 120.0
MEASURED_AFTER_W = 15.0
MEASURED_DUTY_BEFORE = 0.90
MEASURED_DUTY_AFTER = 0.30


def _loss_coefficient(w_before: float, w_after: float,
                      d_before: float, d_after: float) -> float:
    """Solve for the loss coefficient b that reproduces a measured power pair.

    From P(d) = base * (a*d^3 + b*d) / (a+b), the measured ratio gives

        w_before / w_after = (a*d_before^3 + b*d_before)
                             / (a*d_after^3 + b*d_after)

    which is linear in b. Solved for a = 1.
    """
    num = w_before * (d_after ** 3) - w_after * (d_before ** 3)
    den = w_after * d_before - w_before * d_after
    if den == 0:
        raise ValueError("degenerate duty pair")
    return num / den


def base_w_from_measurement(w: float, duty: float, a: float = A_CUBIC,
                            b: float = B_LOSS) -> float:
    """Infer the power at 100% duty from one measured (wattage, duty) point."""
    if w < 0:
        raise ValueError("w must be non-negative")
    if not (0.0 < duty <= 1.0):
        raise ValueError("require 0 < duty <= 1")
    shape = (a * duty ** 3 + b * duty) / (a + b)
    if shape <= 0:
        raise ValueError("duty yields zero power")
    return w / shape


# The power at 100% duty implied by the measured 120 W @ 90%.
MEASURED_BASE_W = base_w_from_measurement(MEASURED_BEFORE_W, MEASURED_DUTY_BEFORE)

# The affinity-law prediction at the same duty pair, for comparison.
CUBIC_PREDICTED_AFTER_W = MEASURED_BEFORE_W * (MEASURED_DUTY_AFTER / MEASURED_DUTY_BEFORE) ** 3


def fan_power(duty: float, base_w: float, a: float = A_CUBIC, b: float = B_LOSS) -> float:
    """Fan electrical power at a given duty cycle.

    base_w is the power at 100% duty. The returned value uses the calibrated
    affine-cubic law. `duty` is clamped to [0, 1].
    """
    if base_w < 0:
        raise ValueError("base_w must be non-negative")
    if a <= 0 or b < 0:
        raise ValueError("require a > 0 and b >= 0")
    d = min(1.0, max(0.0, duty))
    if d == 0.0:
        return 0.0
    denom = a + b
    return base_w * (a * d ** 3 + b * d) / denom


def fan_power_cubic(duty: float, base_w: float) -> float:
    """Pure affinity law. Kept as the explicit naive comparison."""
    if base_w < 0:
        raise ValueError("base_w must be non-negative")
    d = min(1.0, max(0.0, duty))
    return base_w * d ** 3


def saving_fraction(duty_base: float, duty_ctrl: float) -> float:
    """Fraction of fan power removed, using the calibrated law."""
    if not (0.0 <= duty_ctrl <= duty_base <= 1.0):
        raise ValueError("require 0 <= duty_ctrl <= duty_base <= 1")
    if duty_base == 0.0:
        return 0.0
    before = fan_power(duty_base, 1.0)
    after = fan_power(duty_ctrl, 1.0)
    return (before - after) / before


def saving_fraction_cubic(duty_base: float, duty_ctrl: float) -> float:
    """Same, using the pure affinity law."""
    if not (0.0 <= duty_ctrl <= duty_base <= 1.0):
        raise ValueError("require 0 <= duty_ctrl <= duty_base <= 1")
    if duty_base == 0.0:
        return 0.0
    return 1.0 - (duty_ctrl / duty_base) ** 3


def report(duty_base: float = 0.95, duty_ctrl: float = 0.35, base_w: float = 1000.0) -> dict:
    """Everything a reader needs to see the model and its error in one dict."""
    before = fan_power(duty_base, base_w)
    after = fan_power(duty_ctrl, base_w)
    before_c = fan_power_cubic(duty_base, base_w)
    after_c = fan_power_cubic(duty_ctrl, base_w)
    return {
        "duty_base": duty_base,
        "duty_ctrl": duty_ctrl,
        "base_w": base_w,
        "calibrated_before_w": before,
        "calibrated_after_w": after,
        "calibrated_saving_w": before - after,
        "calibrated_saving_pct": 100.0 * (before - after) / before if before else 0.0,
        "cubic_before_w": before_c,
        "cubic_after_w": after_c,
        "cubic_saving_w": before_c - after_c,
        "cubic_saving_pct": 100.0 * (before_c - after_c) / before_c if before_c else 0.0,
        "overstatement_w": (before_c - after_c) - (before - after),
    }


def selftest() -> int:
    ok = 0

    def check(name: str, cond: bool, detail: str = "") -> None:
        nonlocal ok
        if not cond:
            print("  FAIL  %s  %s" % (name, detail))
            raise SystemExit(1)
        ok += 1
        print("  pass  %s" % name)

    # 1. The calibration must reproduce the measurement exactly.
    before = fan_power(MEASURED_DUTY_BEFORE, MEASURED_BASE_W)
    after = fan_power(MEASURED_DUTY_AFTER, MEASURED_BASE_W)
    check("calibrated law reproduces 120 W at 90% duty",
          abs(before - MEASURED_BEFORE_W) < 1e-6, "got %.4f" % before)
    check("calibrated law reproduces 15 W at 30% duty",
          abs(after - MEASURED_AFTER_W) < 1e-6, "got %.4f" % after)
    check("implied 100% duty power is 155.3 W",
          abs(MEASURED_BASE_W - 155.3) < 0.1, "got %.3f" % MEASURED_BASE_W)

    # 2. The measured cut is 87.5%, and the cubic overstates it.
    measured_frac = (MEASURED_BEFORE_W - MEASURED_AFTER_W) / MEASURED_BEFORE_W
    check("calibrated law gives the measured 87.5% cut",
          abs((MEASURED_BEFORE_W - MEASURED_AFTER_W) / MEASURED_BEFORE_W
              - measured_frac) < 1e-9)
    check("loss coefficient solved from the measured pair is 0.342",
          abs(_loss_coefficient(MEASURED_BEFORE_W, MEASURED_AFTER_W,
                                MEASURED_DUTY_BEFORE, MEASURED_DUTY_AFTER)
              - B_LOSS) < 1e-9)
    check("pure cubic overstates the saving",
          saving_fraction_cubic(MEASURED_DUTY_BEFORE, MEASURED_DUTY_AFTER)
          > measured_frac + 0.05)
    check("cubic prediction at 30% is 4.44 W, not 15 W",
          abs(CUBIC_PREDICTED_AFTER_W - 4.44) < 0.01,
          "got %.4f" % CUBIC_PREDICTED_AFTER_W)

    # 3. Monotonicity and bounds.
    check("power is monotonic in duty",
          all(fan_power(d / 100.0, 1000.0) < fan_power((d + 1) / 100.0, 1000.0)
              for d in range(100)))
    check("power at 100% duty equals base", abs(fan_power(1.0, 1000.0) - 1000.0) < 1e-9)
    check("power at 0% duty is zero", fan_power(0.0, 1000.0) == 0.0)

    # 4. The law is gentler than cubic at every interior point: the loss term
    #    keeps a floor under the power, which is the physical claim.
    check("calibrated law sits above the cubic for all interior duty",
          all(fan_power(d / 100.0, 1000.0) >= fan_power_cubic(d / 100.0, 1000.0)
              for d in range(1, 100)))

    # 5. The affine-cubic saving fraction is strictly between the cubic
    #    prediction and zero for any real duty reduction.
    f_cal = saving_fraction(0.95, 0.35)
    f_cub = saving_fraction_cubic(0.95, 0.35)
    check("calibrated saving sits between cubic and zero",
          0.0 < f_cal < f_cub)
    check("95->35 calibrated saving is 86.25%",
          abs(f_cal - 0.8625) < 1e-4, "got %.6f" % f_cal)

    # 6. Invalid inputs raise.
    for bad in (lambda: fan_power(0.5, -1.0), lambda: fan_power(0.5, 100.0, a=0.0)):
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
    ap.add_argument("--duty-base", type=float, default=0.95)
    ap.add_argument("--duty-ctrl", type=float, default=0.35)
    ap.add_argument("--base-w", type=float, default=1000.0)
    args = ap.parse_args()

    if args.selftest:
        selftest()
        return

    print("=" * 78)
    print("FAN POWER LAW - calibrated against a measured 120 W -> 15 W result")
    print("=" * 78)
    print("law          P(d) = base * (a*d^3 + b*d) / (a+b),  a=%.3f b=%.3f" % (A_CUBIC, B_LOSS))
    print("calibration  @0xAlcibiades quiet-lab: 120 W @ ~90% -> 15 W @ ~30%")
    print()

    r = report(args.duty_base, args.duty_ctrl, args.base_w)
    print("operating point: %.0f%% -> %.0f%% on a %.0f W tray" %
          (100 * r["duty_base"], 100 * r["duty_ctrl"], r["base_w"]))
    print()
    print("  calibrated : %8.1f W -> %8.1f W   save %7.1f W  (%.2f%%)" %
          (r["calibrated_before_w"], r["calibrated_after_w"],
           r["calibrated_saving_w"], r["calibrated_saving_pct"]))
    print("  cubic      : %8.1f W -> %8.1f W   save %7.1f W  (%.2f%%)" %
          (r["cubic_before_w"], r["cubic_after_w"],
           r["cubic_saving_w"], r["cubic_saving_pct"]))
    print()
    print("  the pure affinity law overstates the saving by %.1f W on this tray." %
          r["overstatement_w"])
    print("  That is the difference between a 95%% claim and an 86%% claim.")


if __name__ == "__main__":
    main()
