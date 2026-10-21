# PHYSICS

The models this repository uses, what each one assumes, and where each one
was calibrated. Every model here is a model. Two of them are calibrated
against a measurement; the rest are stated assumptions with named inputs.

---

## 1. Fan power

### 1.1 The affinity law, and why it is not enough

For a fixed impeller on a free-air load:

```
airflow  ∝ N
pressure ∝ N²
shaft power ∝ N³
```

A duty reduction is therefore cubic, and the pure cubic is the entire reason
fan control is worth money. It is also the single most overstated term in
vendor economics, because a real fan is not an ideal impeller.

The one real server measurement available to this project is upstream's:

| | |
|---|---|
| fan power | 120 W → 15 W |
| cut | 87.5 % (upstream's table rounds it to −87 %) |
| idle fan speed | 80–100 % → 25–35 % |
| noise | 65 dB → 42 dB |
| machine | 64-core Ampere Altra (Supermicro ARS-210M-NR), a **CPU server**, not a GPU node |

Source: [@0xAlcibiades, quiet-lab](https://github.com/0xAlcibiades/quiet-lab)
(MIT). It is the only measured fan-power saving in this repository, and it is
**87.5 %, not 95 %**.

### 1.2 Why the cubic overstates the saving

Three effects break the pure `N³` scaling on real hardware:

1. **Motor losses.** Bearing friction, windage and brushless drive electronics
   have a floor on electrical input that does not vanish with speed. Power
   falls as roughly `a + b·d³`, not `d³` alone.
2. **The load regime.** A fan at low duty against a restricted duct runs
   closer to stall, where the cubic relation is at its weakest.
3. **Quiescent draw.** The controller and driver electronics draw roughly the
   same at 25 % duty as at 100 %.

The consequence is that the pure cubic overstates the saving in the direction
that matters: it predicts a larger number than the machine actually delivers.
On a 1 kW tray, 95 % → 35 %:

| law | at 95 % | at 35 % | saved | cut |
|---|---:|---:|---:|---:|
| pure cubic | 857.4 W | 42.9 W | 814.5 W | 95.0 % |
| calibrated affine-cubic | 881.0 W | 121.1 W | 759.8 W | 86.25 % |

The cubic overstates the saving by **54.7 W on a 1 kW tray**. On the upstream
node the same disagreement is 120 W → 15 W measured against 120 W → 4.4 W
predicted — a factor of 3.4.

### 1.3 The empirical fit

The model used in `code/fanlaw.py` and `code/server_thermal_controller.py` is
an affine-cubic: the aerodynamic cubic term plus a loss term, normalised so
that the power at 100 % duty is the base wattage.

```
P(d) = base · (a·d³ + b·d) / (a + b)
```

`a` is the aerodynamic weight, `b` is the loss weight. The calibration uses
the upstream measurement's two points:

```
120 W at ~90 % duty
 15 W at ~30 % duty
```

(The upstream README states duty ranges of 80–100 % and 25–35 %; the
midpoints are used, which is an assumption and is labelled as one in
`code/fanlaw.py`.)

The ratio of the two measurements removes `base` and the normalisation:

```
120 / 15 = 8 = (a·0.9³ + b·0.9) / (a·0.3³ + b·0.3)
```

With `a = 1`:

```
0.729 + 0.9b  =  8 · (0.027 + 0.3b)  =  0.216 + 2.4b
0.513         =  1.5b
b             =  0.342
```

The implied power at 100 % duty is then

```
base = 120 · (1 + 0.342) / (0.729 + 0.342 · 0.90) = 155.3 W
```

So a 120 W reading at 90 % duty implies a 155.3 W tray at full speed, and
with those two numbers the model reproduces the measurement exactly.

**The percentages are not the same claim, and the difference matters.**

- **87.5 %** is the cut at the *measured* duty pair (≈90 % → ≈30 %). It is
  the only measured fan-power saving in this project.
- **86.25 %** is the cut the calibrated law gives at 95 % → 35 % — the duty
  pair the *first* version of the fleet model used.
- **86.10 %** is the cut the *thermal* model gives at 80 % GPU load when it is
  asked to hold the 83 °C throttle knee. It is a different construction from
  the fan law, and it lands 1.4 points from the measurement, which is the
  strongest evidence in this package that the two models are both roughly
  right.
- **72.20 %** is the cut at the *shipped* duty of 52.9 %, which holds the die
  at 75 °C and costs no throughput at all.
- **95 %** is what the pure cubic predicts, and it is wrong.

---

## 2. The thermal model

`code/server_thermal_controller.py` uses a lumped-parameter model with three
nodes: die, heatsink, and case air.

```
        Q_gpu                  Q_dh                  Q_ha                  Q_amb
   ┌────────────┐        ┌────────────┐        ┌────────────┐        ┌────────────┐
   │    die     │  R_dh  │  heatsink  │  R_ha  │  case air  │ R_amb  │  ambient   │
   │ C = 1800 J/K│◄──────►│ C = 7200 J/K│◄──────►│ C = 5000 J/K│◄──────►│  25 °C     │
   └────────────┘        └────────────┘        └────────────┘        └────────────┘
```

| parameter | value | source |
|---|---|---|
| die heat capacity | 2.0 kg × 900 J/kgK = 1800 J/K | assumed (die + cold plate) |
| heatsink heat capacity | 8.0 kg × 900 J/kgK = 7200 J/K | assumed (full heatsink assembly) |
| case air heat capacity | 5.0 kg × 1000 J/kgK = 5000 J/K | assumed (case air + chassis) |
| `R_die_hs` | 0.0050 K/W | assumed (TIM and copper spreader) — **does not scale with airflow** |
| `R_hs_air` | 0.0028 K/W | assumed (fin array, 8 fans) — **scales with airflow** |
| `R_air_amb` | 0.0015 K/W | assumed (case exhaust path to ambient) — **does not scale with airflow** |
| ambient | 25 °C | assumed |
| time step | 1 s | — |

The calibration anchor is a single steady state: a dense 8×700 W node at
95 % fan duty and full GPU load holds a die temperature near 77 °C, which is
where an H100 actually sits under sustained load. Every other number in the
file falls out of that anchor.

### Airflow scaling

Only the convection path over the fin array scales with airflow. The heat
transfer coefficient goes as `h ∝ duty^0.8`, so the heatsink-to-air resistance
is divided by `h` at every step:

```
h   = duty^0.8
R_dh = R_die_hs              (fixed conduction: TIM and spreader)
R_ha = R_hs_air / h          (forced convection over the fin array)
```

The exponent 0.8 is not a free parameter chosen here. It is the turbulent-flow
exponent from upstream's heat-transfer model, where `H_ii(u) = Σ H^max_ij ·
u_j^α` with α ≈ 0.8 — the same structure, reimplemented.

### Steady state, solved

At steady state every path carries the same power `P`, because the only
source is the GPU and the only sink is ambient. The three resistances are
therefore in series, and the closed form is:

```
T_inlet = T_ambient + P · R_air_amb
T_hs    = T_inlet  + P · R_hs_air / h
T_die   = T_hs     + P · R_die_hs
```

The closed form is then verified against the time-domain model, and the
self-test asserts that they agree to within 1 °C and that the model
converges (drift over the last 20 % of a 3,000 s run below 0.05 °C).

This matters: a 120 s timed run at 35 % duty has not settled, and it reports
a die temperature several degrees below the real one. A fan controller is
asked to hold a temperature forever, not for two minutes, so every duty point
in this project is a steady-state point.

### The safe duty, and why it is the number that matters

`min_duty_for_temp()` bisects on duty for the **lowest** duty that holds the
die at or below a target temperature. That is not the duty that maximizes the
fan saving. It is the duty that is actually safe, and it is a function of GPU
load:

| GPU load | GPU W | min duty at 83 °C | fan W | saved W | saved % |
|---:|---:|---:|---:|---:|---:|
| 40 % | 2,240 | 15.0 % | 40.7 | 840.2 | 95.38 % |
| 50 % | 2,800 | 15.0 % | 40.7 | 840.2 | 95.38 % |
| 60 % | 3,360 | 18.6 % | 52.1 | 828.9 | 94.08 % |
| 70 % | 3,920 | 25.7 % | 78.2 | 802.8 | 91.12 % |
| **80 %** | **4,480** | **35.3 %** | **122.5** | **758.5** | **86.10 %** |
| 90 % | 5,040 | 48.3 % | 207.3 | 673.7 | 76.47 % |
| 100 % | 5,600 | 67.0 % | 394.7 | 486.3 | 55.20 % |

The saving is not a constant. It is a function of the workload, and that is
the whole engineering problem.

### Throttling

Work is throttled by temperature on a piecewise curve: 100 % of the work up to
75 °C, declining linearly to 50 % at 90 °C.

| operating point (80 % GPU load) | die | duty | fan | saved | throughput cost |
|---|---:|---:|---:|---:|---:|
| throttle knee, target 83 °C | 83.0 °C | 35.3 % | 122.5 W | 86.10 % | **26.67 %** |
| throughput-safe, target 75 °C | 75.0 °C | 52.9 % | 244.9 W | 72.20 % | **0.00 %** |

The knee is the number that maximises the fan saving, and it destroys a
quarter of the work. The shipped operating point is the other end of the
trade: hold the die at the point where the GPU still runs at full boost, and
take whatever fan saving that allows. Reporting only the knee is how a fan
controller becomes a revenue-loss project.

### What the model gets wrong

It is a one-dimensional lumped model. It has no airflow sharing between
fans, no recirculation between the inlet and the die, no per-GPU variation, no
VRM or DIMM heating, and the throttle curve is a straight line that stands in
for NVIDIA's VBIOS behaviour. Its calibration point is a single steady state.
It is good enough to answer "what duty does this node need at this load, and
what does that cost" in order of magnitude, and it is not a substitute for a
thermal measurement on real hardware.

---

## 3. EKF and MPC

Both are adapted from upstream's quiet-lab design.

### Extended Kalman Filter

The filter estimates the hidden thermal states from noisy temperature
readings:

```
predict:  x⁻ = A·x,   P⁻ = A·P·Aᵀ + Q
update:   K   = P·Hᵀ / (H·P·Hᵀ + R),   x = x⁻ + K·(z − H·x⁻)
```

with `Q = 0.05·I` and `R = 1.0` for the single measured channel. Upstream
augments the state with the heat-transfer parameters so that the model learns
the machine online; this repository's implementation keeps the covariance
diagonal and does not learn the parameters. That is a deliberate reduction in
ambition, not an oversight.

### Model Predictive Control

The controller picks a fan duty by minimising a cost over a horizon:

```
cost = w_power · P_fan(u)
     + w_temp  · max(0, T_pred − T_target)²
     + w_noise · (Λ(u) − 1)²
     + constraint penalties
```

| term | weight | detail |
|---|---:|---|
| fan power | 1e-4 | `P_fan` from the calibrated law |
| temperature | 1.0 | target 75 °C, warning 85 °C, critical 95 °C |
| acoustics | 0.1 | `L = 40 + 50·log10(u)` dB, perceived loudness `Λ = 2^((L−40)/10)` sones |
| hard constraints | — | 50·(T−85)² and 10,000·(T−95)² |

Duty is searched over 25–100 %, matching upstream's minimum fan speed: below
that, a fan stalls.

The temperature prediction is deliberately simple: the cooling credit is
proportional to the duty above the 25 % floor. A real implementation would use
the learned model.

---

## 4. Fatigue

### 4.1 Counting cycles

`code/cycling.py` counts cycles the way the standard says to:
**ASTM E1049-85**, three-point rainflow.

A cycle closes when the newest segment is shorter than the one before it —
the path went X → Y → back through X, so X..Y is a closed loop. Equal ranges
are a continuing trend, not a cycle; treating them as cycles turns any
monotone ramp into noise. What remains on the stack is counted as half
cycles, the standard treatment of the residual.

Before counting, the signal is reduced to turning points and smoothed with a
five-sample moving average, so that sensor noise does not become fatigue
damage. Cycles below 1 °C are ignored.

Measured on this machine's own 1.67 h trace
(`data/telemetry-sample.csv`, replayable with
`uv run --no-project python code/cycling.py --replay data/telemetry-sample.csv`):

| | |
|---|---|
| full cycles | 109 |
| mean ΔT | 5.9 °C |
| max ΔT | 19.2 °C |
| cycle rate | 65.5 per hour |
| damage concentration | 15 % of cycles (10–20 °C) carry 55 % of the damage |

That Pareto shape is the only cycling claim this project can support: **the
damage is in the transients, not in the ripples.** A controller that holds the
die still removes the large swings first.

### 4.2 Damage per cycle

**Coffin-Manson** — the low-cycle fatigue law:

```
N_f ∝ ΔT^(−n)          n ≈ 2 for SAC solder (1.9–2.0)
damage = Σ count · ΔT^n
```

**Norris-Landzberg** — the mean-temperature acceleration term, on top of
Coffin-Manson:

```
N_f ∝ f^(−m) · ΔT^(−n) · exp(Ea / (k · T_max))
```

with `Ea = 0.1 eV`, `k = 8.6173e-5 eV/K`, `m = 1/3`. The per-cycle damage
carries `exp(−Ea / (k · T_max))`, so a cycle at the same amplitude hurts more
at a higher mean temperature.

**Miner's rule** — linear accumulation of damage:

```
D = Σ nᵢ / N_fᵢ        failure at D = 1
```

### 4.3 The ratio, and the scenario

The absolute damage number is model-dependent; the **ratio** between two
controllers on the same plant and the same workload is not. The simulator
runs stock, a bang-bang threshold controller, and this repository's MPC
against the same plant, and reports:

| damage model | reduction, controlled vs stock |
|---|---|
| Coffin-Manson | 1.3–1.8× |
| Norris-Landzberg | ≈2.0× |

The dollar leg of the model does **not** use that ratio. It uses a swing
scenario: `R = (ΔT_base / ΔT_ctrl)^n`, with a 12 °C → 2 °C swing, giving
R = 36. R = 36 is an **assumption**, and the audit says so out loud. The
honest number is the simulator's 1.3–1.8× range; R = 36 is the top of the
scenario.

The fatigue leg is also bounded, and the bound is the fastest way to kill a
bad claim:

```
max fatigue $/node/yr = afr · share · replacement
```

You cannot avoid more failures than occur.

---

## 5. PUE, applied to the saving

```
saved $/yr = ΔW × hours / 1000 × tariff × PUE
```

PUE multiplies the **saving**, not the facility load.

The reasoning: PUE is the ratio of total facility energy to IT energy. A watt
removed at the server is a watt removed from the IT load, and it is also a
watt removed from the cooling plant that was removing it. So the marginal
facility energy avoided is `ΔW × PUE`, not `ΔW`.

Applying PUE to the whole facility total — "the facility burns 1.4 × the IT
power, so we save 1.4 × ΔW" — arrives at the same number by a different route
and is wrong for the same reason: it double-counts the part of the overhead
that is not proportional to the load.

Two caveats, stated because the treatment is only first-order correct:

1. It assumes the removed heat was actually being removed by mechanical
   cooling, i.e. that the node is not on a liquid loop with a bypass.
2. It assumes the plant's PUE is **marginal**, not average. A facility whose
   average PUE is 1.4 because of a large chiller plant running at low load
   may have a marginal PUE closer to 1.0.

### The headline, from the model

```
duty      = 52.9 %          (modelled safe duty at 80 % GPU load, 75 °C die)
ΔW        = 635.9 W         (881.0 W uncontrolled -> 245.1 W controlled)
hours     = 8,760 h/yr
tariff    = $0.09/kWh
PUE       = 1.40

635.9 × 8760 / 1000 × 0.09 × 1.40 = $702.08 / node / year
```

At $0.09/kWh and PUE 1.4, a 1,000-node fleet of such nodes saves **$701,830
per year** in fan power, under a modelled fan tray wattage and a measured
fan-power curve from different hardware.

At the fleet case settings of $0.08/kWh and PUE 1.35 the same node is worth
**$601.57/node/yr**, which is the energy leg in `code/lambda_case.py` and
`code/together_case.py`.
