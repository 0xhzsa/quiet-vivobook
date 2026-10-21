# HOW IT WORKS

The complete technical account: what was built, how it works, why it is
built that way, what the maths is, what we measured versus what we modelled,
what each party gains, and what would change our mind.

Everything here is computed by `code/`. `code/audit.py` fails the build if a
number in this file drifts from the code.

---

## 1. What we built, and what we did not

**Built and running:**

- A closed-loop fan controller (`code/closed_loop.py`): an Extended Kalman
  Filter estimates the die temperature and the sensor bias, a Model Predictive
  Controller chooses the fan duty, and the first move of the horizon is
  applied. It runs against a lumped thermal model with a noisy sensor and a
  load that changes, and it is compared against constant-duty baselines.
- A thermal model of an 8-GPU air-cooled node (`code/thermal_model.py`):
  three nodes in series, solved to steady state, with the operating point
  derived rather than assumed.
- A calibrated fan power law (`code/fanlaw.py`): the power of a fan at a
  given duty, fitted to a real measurement, carrying its own uncertainty.
- A laptop measurement harness (`controller/fan-scan/scheme-ab.ps1`): a clean
  A/B on real hardware, with the work counted, not guessed.
- An independent auditor (`code/audit.py`): a second implementation in
  `Decimal` that can disagree, plus 12 module selftests.

**Not built, and not claimed:**

- We do not have an 8-GPU server. There is no BMC trace of a GPU node
  anywhere in this repository.
- We have never measured a fan. This machine has no fan telemetry: 0 of 256
  EC registers are non-zero, `Win32_Fan` is empty, there is no tachometer.
  The one fan measurement in the project is @0xAlcibiades' 120 W -> 15 W on a
  64-core CPU server.
- The thermal resistances, the 1 kW fan tray, the throttle thresholds and the
  75 °C full-boost point are all **assumptions**. They are listed in
  §4 and their effect is quantified.

---

## 2. The question

Kian Kyars' "From Watts to Tokens" (@neuralkian, @freeCodeCamp,
https://kiankyars.github.io/gigawatt/) follows one watt from the utility
grid to GPU transistors and back out as heat. The cooling chapter covers where
that heat goes.

The question this project asks is the next one: **the heat leaves through the
fans, and the fans cost watts. What happens to the work if you turn them
down?**

There is a naive answer, and it is wrong. The affinity law says fan power
goes as the cube of speed, so a duty cut from 95 % to 35 % removes 95 % of
the fan power. Quiet-lab measured 87.5 % on a real server. Every number in
this repository is downstream of that 7.5-point gap.

---

## 3. How it works, end to end

```
   BMC sensor (noisy, drifts)
            |
            v
   +------------------+     estimates die temperature and the
   |       EKF        |     sensor bias from the plant model
   +------------------+
            |
            v
   +------------------+     rolls the plant forward over a 300 s
   |       MPC        |     horizon for candidate duties
   +------------------+
            |
            v
      fan duty 0..1
            |
            v
   +------------------+     duty -> airflow -> convection -> die temp
   |  thermal model   |     die temp -> work rate (throttle curve)
   +------------------+
```

**The sensor.** A die-temperature reading with Gaussian noise and a slowly
drifting bias. Real BMC sensors are like this, and a controller that only
works with a perfect sensor is a spreadsheet, not a controller.

**The EKF.** State is `[die_temp, hs_temp, inlet_temp, bias]`. The process
model *is* the plant - `thermal_model.ServerThermalModel.step` - and the
Jacobian is computed by finite differences on that same function, so the
filter can never drift away from the physics it is estimating. The
measurement matrix is `H = [1, 0, 0, 1]`: the sensor reads the true
temperature plus the bias plus noise. Estimating the bias is the point: a
controller that chases a drifting sensor changes the duty for no reason.

**The MPC.** At each control step it rolls the plant forward for a 300 s
horizon at each of 21 candidate duties, and picks the lowest cost:

```
cost = sum over horizon of  w_temp * max(0, T - target)^2 * dt
     +                              500 * max(0, T - critical)^2 * dt
     + w_power * fan_power(duty) * horizon_s
     + w_change * |duty - previous_duty|
```

The horizon is 300 s because the plant's dominant time constant is about
100 s. An 8-second horizon - which is what the first implementation used -
cannot see the consequence of a duty change, and the controller freezes at
one value. That was a real bug, found by instrumenting the duty trace.

The duty rate limit (0.02 per second) exists because a real BMC fan curve
cannot teleport the fans. It is also why the closed loop peaks slightly above
its target: that is a property of the actuator, not a bug in the controller.

**The plant.** `die -> heatsink -> inlet -> ambient`, three nodes with real
thermal masses, plus a case air path. Only the convection path scales with
airflow (`duty^0.8`); the TIM/spreader path and the case path do not.

**The work.** Die temperature maps to throughput through the throttle curve
(§4.3). This is the term that turns a fan saving into a throughput cost.

---

## 4. The physics, and where every number comes from

### 4.1 Fan power

The affinity law for a fixed impeller: airflow ~ N, pressure ~ N^2, shaft
power ~ N^3. Real fan motors break it in three ways:

1. Motor losses put a floor under the electrical input that does not vanish
   with speed.
2. Bearing and windage losses grow with speed at a different exponent.
3. Drive electronics draw a roughly speed-independent quiescent current.

So the model is affine-cubic:

```
P(d) = base * (a*d^3 + b*d) / (a + b)
```

with `a = 1.0` fixed and `b` solved from a measured pair:

```
120 W at 90 % duty  ->  15 W at 30 % duty
120/15 = 8 = (0.9^3 + 0.9b) / (0.3^3 + 0.3b)
        = (0.729 + 0.9b) / (0.027 + 0.3b)
0.729 + 0.9b = 0.216 + 2.4b
b = 0.342
```

and the implied power at 100 % duty is `120 * (1+b) / (0.729 + 0.342*0.9) =
155.3 W`.

**The honest part.** quiet-lab states duty *ranges* ("80-100 %" and
"25-35 %"), not points. We used the midpoints 90 % and 30 %. Across the
ranges quiet-lab actually states, `b` spans **0.085 to 0.875** - a 10x
spread - and the fan saving at the shipped duty spans **54.4 % to 74.5 %**
instead of a single 72.2 %. `code/fanlaw.py:saving_band()` returns that
band and the selftest asserts the pure cubic lies *above* it, which is the
point of the band: it is not a way to rescue the cubic, it is a way to
exclude it.

### 4.2 The thermal model

At steady state every path carries the same power P, because the only
source is the GPU and the only sink is ambient. The three resistances are in
series:

```
die - hs    = P * r_die_hs          (TIM + copper spreader, no airflow term)
hs  - inlet = P * r_hs_air / h      (fin array, h = duty^0.8)
inlet - amb  = P * r_air_amb        (case exhaust path, no airflow term)
```

so the die temperature has a closed form. The closed form is verified
against the time-domain integration, and the model must converge - the
first version used an integrator for the inlet, which has no equilibrium,
so every "steady state" number taken from it was a fiction.

The resistances are **assumptions**, anchored to one number: a dense 8x700 W
node at 95 % duty and full GPU load should hold a die temperature near
77 °C. One anchor, three free parameters, no residual.

### 4.3 The throttle curve

```
work_fraction(T) = 1.0                                     for T <= 75 C
                 = 1.0 - (T-75)/15 * 0.5                   for 75 C < T < 90 C
                 = 0.5                                     for T >= 90 C
```

**75 C is an assumption, not a citation.** It is the single number the
"zero throughput cost" claim hangs on, and moving it 5 °C moves the
headline by 13 points of fan saving. `code/thermal_model.py` exposes it as
a named constant so the assumption is visible rather than buried.

### 4.4 The operating point

The duty that holds a target is found by bisection on the closed form, and
it is **derived**, not hard-coded. `code/thermal_model.py:shipped_duty()`
is imported by `case.py`, `lambda_case.py`, `together_case.py` and
`modal_case.py`, and `code/audit.py` checks the *derivation* - so if the
thermal model changes, the fleet numbers move with it.

At 80 % GPU load and 25 °C inlet:

| operating point | duty | fan saved | work cost |
|---|---|---|---|
| throughput-safe (75 °C) | 52.9 % | 72.2 % (band 54.4-74.5 %) | 0.00 % |
| throttle knee (83 °C) | 35.3 % | 86.1 % | 26.7 % |

**The knee is where the fan saving is largest and the throughput cost is
worst.** Quoting only the knee is how a fan controller becomes a
revenue-loss project.

### 4.5 The answer depends on the room

At 80 % GPU load, the throughput-safe fan saving:

| inlet ambient | safe duty | fan saved |
|---|---|---|
| 18 °C | 36.8 % | 85.1 % |
| 21 °C | 42.5 % | 81.2 % |
| 24 °C | 49.9 % | 75.1 % |
| 27 °C | 60.0 % | 64.4 % |
| 30 °C | 74.4 % | 43.6 % |

A 5 °C change in inlet moves the answer by 20 points. A real row sees
18-30 °C. A single headline number without this table is a number without
a meaning - and the table is also the thing that makes the measurement
worth taking: inlet temperature is on the BMC.

### 4.6 The throughput cost, in both regimes

A fan controller does not create work, it moves the constraint. Losing
5.15 % of the work costs money only if the work would have been sold:

- **Spare capacity** (utilization < 1): the work that did not happen was
  work the node could not have sold anyway. Immediate revenue cost is $0.
  What you lose is headroom.
- **Capacity-constrained** (utilization = 1): every GPU-hour the cluster
  cannot deliver is one the customer was going to pay for. The loss bills
  back at list price.

On an 8-GPU node at $3.99/GPU-hour and 60 % utilization, the gross revenue
basis is `$167,772/node/yr`. A 5.15 % loss against that is $8,640 - more
than the $702 fan saving. This is the term the first version of this model
left out, and leaving it out is what turned a capacity project into a
revenue-loss project.

---

## 5. Is it better? Measured against itself

The controller is compared against the **cheapest constant duty that holds
the same peak temperature** - not the coolest one, and not the most
expensive one, because those answer a different question.

1800 s of varying load, noisy sensor with a drifting bias:

| policy | mean die | peak die | fan power |
|---|---|---|---|
| open loop 50 % | 66.79 °C | 74.55 °C | 220.6 W |
| open loop 60 % | 64.47 °C | 71.84 °C | 313.9 W |
| open loop 100 % | 59.45 °C | 66.02 °C | 1000.0 W |
| **closed loop (EKF + MPC)** | **70.04 °C** | **77.62 °C** | **159.8 W** |

**27.6 % less fan power at the same peak temperature.** The closed loop is
also the only policy that tracks a load that changes, and it is the only
one that can use 160 W when the node is idle and 800 W when a job starts.

The test can fail, and it did. Before the duty rate limit was added, the
controller oscillated between 25 % and 100 % and spent more fan power than
the constant duty. That is in the git history.

---

## 6. What we gain

Per 8-GPU node at the throughput-safe duty, 80 % GPU load, $0.08/kWh,
PUE 1.35:

```
saved watts        636.1 W   (1,000 W tray at 95 % -> 244.9 W at 52.9 %)
annual energy      5.57 MWh
annual cost       $601.78 / node / yr
```

Fan tray sensitivity - the tray wattage is the biggest single input and it is
**assumed**:

| tray | saved W | $/node/yr |
|---|---|---|
| 600 W | 381.6 | $421 |
| 800 W | 508.9 | $562 |
| 1,000 W (assumed) | 636.1 | $702 |
| 1,200 W | 763.3 | $842 |
| 1,500 W | 954.1 | $1,053 |

And the closed loop adds a further 27.6 % on top of any fixed duty, because
it stops paying for full speed while the node is idle.

**What we do not gain:** the fatigue leg. It is assumption-driven (annual
failure rate, attribution share, replacement cost) and it is reported
separately at 1.3-1.8x, never as the headline.

---

## 7. What each party gains

The physics is identical everywhere. What differs is who holds the fan tray
and who pays the meter. That is the whole point of the table below: it is
not a verdict on any company, it is a statement about where a dollar would
land.

| party | annual fan bill at the throughput-safe duty | what they have to do | what they gain |
|---|---|---|---|
| **Lambda** (@stephenbalaban, @LambdaAPI) | $707,692/yr energy at ATL02, $1.43M/yr with the fatigue leg | BMC access at Atlanta, one A/B/A | a utility line item falls; capacity MW is freed |
| **Together** (@vipulved, @togethercompute) | $601,779/yr energy on 8k air-cooled | confirm whether the meter is theirs or **@hypertec**'s | depends entirely on a question only they can answer |
| **@hypertec** | up to the same $601,779/yr if they hold the meter | confirm ownership of the H100/H200 fleet | the same physics, a different letterhead |
| **Modal** (@bernhardsson, @modal) | $0 to Modal; $7,312,387/yr at its 13 node providers | a fan-telemetry term in its provider contracts | Modal's leverage is utilization ($416,666,667/yr gross), not fans |
| **@EdgeConneX** | Lambda's Atlanta site | landlord for the site | lower the load in the row they lease out |
| **@0xAlcibiades** | already has the measurement | nothing | the method is used, and the physics is credited |
| **@neuralkian** / **@freeCodeCamp** | - | nothing | the cooling chapter gets a worked example |

**What everybody gets:** the physics is public, the code is public, the
measurement method is public, and the next node does not have to re-derive
it. The only thing anyone has to supply is one BMC trace.

---

## 8. How we did all of this

**The measurement method** (`docs/METHOD.md`). A/B/A, because a single A/B
cannot distinguish "B is slower" from "the machine got slower". Confounds
controlled explicitly: thermal history (fixed cooldown), baseline drift
(alternating order so monotone drift cancels), order effects (paired
blocks), EcoQoS and child-process pinning (the load runs in-process, on
real threads, with a completed-work counter that cannot be faked by a
faster clock on idle threads), mode drift (read back every sample), governor
interference (paused for the duration), battery state (AC required, the
harness refuses to run otherwise). A run is invalidated rather than
reported if the work counter stalls, the temperature goes null, the mode
drifts, or the steady window is too short.

**The laptop harness** (`controller/fan-scan/scheme-ab.ps1`). Power schemes
only, so it needs no elevation and cannot leave a machine in a bad thermal
state. The original scheme is restored in `finally`. The confounded
thermal-mode run is committed with the reason it failed, because deleting
bad runs is how a project starts lying.

**The audit** (`code/audit.py`). A second implementation of the fan law in
`Decimal` that does not import `code/fanlaw.py`, so a change that is wrong
still gets caught. It re-derives every fleet number and compares against
the modules. It also checks the documentation: a documented number that
drifts from the code is a hard failure, and so is the reappearance of the
verdict language this project removed.

**The self-review** (`SELF-REVIEW.md`). We tried to break our own work and
published the eleven defects we found, including the ones that were
mislabelled as validation, the untested firmware-writing harness, the
one-parameter fan law, the constant that came from an invalid transient
run, and the controller that was dead code. A project that publishes its
own defects is worth more than one that pretends it has none.

---

## 9. What would change our mind

| if this turns out to be true | then |
|---|---|
| a real 8-GPU BMC trace shows a fan saving materially outside 54.4-74.5 % | the fan law is wrong; it gets refitted |
| the same trace shows a safe duty materially different from 52.9 % | the thermal resistances are wrong; they get refitted |
| a measured throughput cost above 0 % at the shipped duty | the throttle curve is wrong; the headline changes |
| a real node cannot hold 75 °C at 52.9 % duty | the shipped duty is unsafe; it gets raised |
| the 1 kW fan tray is not a fan tray | every dollar figure scales down by the same factor |
| the quiet-lab duty ranges are not the actual operating points | the band narrows or shifts; `b` is recomputed |

Each of these is a measurement somebody can take with a BMC and a stopwatch.
None of them require believing us.

---

## 10. Run it yourself

```bash
uv run --no-project python code/fanlaw.py                    # the law and its band
uv run --no-project python code/thermal_model.py              # the envelope
uv run --no-project python code/closed_loop.py                # the experiment
uv run --no-project python code/server_thermal_controller.py # the operating point
uv run --no-project python code/audit.py                     # the auditor
```

On the machine (PowerShell, no elevation needed for the A/B):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File controller/fan-scan/scheme-ab.ps1 `
  -LoadSec 60 -SteadySec 40 -BetweenSec 45 -Threads 8
```

On a real node, the protocol is in `docs/REPRODUCE.md`: read FanPower via
BMC, set duty via IPMI raw `0x30 0x70 0x66`, hold a fixed workload,
A/B/A for 30 days, count work and watts.
