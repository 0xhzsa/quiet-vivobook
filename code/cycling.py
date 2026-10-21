"""
cycling.py - the second half of the "7 figure savings" claim.

quiet-lab's author attributes the money to two things:

    "reduced fan power consumption AND thermal cycling"

fleet_model.py covers the first. This covers the second, properly:

  1. rainflow cycle counting (ASTM E1049-85, three-point method)
  2. Coffin-Manson fatigue damage   D = sum( count * dT^n )
  3. Norris-Landzberg mean-temp correction  (hot cycles hurt more)
  4. Miner's rule to accumulate damage

and it runs three controllers against the same plant and the same workload:

  stock    - no governor, fixed at the stock equilibrium
  bangbang - threshold controller (what a "quiet fan" script does)
  mpc      - the quiet-vivobook controller, ported line for line

The absolute damage number is model dependent. The *ratio* between two
controllers on the same plant is worth quoting, and the sensitivity table
shows how far it moves when the exponent is wrong.

Run:
    uv run --no-project python cycling.py
    uv run --no-project python cycling.py --selftest
"""

from __future__ import annotations

import argparse
import math
import random
from dataclasses import dataclass
from functools import partial


# ---------------------------------------------------------------------------
# measured plant (profiles.csv, AC, 20-thread load)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Profile:
    id: str
    eq: float      # steady state core temperature under sustained load, C
    watts: float   # package power at that steady state, W
    work: float    # fraction of stock throughput retained


PROFILES = (
    Profile("efficient", 72.5, 17.9, 0.82),
    Profile("noturbo", 67.7, 10.7, 0.40),
    Profile("floor", 64.5, 8.7, 0.32),
)

STOCK_EQ = 82.2          # measured stock steady state, same workload
IDLE_EQ = 44.0           # measured idle core temperature
BOOST_RISE = 23.0        # transient equilibrium bump at the start of a load step
BOOST_S = 30.0           # how long the boost lasts

TAU_HEAT = 25.0          # die heats fast
TAU_COOL = 60.0          # chassis cools slowly
POLL = 5.0

# controller settings, identical to config.json
TARGET_HIGH = 80.0
TARGET_LOW = 68.0
EMERGENCY = 90.0
WARN = 85.0
CRIT = 95.0
HORIZON = 18
W_OVER = 1.0
W_PERF = 2.0
W_SWITCH = 6.0
DWELL_S = 25.0
EMA_ALPHA = 0.4
PREDICTIVE_WINDOW = 15.0

CM_EXPONENT = 2.0        # Coffin-Manson exponent for SAC solder, 1.9-2.0
EACT = 0.10              # eV, Norris-Landzberg activation energy
KB_EV = 8.617333262e-5   # eV/K
MIN_RANGE = 1.0          # C, fatigue cycles below this are ignored


# ---------------------------------------------------------------------------
# 1. rainflow counting - ASTM E1049-85 three point method
# ---------------------------------------------------------------------------

def rainflow(series):
    """Return [(range, mean, count), ...] from a sequence of turning points.

    A cycle closes when the newest segment is *shorter* than the one before
    it: the path went X -> Y -> back through X, so X..Y is a closed loop and
    both points come off the stack. Equal ranges are a continuing trend, not
    a cycle - treating them as cycles turns any monotone ramp into noise.

    Whatever is left on the stack is a set of half cycles (count 0.5), which
    is the standard treatment of the residual.
    """
    stack = []
    cycles = []
    for z in series:
        stack.append(z)
        while len(stack) >= 3:
            x, y, zz = stack[-3], stack[-2], stack[-1]
            r1 = abs(y - x)
            r2 = abs(zz - y)
            if r2 >= r1:
                break
            cycles.append((r1, (x + y) / 2.0, 1.0))
            del stack[-3:-1]
    for i in range(len(stack) - 1):
        cycles.append((abs(stack[i + 1] - stack[i]), (stack[i] + stack[i + 1]) / 2.0, 0.5))
    return cycles


def smooth(temps, window=5):
    """Moving average - stops sensor noise from becoming fatigue cycles."""
    if window <= 1 or len(temps) < window:
        return list(temps)
    out = []
    acc = 0.0
    for i, t in enumerate(temps):
        acc += t
        if i >= window:
            acc -= temps[i - window]
        out.append(acc / min(i + 1, window))
    return out


def turning_points(temps):
    """Reduce a sampled signal to reversals, dropping collinear samples."""
    if len(temps) < 3:
        return list(temps)
    out = [temps[0]]
    for i in range(1, len(temps) - 1):
        a, b, c = temps[i - 1], temps[i], temps[i + 1]
        if (b - a) * (c - b) < 0:
            out.append(b)
    out.append(temps[-1])
    return out


# ---------------------------------------------------------------------------
# 2/3. damage models
# ---------------------------------------------------------------------------

def coffin_manson(cycles, n=CM_EXPONENT, floor=MIN_RANGE):
    """Relative damage, arbitrary units: sum count * (dT - floor)^n."""
    total = 0.0
    for rng, _mean, count in cycles:
        d = rng - floor
        if d > 0:
            total += count * (d ** n)
    return total


def norris_landzberg(cycles, n=CM_EXPONENT, eact=EACT, freq=1.0 / 3600.0, floor=MIN_RANGE):
    """Damage with a mean-temperature acceleration term.

    N_f ~ f^-m * dT^-n * exp(Ea / (k * Tmax)), so damage per cycle carries
    exp(-Ea / (k * Tmax)). Tmax is in kelvin.
    """
    m = 1.0 / 3.0
    total = 0.0
    for rng, mean, count in cycles:
        if rng <= floor:
            continue
        tmax_k = mean + rng / 2.0 + 273.15
        total += count * (rng ** n) * (freq ** m) * math.exp(-eact / (KB_EV * tmax_k))
    return total


def cycle_report(temps):
    """Smooth, reduce to reversals, count, score."""
    cyc = rainflow(turning_points(smooth(temps)))
    full = [c for c in cyc if c[2] == 1.0 and c[0] >= MIN_RANGE]
    return cyc, full


# ---------------------------------------------------------------------------
# plant
# ---------------------------------------------------------------------------

def step_temp(temp, eq, dt):
    """One step of a first-order plant with an asymmetric time constant."""
    tau = TAU_HEAT if eq > temp else TAU_COOL
    return temp + (dt / tau) * (eq - temp)


def equilibrium(profile_watts, profile_eq, t_in_period, on_s, off_s, boosted_eq):
    if t_in_period >= on_s:
        return IDLE_EQ
    if t_in_period < BOOST_S:
        return boosted_eq
    return profile_eq


# ---------------------------------------------------------------------------
# controllers
# ---------------------------------------------------------------------------

def mpc_action(temp, ema, trend, idx, w_over=W_OVER, w_switch=W_SWITCH, w_perf=W_PERF):
    """Ported from Invoke-Mpc in quiet-vivobook.ps1."""
    decay = math.exp(-POLL / 60.0)
    start = ema + max(0.0, trend) * PREDICTIVE_WINDOW
    best, best_cost = idx, float("inf")
    for a, p in enumerate(PROFILES):
        t = start
        cost = 0.0
        peak = start
        for _ in range(HORIZON):
            t = p.eq + (t - p.eq) * decay
            peak = max(peak, t)
            over = t - TARGET_HIGH
            if over > 0:
                sigma = min(1.0, max(0.0, (t - WARN) / (CRIT - WARN)))
                cost += w_over * (1 + 9 * sigma ** 3) * over * over
        cost += w_perf * (1.0 - p.work) * HORIZON
        if a != idx:
            cost += w_switch
        if peak >= EMERGENCY:
            cost += 10000.0
        if cost < best_cost:
            best, best_cost = a, cost
    return best


def bangbang_action(temp, ema, trend, idx):
    """Threshold controller with the same dwell as the governor."""
    projected = ema + max(0.0, trend) * PREDICTIVE_WINDOW
    if (ema > TARGET_HIGH or temp > TARGET_HIGH + 2 or projected > TARGET_HIGH + 3) and idx < 2:
        return idx + 1
    if ema < TARGET_LOW and temp < TARGET_LOW and projected < TARGET_LOW + 2 and idx > 0:
        return idx - 1
    return idx


def stock_action(temp, ema, trend, idx):
    return 0


# ---------------------------------------------------------------------------
# simulation
# ---------------------------------------------------------------------------

@dataclass
class Result:
    name: str
    temps: list
    switches: int
    cycles: list
    full: list
    cm: float
    nl: float
    mean_range: float
    max_range: float
    mean_temp: float
    peak: float
    work: float


def simulate(controller, on_min, off_min, hours, seed=7, noise=0.2, name=None):
    rng = random.Random(seed)
    on_s, off_s = on_min * 60.0, off_min * 60.0
    period = on_s + off_s
    dt = POLL
    steps = int(hours * 3600 / dt)
    warmup = int(0.15 * steps)

    temp = IDLE_EQ
    ema = None
    prev_ema = None
    trend = 0.0
    idx = 0
    last_switch = -1e9
    switches = 0
    temps = []
    work_acc = 0.0

    for k in range(steps):
        t = k * dt
        phase = t % period
        p = PROFILES[idx]
        eq = equilibrium(p.watts, p.eq, phase, on_s, off_s,
                         p.eq + BOOST_RISE * (p.watts / PROFILES[0].watts))
        if controller is stock_action:
            eq = STOCK_EQ if phase < on_s else IDLE_EQ
            if phase < BOOST_S and phase < on_s:
                eq = STOCK_EQ + BOOST_RISE

        temp = step_temp(temp, eq, dt)
        observed = temp + rng.gauss(0.0, noise)
        temps.append(observed)

        prev_ema = ema
        ema = observed if ema is None else (1 - EMA_ALPHA) * ema + EMA_ALPHA * observed
        if prev_ema is not None:
            trend = 0.6 * trend + 0.4 * ((ema - prev_ema) / dt)

        if t - last_switch >= DWELL_S:
            nxt = controller(observed, ema, trend, idx)
            if nxt != idx:
                idx = nxt
                switches += 1
                last_switch = t
        work_acc += 1.0 if controller is stock_action else PROFILES[idx].work

    cut = temps[warmup:]
    cycles, full = cycle_report(cut)
    return Result(
        name=name or getattr(controller, "__name__", "controller").replace("_action", ""),
        temps=cut,
        switches=switches,
        cycles=cycles,
        full=full,
        cm=coffin_manson(cycles),
        nl=norris_landzberg(cycles, freq=1.0 / period),
        mean_range=(sum(c[0] for c in full) / len(full)) if full else 0.0,
        max_range=max((c[0] for c in full), default=0.0),
        mean_temp=sum(cut) / len(cut),
        peak=max(cut),
        work=work_acc / steps,
    )


# ---------------------------------------------------------------------------
# self tests
# ---------------------------------------------------------------------------

def selftest():
    ok = 0

    def check(name, cond, detail=""):
        nonlocal ok
        if not cond:
            print("  FAIL  %s   %s" % (name, detail))
            raise SystemExit(1)
        ok += 1
        print("  pass  %s" % name)

    # A monotone ramp is not a full cycle, but it is a half-cycle. The old
    # "no damage" assertion was physically false and hid the residual-cycle
    # handling; count the half-cycle after extracting turning points.
    ramp = [float(i) for i in range(200)]
    half = rainflow(turning_points(ramp))
    check("monotone ramp: no full cycles",
          all(c[2] != 1.0 for c in half))
    check("monotone ramp: one half-cycle with damage",
          len(half) == 1 and abs(half[0][0] - 199.0) < 1e-9
          and half[0][2] == 0.5 and coffin_manson(half) > 0.0)

    # conservation: n turning points always hold (n-1)/2 cycle equivalents
    for name, seq in (
        ("ramp", ramp),
        ("alternating", [0.0, 10.0] * 7),
        ("sine", [10 * math.sin(2 * math.pi * i / 20) for i in range(41)]),
        ("random walk", [sum(random.Random(i).gauss(0, 1) for i in range(1, 40))]),
    ):
        total = sum(c[2] for c in rainflow(seq))
        check("conservation: %s" % name, abs(total - (len(seq) - 1) / 2.0) < 1e-9,
              "%.3f != %.3f" % (total, (len(seq) - 1) / 2.0))

    # a nested excursion closes exactly one cycle, with the outer range
    cyc = rainflow([0.0, 10.0, 2.0, 8.0, 0.0])
    full = [c for c in cyc if c[2] == 1.0]
    check("nested: one cycle", len(full) == 1, str(full))
    check("nested: range is the outer one", abs(full[0][0] - 10.0) < 1e-9)

    # offset invariance
    base = [0, 5, -1, 3, -2, 8, -6, 4]
    check("offset invariant",
          sorted((round(r, 6), c) for r, _m, c in rainflow(base)) ==
          sorted((round(r, 6), c) for r, _m, c in rainflow([x + 1000 for x in base])))

    # amplitude scaling
    big = rainflow([0.0, 20.0, 5.0, 15.0, 0.0])
    small = rainflow([0.0, 10.0, 2.5, 7.5, 0.0])
    r_big = [c[0] for c in big if c[2] == 1.0][0]
    r_small = [c[0] for c in small if c[2] == 1.0][0]
    check("scaling: range doubles", abs(r_big / r_small - 2.0) < 1e-9)

    # damage ordering
    check("amplitude matters", coffin_manson(big) > coffin_manson(small))
    check("exponent matters", coffin_manson(big, n=2.5) > coffin_manson(big, n=2.0))

    # hot cycles damage more
    cold = rainflow([40.0, 50.0, 42.0, 49.0, 40.0])
    hot = rainflow([80.0, 90.0, 82.0, 89.0, 80.0])
    check("norris-landzberg: hot worse", norris_landzberg(hot) > norris_landzberg(cold))

    # smoothing must not destroy the real cycles
    t = [60 + 12 * math.sin(2 * math.pi * i / 120) for i in range(600)]
    raw = coffin_manson(rainflow(turning_points(t)))
    sm = coffin_manson(rainflow(turning_points(smooth(t))))
    check("smoothing keeps the signal", sm > 0.0 and abs(sm - raw) / raw < 0.10,
          "%.2f vs %.2f" % (sm, raw))

    # noise must not create damage out of a steady temperature
    flat = [60 + random.Random(3).gauss(0, 0.3) for _ in range(600)]
    check("noise floor ignored", coffin_manson(rainflow(turning_points(smooth(flat)))) == 0.0)

    # valuation: count cycling-related failures once, not all failures
    avoided, dollars = value(2.0, fleet=1000, afr=0.03,
                             replacement=7500.0, share=0.35)
    check("valuation counts cycling share once",
          abs(avoided - 1000 * 0.03 * 0.35 * 0.5) < 1e-9)
    check("valuation dollars", abs(dollars - avoided * 7500.0) < 1e-9)

    print("\n%d checks passed" % ok)


# ---------------------------------------------------------------------------
# valuation
# ---------------------------------------------------------------------------

def value(ratio, fleet=1000, afr=0.03, replacement=7500.0, share=0.35):
    """Cycling-related replacements avoided per year when damage drops by `ratio`.

    `afr` is failures per node-year, not 1/service life. `share` is the
    fraction of failures attributable to cycling, so it is applied exactly
    once. The earlier version counted all failures as "avoided" and then
    discounted only the dollars, which overstated the replacement count by
    1/share (2.86x at the default 35%).
    """
    if ratio <= 0:
        raise ValueError("ratio must be positive")
    if afr < 0 or replacement < 0:
        raise ValueError("afr and replacement must be non-negative")
    if not (0.0 <= share <= 1.0):
        raise ValueError("share must be in [0, 1]")
    avoided = fleet * afr * share * (1.0 - 1.0 / ratio)
    return avoided, avoided * replacement


# ---------------------------------------------------------------------------
# weight sweep - the tuning study the config currently guesses at
# ---------------------------------------------------------------------------

def sweep(hours=12.0, on=4.0, off=4.0):
    base = simulate(bangbang_action, on, off, hours)
    print("WEIGHT SWEEP  (%g min on / %g min off, %g h)" % (on, off, hours))
    print("  bangbang reference: %d switches, %.1f C mean, %.1f C peak, %.1f C dT, work %.1f%%"
          % (base.switches, base.mean_temp, base.peak, base.mean_range, 100 * base.work))
    print("  %-7s %-8s %7s %8s %8s %8s %10s %9s %7s" %
          ("wOver", "wSwitch", "switch", "meanT", "peakT", "mean dT", "damage", "vs bang", "work"))
    best = None
    for w_over in (1.0, 3.0, 10.0):
        for w_switch in (0.0, 2.0, 6.0, 12.0):
            ctrl = partial(mpc_action, w_over=w_over, w_switch=w_switch)
            r = simulate(ctrl, on, off, hours, name="mpc")
            ratio = base.cm / max(r.cm, 1e-12)
            print("  %-7.0f %-8.0f %7d %8.1f %8.1f %8.1f %10.3e %8.2fx %6.1f%%" %
                  (w_over, w_switch, r.switches, r.mean_temp, r.peak,
                   r.mean_range, r.cm, ratio, 100 * r.work))
            if r.peak < 85 and r.work >= base.work and (best is None or r.cm < best[0]):
                best = (r.cm, w_over, w_switch, r)
    if best:
        _, wo, ws, r = best
        print("\n  best that keeps peak < 85 C and throughput >= bangbang:")
        print("    wOver=%.0f wSwitch=%.0f -> %.2fx damage vs bangbang, %d switches, work %.1f%%"
              % (wo, ws, base.cm / r.cm, r.switches, 100 * r.work))


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def load_telemetry(path):
    """Read telemetry.csv, tolerating both the 5 and 7 column schemas."""
    rows = []
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("time,"):
                continue
            parts = line.split(",")
            if len(parts) < 5:
                continue
            try:
                rows.append((parts[0], float(parts[1]), float(parts[2])))
            except ValueError:
                continue
    return rows


def replay(path):
    """Measure the cycle histogram of a recorded trace. No counterfactual."""
    rows = load_telemetry(path)
    if len(rows) < 50:
        print("not enough samples in %s (%d)" % (path, len(rows)))
        return

    first, last = rows[0][0], rows[-1][0]
    temps = [r[1] for r in rows]
    watts = [r[2] for r in rows]
    cycles, full = cycle_report(temps)
    span_h = max((len(rows) - 1) * POLL / 3600.0, 1e-9)

    print("REPLAY  %s" % path)
    print("  window   : %s -> %s  (%d samples, %.2f h)" % (first, last, len(rows), span_h))
    print("  temp     : mean %.1f C, peak %.1f C, power mean %.1f W"
          % (sum(temps) / len(temps), max(temps), sum(watts) / len(watts)))
    print("  cycles   : %d full, mean dT %.1f C, max dT %.1f C, %.1f per hour"
          % (len(full), sum(c[0] for c in full) / len(full) if full else 0.0,
             max((c[0] for c in full), default=0.0), len(full) / span_h))

    total = coffin_manson(cycles)
    print("  damage   : %.3e total, %.3e per hour" % (total, total / span_h))

    buckets = ((1, 3), (3, 6), (6, 10), (10, 20), (20, 1e9))
    print("  %-10s %8s %8s %10s" % ("dT range", "cycles", "share", "damage%"))
    for lo, hi in buckets:
        sel = [c for c in full if lo <= c[0] < hi]
        d = coffin_manson([(c[0], c[1], c[2]) for c in sel])
        label = "%g-%g" % (lo, hi) if hi < 1e9 else "%g+" % lo
        print("  %-10s %8d %7.0f%% %9.0f%%"
              % (label, len(sel), 100.0 * len(sel) / max(len(full), 1),
                 100.0 * d / max(total, 1e-12)))

    print("  note     : measurement only. A counterfactual needs the plant model,")
    print("             which is what the simulator above provides.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--sweep", action="store_true")
    ap.add_argument("--replay", metavar="CSV")
    ap.add_argument("--hours", type=float, default=12.0)
    args = ap.parse_args()

    if args.selftest:
        selftest()
        return
    if args.replay:
        replay(args.replay)
        return
    if args.sweep:
        sweep(hours=args.hours)
        return

    print("THERMAL CYCLING MODEL")
    print("=" * 78)
    print("plant  : measured equilibria, tau %.0fs heat / %.0fs cool, boost +%.0fC"
          % (TAU_HEAT, TAU_COOL, BOOST_RISE))
    print("damage : Coffin-Manson n=%.1f, Norris-Landzberg Ea=%.2f eV, floor %.1fC"
          % (CM_EXPONENT, EACT, MIN_RANGE))
    print("note   : absolute damage is arbitrary; the ratios are the claim")

    results = {}
    for on, off in ((2.0, 2.0), (4.0, 4.0), (10.0, 10.0)):
        print()
        print("CASE  %g min on / %g min off, %g h" % (on, off, args.hours))
        print("  %-9s %7s %7s %8s %8s %8s %8s %11s %7s %8s" %
              ("controller", "switch", "cycles", "mean dT", "max dT", "mean T", "peak T", "damage", "work", "per work"))
        row = {}
        for ctrl, label in ((stock_action, "stock"), (bangbang_action, "bangbang"), (mpc_action, "mpc")):
            r = simulate(ctrl, on, off, args.hours)
            row[label] = r
            print("  %-9s %7d %7d %8.1f %8.1f %8.1f %8.1f %11.3e %6.1f%% %8.3f" %
                  (label, r.switches, len(r.full), r.mean_range, r.max_range,
                   r.mean_temp, r.peak, r.cm, 100 * r.work, r.cm / max(r.work, 1e-9) / 1e5))
        base = row["stock"].cm
        print("  damage vs stock : bangbang %5.2fx   mpc %5.2fx" %
              (base / max(row["bangbang"].cm, 1e-12), base / max(row["mpc"].cm, 1e-12)))
        print("  per unit work   : bangbang %5.2fx   mpc %5.2fx   (higher is better)"
              % (row["stock"].cm / max(row["bangbang"].cm / max(row["bangbang"].work, 1e-9), 1e-12),
                 row["stock"].cm / max(row["mpc"].cm / max(row["mpc"].work, 1e-9), 1e-12)))
        print("  fatigue vs stock: bangbang %5.2fx   mpc %5.2fx" %
              (row["stock"].nl / max(row["bangbang"].nl, 1e-12),
               row["stock"].nl / max(row["mpc"].nl, 1e-12)))
        results[(on, off)] = row

    print()
    print("SENSITIVITY  (4 on / 4 off) - mpc vs bangbang damage reduction")
    row = results[(4.0, 4.0)]
    print("  %-5s %10s %10s" % ("n", "coffin", "norris-l"))
    for n in (1.5, 1.9, 2.0, 2.5):
        cm = coffin_manson(row["bangbang"].cycles, n=n) / max(coffin_manson(row["mpc"].cycles, n=n), 1e-12)
        nl = norris_landzberg(row["bangbang"].cycles, n=n) / max(norris_landzberg(row["mpc"].cycles, n=n), 1e-12)
        print("  %-5.1f %9.2fx %9.2fx" % (n, cm, nl))

    print()
    print("VALUATION vs doing nothing (stock), 4 on / 4 off")
    print("  assumes 3%/yr failure rate, 35% cycling-related, $7,500 node")
    print("  %-7s %-9s %12s %14s" % ("fleet", "controller", "avoided/yr", "$/yr"))
    stock = results[(4.0, 4.0)]["stock"].cm
    for fleet in (100, 1000, 5000):
        for name in ("bangbang", "mpc"):
            ratio = stock / max(results[(4.0, 4.0)][name].cm, 1e-12)
            avoided, usd = value(ratio, fleet=fleet)
            print("  %-7d %-9s %12.1f %14s" % (fleet, name, avoided, "${:,.0f}".format(usd)))

    print()
    print("CAVEATS")
    print("  - fan bearing wear is the dominant server wear-out mode and is not modelled")
    print("  - plant is first order, calibrated to four measured points, not CFD")
    print("  - a governor that steps profiles can add cycles while lowering Tmax;")
    print("    read the norris-l column, not the coffin-manson column alone")


if __name__ == "__main__":
    main()
