# The Case

The claim under test, quoted exactly:

> "while this is fun for something like a homelab, applied at scale you'd be
> looking at **7 figure savings for a bare metal deployment** because of reduced
> **fan power consumption** and **thermal cycling**. You can prop this upwards
> to the datacenter scale and back propagate down."
>
> — @0xAlcibiades, 2025-07-06

Two legs, one missing word: **scale**. This document is the proof, and the
conditions under which it fails.

---

## 1. Decomposition

| leg | method | unit | status |
|---|---|---|---|
| fan energy | affinity law `P ∝ duty³`, marginal PUE | $/node/yr | physics, one uncertain input |
| thermal fatigue | swing-ratio scenario; rainflow simulator in `cycling.py` | $/node/yr | conditional on three assumptions, and R is not measured |
| composition | sum, then solve for fleet size | $/yr | arithmetic |
| verification | bound each leg, solve for required attribution | — | the actual deliverable |

The interesting question is not *"is it 7 figures?"* It is
*"7 figures at what fleet size, and which assumption has to be true?"*

---

## 2. Fan energy: the leg that is physics

For a fixed impeller:

```
airflow  ∝ N
pressure ∝ N²
shaft power ∝ N³
```

So a duty reduction is cubic. From 95 % to 35 %:

```
P_ctrl / P_base = (0.35 / 0.95)³ = 0.050
```

95 % of the fan's shaft power disappears. That cubic is the entire business
case, and it is why the result is so sensitive to two numbers nobody publishes:
**the fan tray's base wattage** and **how far duty actually falls**.

### Per node, per year

At $0.09/kWh and PUE 1.4 (PUE multiplies the *saving*, not the facility — a
watt removed at the server also removes its share of cooling overhead):

| node class | fan base | duty base → ctrl | saved W | $/node/yr |
|---|---|---|---|---|
| 1U CPU node | 60 W | 80 % → 35 % | 55.0 | $60.68 |
| 4-GPU node | 400 W | 90 % → 35 % | 376.5 | $415.54 |
| 8-GPU dense node | 1,000 W | 95 % → 52.9 % | 635.9 | $702.08 |

The arithmetic for the 8-GPU row:

```
950 W × 8,760 h / 1,000 = 8,322 kWh/yr
7,065 × $0.09 × 1.4     = $702.08/yr
```

**Every 1,000 eight-GPU nodes is ~$1.05M/yr in fan power alone** under the
ideal cubic. The upstream project's measured 120 W → 15 W result is a **87.5 %**
cut, not 95 %; at 1 kW that is 875 W, or **$965.79/node/yr** and **$0.97M per
1,000 nodes**. The affinity law overstates fan savings at low duty. Use the
875–950 W range until a BMC reading replaces it.

---

## 3. Thermal fatigue: the leg that depends on assumptions

A temperature trace is counted with rainflow (ASTM E1049-85). Damage per cycle
is Coffin-Manson with a Norris-Landzberg mean-temperature correction:

```
N_f ∝ ΔT^(−n) · exp(Ea / k·T_max)      n ≈ 2 (SAC solder), Ea ≈ 0.1 eV
D    = Σ nᵢ / N_fᵢ                      Miner's rule
R    = D_uncontrolled / D_controlled    life ratio
```

On this machine's own 1.67 h trace:

- **109 cycles**, mean ΔT **5.9 °C**, 65.5 cycles/hour
- **15 % of cycles (ΔT 10–20 °C) carry 55 % of the fatigue damage**

That Pareto shape is the only cycling claim this project can support: *the
damage is in the transients, not the ripples.* A controller that holds the die
still removes the large swings first.

The dollar leg below does **not** use that rainflow result. It uses a
**12 °C → 2 °C swing scenario**, `R = (12/2)² = 36`. The package's own laptop
simulator, `cycling.py`, produces **1.3–1.8× Coffin-Manson damage reduction**,
not 36×. The Norris-Landzberg mean-temperature correction reaches ~2.0×; the
dollar table below uses the Coffin-Manson range, not the Norris-Landzberg
column. No server temperature trace exists in this package, so R=36 is an
assumption and must be quoted as a scenario, not a measurement.

Dollars, though, need three numbers that are not in the trace:

```
failures avoided per node-year = afr · share · (1 − 1/R)
fatigue $/node/yr              = failures avoided · replacement
```

with `afr` = annual failure rate, `share` = fraction attributable to cycling,
`replacement` = cost per node. None of these is measured by this project. They
are exposed as parameters, and they are **bounded** — see §5.

---

## 4. Composition

```
total $/node/yr = fan $ + fatigue $
nodes for target = ceil(target / total)
```

At $0.09/kWh, PUE 1.4, the client row uses 5 %/yr failure rate, 20 % cycling
attribution, $1,200 replacement, and 18→12 °C (R=2.25). The server rows use
3 %/yr, 35 % cycling attribution, and R=36; replacement is $7,500 for the 1U CPU node,
$25k for the 4-GPU, and $60k for the 8-GPU:

| node | fan $ | fatigue $ | total $/yr | nodes for $1M |
|---|---|---|---|---|
| Vivobook 15 (client) | 2.03 | 6.67 | **8.70** | 114,980 |
| 1U CPU node | 30.75 | 76.56 | **107.31** | 9,319 |
| 4-GPU node | 415.54 | 255.21 | **670.75** | **1,491** |
| 8-GPU dense node | 701.83 | 612.50 | **1,314.33** | **761** |

Fan power dominates for server classes (62 % of the 4-GPU total). The client
row is not an energy business — the fan leg there is $2.30/yr — which is why the
laptop work is framed as noise and sustained clocks, never savings.

At the cycle simulator's **1.3–1.8×**, the 4-GPU fatigue is **$61–$117/node**
with the $25k replacement (total **$476–$532**). The 8-GPU dense node uses the
$60k replacement: fatigue **$145–$280/node**, total **$1,194–$1,329** at
$0.09/1.4, or **$1,044–$1,179** at the founder-case $0.08/1.35. The R=36 server
rows are a best-case scenario; the range is the honest number. This does not change
Lambda's verdict at 1 kW (energy alone is $1.06M at ATL02), but it changes
Together's ownership boundary.

### Sensitivity

Base case: 4-GPU node, $670.75/node/yr. Each knob moved ±50 %:

| knob | low | high | swing |
|---|---|---|---|
| fan power | 462.98 | 878.51 | **62 %** |
| node cost | 543.14 | 798.35 | 38 % |
| failure rate | 543.14 | 798.35 | 38 % |
| fatigue share | 543.14 | 798.35 | 38 % |
| duty after | 609.08 | 693.47 | 13 % |
| swing after | 661.63 | 676.21 | 2 % |

The single assumption that matters most is **how much fan power a node actually
has**. Everything about the controller — duty after, swing after — is a
rounding error next to it.

---

## 5. Verification

The fatigue leg is bounded. You cannot avoid more failures than occur:

```
max fatigue $/node/yr = afr · share · replacement
                      = 0.03 · 0.35 · $25,000
                      = $262.50
```

4-GPU node at three fleet sizes:

| fleet | need $/node | fan alone | gap | verdict |
|---|---|---|---|---|
| 500 | 2,000 | 415.54 | 1,584.46 | **impossible** — needs 211 % attribution |
| 1,000 | 1,000 | 415.54 | 584.46 | **impossible** — needs 78 % attribution |
| 5,000 | 200 | 415.54 | — | **met by fan power alone** |

This is the honest shape of the claim:

- At **small fleets** it is arithmetically impossible, because the fatigue leg
  is capped and fan power cannot reach the target alone.
- At **large fleets** the fan leg clears it on its own, and cycling is a bonus
  rather than the mechanism.
- The band where the cycling leg is *necessary* is narrow, and inside it the
  claim requires an attribution share nobody has measured.

**The threshold, stated plainly:**

| node class | fan alone reaches $1M at |
|---|---|
| 4-GPU (376.5 W saved) | ~2,407 nodes |
| 8-GPU (950 W saved) | ~954 nodes |
| 1U CPU (55 W saved) | ~16,480 nodes |

Below those counts, the 7-figure claim depends on the fatigue leg — and the
fatigue leg is an assumption, not a measurement.

---

## 6. What was actually built (the "back propagate down" part)

The laptop is the hard case: a machine with **no fan telemetry at all**.

- ASUS Vivobook 15 X1502VA, i9-13900H (14C/20T), 16 GB, BIOS 306, Windows 11.
- Sensing: PawnIO (signed, HVCI-compatible) + LibreHardwareMonitor `IntelMsr`.
  Per-core temperature from `0x19C`, package energy from `0x611`, RAPL unit
  from `0x606`, TjMax from `0x1A2`.
- Controller: learned equilibrium per power profile, discrete MPC over a 90 s
  horizon, asymmetric cost (over-temperature penalised harder than lost work),
  switch penalty to prevent chatter.
- Actuator: ASUS ACPI WMI `AsusAtkWmi_WMNB`, device `0x00110019`
  (`THROTTLE_THERMAL_POLICY_VIVO`), three states.

### The encoding trap

VIVO is **not** the generic ASUS mapping:

| value | VIVO | generic ASUS |
|---|---|---|
| 0 | balanced | balanced |
| 1 | **silent** | overboost |
| 2 | **overboost** | silent |

Writing `1` expecting overboost would silently set silent. The mapping was
taken from the Linux `asus-wmi` driver and confirmed by read-back.

### Measured profile table (20-thread load, AC)

| profile | tail °C | avg W | throughput retained |
|---|---|---|---|
| stock | 82.2 | 25.3 | 100 % |
| efficient | 72.5 | 17.9 | 82 % |
| no-turbo | 67.7 | 10.7 | 40 % |
| floor | 64.5 | 8.7 | 32 % |

Single sequential run, stock first, 12 s cooldown between phases. Phase order
and thermal history are confounded with the profile: the repeated-mode drift
that breaks the mode-effect comparison below applies here too. The temperatures
are the stable result; the throughput ratios are indicative, not a controlled
A/B.

### Observability: three paths, all empty

- Embedded controller via `WindowsEmbeddedControllerIO`: **0 non-zero registers
  of 256**, ~32 s per sweep.
- `Win32_Fan`: present but empty.
- Intel DPTF: device present, no fan WMI class.
- LibreHardwareMonitor: no fan sensor.
- ASUS WMI: 82 device IDs swept, 7 implemented, none is a tachometer or fan
  power. `0x00110013` moves +4 counts monotonically and never returns — a
  counter, not a fan signal.

So the controller closes the loop on **temperature and package power**, not on
fan speed. That is a real limitation, stated rather than hidden.

### The actuator write path (verified)

`DEVS(0x00110019, mode)` returned `result=1` for every write, and the read-back
matched every time:

| write | result | read-back | mode |
|---|---|---|---|
| no-op (0) | 1 | `0x03030000` | 0 |
| silent (1) | 1 | `0x03030001` | 1 |
| restore (0) | 1 | `0x03030000` | 0 |
| overboost (2) | 1 | `0x03030002` | 2 |
| restore (0) | 1 | `0x03030000` | 0 |

Guardrails before the first write: a no-op write, an independent elevated
watchdog holding the restore value, a temperature abort, and an unconditional
restore in `finally`.

### The effect measurement, and its confound

Four phases, constant in-process load, 100 s each, modes 0 → 1 → 2 → 0:

| phase | mode | steady °C | steady W | work rate |
|---|---|---|---|---|
| p0 | 0 | 89.5 | 37.2 | 2.12M |
| p1 | 1 | 84.5 | 26.3 | 1.54M |
| p2 | 2 | 67.8 | 12.5 | 0.96M |
| p3 | 0 | 72.7 | 16.6 | 1.00M |

**The repeated mode-0 phase did not reproduce the first one** (1.00M vs 2.12M
work rate, 16.6 vs 37.2 W). Something in the plant drifted across the run —
thermal history, charging state, or a firmware power limit. That means the
mode-to-mode throughput comparison is **not valid**, and the overboost row is
the most confounded of the four.

What survives: the write path is real and verified, the modes are distinct
states, and the laptop is a machine where a controller must be built without
fan feedback. The precise performance cost of silent mode is an open
measurement, not a published claim.

---

## 7. What is not claimed

- **No field-failure data.** Every fatigue dollar rests on `afr` and `share`,
  both assumptions.
- **No fan bearing wear.** It is the dominant server wear-out mode and is not
  modelled; including it would change the failure attribution entirely.
- **No throughput credit or debit.** A controller that preserves clocks under
  load is worth more than either leg here, and none of it is in this model. The
  laptop controller's own simulation retains **77–81 %** of stock work; on a
  revenue fleet that would be a cost of **~$34k/node/yr**, not a saving. The
  fan leg is only valid if the server actuator cuts fan power at the same
  compute throughput.
- **No dB.** Fan RPM is unreadable on this laptop, so every acoustic number
  would be invented.
- **No second-order interaction.** Removing fan power also removes heat; the
  model does not credit that.
- **No liquid-cooled fleets.** A cold-plate node has no fan tray to slow down.
  The claim applies to **air-cooled bare metal** only. This is not a footnote —
  it excludes a large and growing share of new AI capacity.

---

## 8. Reproduce it

```powershell
uv run python code/case.py --selftest      # 12 checks on the algebra
uv run python code/case.py                 # the composed case
uv run python code/case.py --tariff 0.12   # re-price it
uv run python code/cycling.py --replay data/telemetry-sample.csv
uv run python code/fleet_model.py
uv run python code/targets.py --selftest   # 12 checks on fleet arithmetic
uv run python code/targets.py              # per-fleet table
```

`case.py` refuses to print a dollar figure that is not derived from a stated
input. `cycling.py` has 17 self-tests against synthetic traces with known cycle
counts. `audit.py` re-derives the headlines in Decimal and flags the three
places where the model's claims outrun its evidence: the measured fan curve, the
R=36 assumption, and the undebited throughput loss.

---

## 9. The ask

The model has one load-bearing unknown: **the fan tray's actual wattage**.

If you operate air-cooled GPU nodes, either of these turns the model into a
measurement:

1. one BMC reading of fan power (`FanPower`, `P12V_FAN`, or per-fan watts), or
2. a 30-day trace of fan duty and node power.

With that, the 7-figure claim stops being arithmetic about a parameter and
becomes a measurement about your fleet.

---

The method that produced this: decompose the claim into independent legs,
implement each with the correct physics instead of a proxy, calibrate to
measured data, test the arithmetic, then find the conditions under which the
claim is false. §5 is the deliverable.
