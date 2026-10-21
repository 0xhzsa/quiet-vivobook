# quiet-vivobook

A closed-loop thermal controller for a machine that refuses to expose its fan —
plus the arithmetic behind the "7 figure savings" claim, and the conditions
under which that claim is **false**.

> "while this is fun for something like a homelab, applied at scale you'd be
> looking at 7 figure savings for a bare metal deployment because of reduced
> fan power consumption and thermal cycling."
> — @0xAlcibiades, 2025-07-06

**Repo:** https://github.com/0xhzsa/quiet-vivobook

This repo takes that sentence seriously enough to try to break it.

## The one number

At **$0.09/kWh, PUE 1.4**, an air-cooled 8-GPU node with a 1 kW fan tray,
controlled from 95 % to 35 % duty:

```
950 W saved × 8,760 h × $0.09/kWh × 1.4 = $1,048 / node / year
```

**Every 1,000 nodes is ~$1.05M/yr in fan power alone** under the ideal affinity
law. The only real server measurement in the upstream project is **120 W → 15 W
(−87.5 %)**, not the 95 % the cubic predicts. At 1 kW that is **875 W**, or
**$966/node/yr** — **~$0.97M per 1,000 nodes**. Use the **875–950 W** range:
the seven-figure line is **~954–1,036 nodes**, not a comfortable margin. 24,000
H100s (3,000 eight-GPU nodes) is **~$2.9–3.1M/yr**. No fatigue assumptions
required.

The fatigue (thermal cycling) leg is a second, conditional term — and it is
capped. The base case uses a **12 °C → 2 °C swing scenario (R=36)**; the
package's own laptop cycle simulator finds **1.3–1.8× Coffin-Manson damage
reduction**, not 36×. The Norris-Landzberg correction can reach ~2.0×; the model uses the
Coffin-Manson range. Quote the range, not the best case. The full falsification
is in `CASE-STUDY.md`.

## What is measured, what is modelled

| | status |
|---|---|
| laptop package power / temperature | **measured** (`data/profiles.csv`) |
| laptop throughput | **logged, indicative** — single sequential run, not a controlled A/B |
| controller behaviour, actuator write + read-back | **measured** (`controller/fan-scan/`) |
| server fan power per node | **modelled** — 60 W to 1 kW by node class |
| PUE, tariff | **parameters**, not measurements |
| annual failure rate, cycling attribution, replacement cost | **assumptions** — named, bounded |
| server fan RPM, dBA, field failure data | **not measured** |
| Lambda fleet, site and price | **public** — 18,000 lease; ATL02 12 MW; $3.99/GPU-hr |
| Together air-cooled count and ownership share | **not public** — scenario and contract question |
| Modal GPU count | **derived from ARR** — scale estimate, not an upper bound; lower price or utilization raises it |

No number here is presented as a measurement when it is a model input.

## The falsification, in one table

4-GPU node, $670.75/node/yr base case:

| fleet | $/node needed | fan alone gives | verdict |
|---|---|---|---|
| 500 | $2,000 | $415.54 | **impossible** — needs 211 % of failures to be cycling-caused |
| 1,000 | $1,000 | $415.54 | **impossible** — needs 78 % |
| 5,000 | $200 | $415.54 | **met by fan power alone** |

The claim is a **scale** claim. It is arithmetically false for a homelab and
for a few hundred servers. It becomes true where the fan leg alone clears the
target, around **2,400 4-GPU nodes** or **950 8-GPU nodes**.

## Three founder-led cases: one qualified, one conditional, one disqualified

The first case proves the claim on a fleet with no founder attached. The next
three point it at founders. The arithmetic is the same; the verdicts are not.
The founder cases use **$0.08/kWh, PUE 1.35**; the generic fan example above
uses **$0.09/kWh, PUE 1.4**.

| target | anchor | direct saving | capacity value | verdict |
|---|---|---:|---:|---|
| **Lambda** (@stephenbalaban) | ATL02 12 MW, 9,408 GPUs | **$1.23–1.39M/yr** | **$18.3M/yr** | **qualified** |
| **Together** (@vipulved) | 8,000 H100/H200, 1,000 nodes | **$1.04–1.18M/yr** at 100 % owned | **$15.6M/yr** | **conditional** |
| **Modal** (@bernhardsson) | ≈48,177 derived / 48,176 modeled | **$0** to Modal | **$0** to Modal | **disqualified** |

At the **R=36 best case**, the direct figures rise to **$1.78M** for Lambda ATL02
and **$1.51M** for Together at 100 % owned. Those are the top of the scenario,
not the 1.3–1.8× range.

- **Lambda** is the cleanest case: an operating air-cooled site, a public price
  list, and a founder who can check a BMC. The 18,000-GPU lease is **$2.35–2.65M/yr**
  direct at 1.3–1.8× if the whole lease is air-cooled; R=36 takes it to $3.40M.
  The ATL02 energy leg alone is
  **$1.06M/yr** at 1 kW and the ideal cubic; at the measured 87.5 % fan curve it
  is **$0.97M**, so the seven-figure verdict needs either the ideal fan curve or
  a small fatigue credit. It does not need the R=36 best case.
- **Together** is the conditional: the 36,000-GPU headline is liquid and
  contributes zero. The claim lives in the air-cooled H100/H200 fleet, and only
  routes to Together on the share whose power it pays for. At 8,000 GPUs the
  energy leg is **$0.90M**; it needs **66.2 %** ownership at R=36, but
  **~85–96 %** at the simulator's 1.3–1.8×. The honest boundary is
  **~6,800–7,700 owned GPUs**, not one point.
- **Modal** is the no: it owns no data centers and no nodes. The fan bill behind
  its $1B ARR is real — about **$6.3–7.1M/yr**, **0.63–0.71 %** of revenue at
  1.3–1.8×; **$9.1M / 0.91 %** at R=36 — but it belongs to 13 capacity providers.
  Utilization is a different business:
  gross revenue at list price is not a like-for-like saving.

The full comparison, the three falsifiers, and the ownership test are in
`THREE-CASES.md`. Each case has its own code and self-tests.

## Quickstart

```powershell
uv run python code/case.py --selftest     # 12 checks on the algebra
uv run python code/case.py                # the composed case
uv run python code/case.py --tariff 0.12  # re-price it
uv run python code/cycling.py --replay data/telemetry-sample.csv
uv run python code/fleet_model.py         # standalone fan-power model
uv run python code/targets.py --selftest  # 12 checks on fleet arithmetic
uv run python code/targets.py             # per-fleet table
uv run python code/lambda_case.py --selftest    # 13 checks on the Lambda case
uv run python code/lambda_case.py               # three legs, sites, sensitivity
uv run python code/lambda_case.py --ratio 1.5   # honest swing-ratio case
uv run python code/together_case.py --selftest  # 16 checks on the Together case
uv run python code/together_case.py             # three legs, ownership, boundaries
uv run python code/modal_case.py --selftest     # 17 checks on the Modal case
uv run python code/modal_case.py                # derived fleet, pass-through, utilization
uv run python code/portfolio.py --selftest      # 10 checks on the three verdicts
uv run python code/portfolio.py                 # the three cases side by side
uv run python code/audit.py                     # independent Decimal + provenance audit
uv run python code/audit.py --strict            # fail on provenance warnings too
```

The controller (Windows, ASUS Vivobook X1502VA) — source is included, but it
needs `LibreHardwareMonitorLib.dll` at `controller\tools\lhm\` first. See
`controller/README.md`; the safety model is documented there and the write path
is proven before it changes anything.

```powershell
.\controller\fan-scan\run.ps1        # read-only sensor map (elevated)
.\controller\fan-scan\run-devs.ps1   # prove the write path, restore after
.\controller\install.ps1             # install the governor as a scheduled task
```

## Layout

```
CASE-STUDY.md        the full argument, equations and failure conditions
THREE-CASES.md       the three founder cases side by side, and the verdicts
LAMBDA-CASE.md       case 2: Lambda, qualified, three legs
TOGETHER-CASE.md     case 3: Together, conditional on ownership
MODAL-CASE.md        case 4: Modal, disqualified (no fans of its own)
LAMBDA-OUTREACH.md   draft X posts for @stephenbalaban + @LambdaAPI (not posted)
THREE-OUTREACH.md    drafts for all three founders (not posted)
TARGETS.md           who this is for, and why liquid-cooled fleets are excluded
X-THREAD.md          the public thread, with the ask
code/case.py         both legs, break-even, sensitivity, falsification
code/cycling.py      rainflow / Coffin-Manson / Norris-Landzberg / Miner
code/fleet_model.py  fan affinity model, standalone
code/lambda_case.py  Lambda energy / fatigue / capacity model, self-tested
code/together_case.py Together model, with the ownership term, self-tested
code/modal_case.py   Modal pass-through / qualification model, self-tested
code/portfolio.py    the three verdicts, self-tested
code/audit.py        independent Decimal, upstream, fatigue and throughput audit
code/targets.py      fleet-size arithmetic, self-tested
data/profiles.csv    measured laptop profile table
data/telemetry-sample.csv  the trace the cycle counts came from
controller/          the Windows controller (governor, actuator, harnesses)
controller/README.md safety model, encoding trap, and what it cannot measure
```

## The ask

The model's load-bearing unknowns are **how many watts a real fan tray draws**
and **who pays for it**. If you operate air-cooled GPU nodes, one of these
replaces the first with a measurement:

1. a BMC fan-power sensor reading (`FanPower`, `P12V_FAN`, or a per-fan watt
   reading) from one node, or
2. a 30-day trace of fan duty and node power.

The second is a contract question: if you do not pay the meter, the saving is
your landlord's. That is the difference between the Lambda and Modal cases.

Everything else in this repo already runs.

## Status

- Laptop controller: **working** — MPC over power profiles, plus a 3-state ASUS
  thermal-policy actuator (`0` balanced, `1` silent, `2` overboost) with
  read-back verification and baseline restore.
- Fleet model: **arithmetic working**, self-tested. The three founder cases plus
  the portfolio script are 56 checks; the original model adds 41. `audit.py`
  independently re-derives the headlines and flags the unsupported claims:
  the upstream 120→15 W curve is not the ideal cubic, `case.py`'s R=36 is not
  the cycle simulator's 1.3–1.8× Coffin-Manson range, and the controller's
  77–81 % work retention is not debited.
- Field validation: **not done**. That is what the ask is for.
