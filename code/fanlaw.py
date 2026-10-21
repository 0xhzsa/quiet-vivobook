#!/usr/bin/env python3
"""
fanlaw.py - the fan power law, and the uncertainty it carries.

The naive model is the affinity law: for a fixed impeller, airflow ~ N,
pressure ~ N^2, and shaft power ~ N^3. That predicts a 95% -> 35% duty cut
removes 95% of fan power.

It is wrong, and the direction of the error matters, because the whole claim
is a dollar figure. @0xAlcibiades measured 120 W -> 15 W on a real 64-core
Ampere server (github.com/0xAlcibiades/quiet-lab, MIT): an 87.5% cut, not 95%.
The pure cubic overstates the saving.

Why the cubic fails
-------------------
A real fan is not an ideal impeller on a free-air load:

  1. Motor losses. Brushless DC fan motors have a floor on electrical input
     that does not vanish with speed.
  2. Bearing and windage losses grow with speed at a different exponent than
     the aerodynamic term.
  3. Drive electronics quiescent current is roughly speed-independent.

So the model is affine-cubic: P(d) = base * (a*d^3 + b*d) / (a + b), with the
speed-independent part folded into the linear term.

THE HONEST PART: this law has ONE free parameter fitted to ONE measured
number, at duty points that quiet-lab only states as ranges.

  measured_before_w  120.0   @0xAlcibiades, quiet-lab README
  measured_after_w    15.0   @0xAlcibiades, quiet-lab README
  duty_before      0.80-1.00  README says "80-100%"; we use the RANGE
  duty_after       0.25-0.35  README says "25-35%"; we use the RANGE

Solving with a = 1 for b, at every combination of the stated duty ranges,
gives b in [0.085, 0.875] - a 10x spread. The resulting fan saving at a
given duty is a BAND, not a number. `saving_band()` returns that band.

The midpoint choice (0.90, 0.30) is one point in that range. It is used for
the headline because it is the most defensible single choice, and every
headline is reported with the band beside it.

Do not quote a fan saving from this module without the band.

    uv run --no-project python code/fanlaw.py --selftest
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass

# The measured anchor this law is calibrated to.
MEASURED_BEFORE_W = 120.0
MEASURED_AFTER_W = 15.0
MEASURED_DUTY_BEFORE_RANGE = (0.80, 1.00)   # README states 80-100%
MEASURED_DUTY_AFTER_RANGE = (0.25, 0.35)    # README states 25-35%

# The midpoint choice, used for the headline. Also the calibration point.
DUTY_BEFORE = 0.90
DUTY_AFTER = 0.30

# Empirical fit coefficients at the midpoint choice. a is the aerodynamic
# (cubic) weight, b is the speed-independent + speed-linear loss weight.
A_CUBIC = 1.0
B_LOSS = 0.342

# The affinity-law prediction at the same duty pair, for comparison.
CUBIC_PREDICTED_AFTER_W = MEASURED_BEFORE_W * (DUTY_AFTER / DUTY_BEFORE) ** 3


def loss_coefficient(w_before: float, w_after: float,
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


def fan_power(duty: float, base_w: float, a: float = A_CUBIC,
              b: float = B_LOSS) -> float:
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


@dataclass(frozen=True)
class Band:
    """A range, with the point estimate inside it."""
    low: float
    high: float
    point: float

    def __str__(self) -> str:
        return f"{100 * self.low:.1f}-{100 * self.high:.1f}% (point {100 * self.point:.1f}%)"


def b_range(d1_range=MEASURED_DUTY_BEFORE_RANGE,
            d2_range=MEASURED_DUTY_AFTER_RANGE) -> tuple:
    """The range of loss coefficients implied by quiet-lab's stated duty ranges."""
    vals = []
    for d1 in d1_range:
        for d2 in d2_range:
            vals.append(loss_coefficient(MEASURED_BEFORE_W, MEASURED_AFTER_W, d1, d2))
    return (min(vals), max(vals))


def saving_band(duty_base: float, duty_ctrl: float,
                d1_range=MEASURED_DUTY_BEFORE_RANGE,
                d2_range=MEASURED_DUTY_AFTER_RANGE) -> Band:
    """The fan saving as a BAND over the duty ranges quiet-lab states.

    This is the honest output of the law. The point estimate uses the duty
    midpoints, which is a choice, not a measurement.
    """
    lo_b, hi_b = b_range(d1_range, d2_range)
    b_point = loss_coefficient(MEASURED_BEFORE_W, MEASURED_AFTER_W, DUTY_BEFORE, DUTY_AFTER)
    vals = []
    for b in (lo_b, hi_b):
        before = fan_power(duty_base, 1.0, B_LOSS, b)
        after = fan_power(duty_ctrl, 1.0, B_LOSS, b)
        vals.append((before - after) / before if before else 0.0)
    lo, hi = min(vals), max(vals)
    point = saving_fraction(duty_base, duty_ctrl)
    return Band(low=lo, high=hi, point=point)


def report(duty_base: float = 0.95, duty_ctrl: float = 0.35,
           base_w: float = 1000.0) -> dict:
    """Everything a reader needs to see the model and its error in one dict."""
    before = fan_power(duty_base, base_w)
    after = fan_power(duty_ctrl, base_w)
    before_c = fan_power_cubic(duty_base, base_w)
    after_c = fan_power_cubic(duty_ctrl, base_w)
    band = saving_band(duty_base, duty_ctrl)
    lo_b, hi_b = b_range()
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
        "saving_band_pct": (100.0 * band.low, 100.0 * band.high),
        "b_range": (lo_b, hi_b),
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
    before = fan_power(DUTY_BEFORE, base_w_from_measurement(MEASURED_BEFORE_W, DUTY_BEFORE))
    after = fan_power(DUTY_AFTER, base_w_from_measurement(MEASURED_BEFORE_W, DUTY_BEFORE))
    check("calibrated law reproduces 120 W at 90% duty",
          abs(before - MEASURED_BEFORE_W) < 1e-6, "got %.4f" % before)
    check("calibrated law reproduces 15 W at 30% duty",
          abs(after - MEASURED_AFTER_W) < 1e-6, "got %.4f" % after)

    # 2. The pure cubic overstates, and by how much.
    measured_frac = (MEASURED_BEFORE_W - MEASURED_AFTER_W) / MEASURED_BEFORE_W
    check("pure cubic overstates the saving",
          saving_fraction_cubic(DUTY_BEFORE, DUTY_AFTER) > measured_frac + 0.05)
    check("cubic prediction at 30% is 4.44 W, not 15 W",
          abs(CUBIC_PREDICTED_AFTER_W - 4.44) < 0.01,
          "got %.4f" % CUBIC_PREDICTED_AFTER_W)

    # 3. THE UNCERTAINTY. This is the check that was missing.
    lo_b, hi_b = b_range()
    check("b spans more than a 5x range over the stated duty ranges",
          hi_b / lo_b > 5.0, "got %.2fx (%.3f to %.3f)" % (hi_b / lo_b, lo_b, hi_b))
    band = saving_band(0.95, 0.353)
    check("the saving band is wider than 5 points",
          (band.high - band.low) > 0.05,
          "band %.4f wide" % (band.high - band.low))
    check("the point estimate lies inside the band",
          band.low <= band.point <= band.high,
          "point %.4f band [%.4f, %.4f]" % (band.point, band.low, band.high))
    # The naive cubic is the OPTIMISTIC end of every physically admissible
    # calibration, and it falls OUTSIDE the band. That is the point of the
    # band: it is not a way to rescue the cubic, it is a way to exclude it.
    check("the naive cubic lies ABOVE the whole band",
          saving_fraction_cubic(0.95, 0.353) > band.high,
          "cubic %.4f band high %.4f" % (saving_fraction_cubic(0.95, 0.353), band.high))
    check("the band excludes the cubic claim",
          band.high < saving_fraction_cubic(0.95, 0.353))
    check("the midpoint point estimate is not the optimistic end",
          abs(band.point - band.high) > 0.01,
          "point %.4f high %.4f" % (band.point, band.high))

    # 4. Monotonicity and bounds.
    check("power is monotonic in duty",
          all(fan_power(d / 100.0, 1000.0) < fan_power((d + 1) / 100.0, 1000.0)
              for d in range(100)))
    check("power at 100% duty equals base", abs(fan_power(1.0, 1000.0) - 1000.0) < 1e-9)
    check("power at 0% duty is zero", fan_power(0.0, 1000.0) == 0.0)

    # 5. The law is gentler than cubic at every interior point: the loss term
    #    keeps a floor under the power, which is the physical claim.
    check("calibrated law sits above the cubic for all interior duty",
          all(fan_power(d / 100.0, 1000.0) >= fan_power_cubic(d / 100.0, 1000.0)
              for d in range(1, 100)))

    # 6. The affine-cubic saving fraction is strictly between the cubic
    #    prediction and zero for any real duty reduction.
    f_cal = saving_fraction(0.95, 0.35)
    f_cub = saving_fraction_cubic(0.95, 0.35)
    check("calibrated saving sits between cubic and zero",
          0.0 < f_cal < f_cub)
    check("95->35 calibrated saving is 86.25%",
          abs(f_cal - 0.8625) < 1e-4, "got %.6f" % f_cal)

    # 7. Invalid inputs raise.
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
    print("calibration  @0xAlcibiades quiet-lab: 120 W -> 15 W")
    print("duty points  quiet-lab states 80-100%% and 25-35%%; midpoints %.0f%% and %.0f%% used"
          % (100 * DUTY_BEFORE, 100 * DUTY_AFTER))
    print()
    lo_b, hi_b = b_range()
    print("UNCERTAINTY: b ranges %.3f to %.3f over the stated duty ranges (%.1fx)"
          % (lo_b, hi_b, hi_b / lo_b))
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
    band = saving_band(args.duty_base, args.duty_ctrl)
    print("  BAND over quiet-lab's stated duty ranges: %.1f%% - %.1f%%" %
          (100 * band.low, 100 * band.high))
    print("  point estimate at the midpoints:          %.1f%%" % (100 * band.point))
    print()
    print("  The pure affinity law overstates the saving by %.1f W on this tray." %
          r["overstatement_w"])
    print()
    print("  Quote the band, not the point. The point is one choice of duty")
    print("  midpoint inside a range quiet-lab only states as a range.")


if __name__ == "__main__":
    main()
