# quiet-vivobook

A closed-loop thermal controller for a machine that exposes no fan telemetry,
and the arithmetic behind the "7 figure savings" claim — including the
conditions under which that claim holds and the conditions under which it is
arithmetically false.

> "while this is fun for something like a homelab, applied at scale you'd be
> looking at 7 figure savings for a bare metal deployment because of reduced
> fan power consumption and thermal cycling."
> — @0xAlcibiades, 2025-07-06

**Repo:** https://github.com/0xhzsa/quiet-vivobook

**What this is.** Measured: this laptop's actuator write/read-back path, its
four power profiles, and a four-block paired A/B of the Quiet against the
Balanced power scheme (6.92 % throughput cost). Measured elsewhere: 120 W →
15 W of fan power on a 64-core Ampere CPU server (87.5 % cut, upstream project
[quiet-lab](https://github.com/0xAlcibiades/quiet-lab)). Modelled: the 8-GPU
node, its thermal behaviour, the fatigue leg, and every fleet dollar figure.
No fan wattage, tariff, PUE, failure rate or replacement cost in this repo is
a measurement of a server.

## Status

Provenance is one of four words, and it is used strictly:

- **measured** — taken from this machine, from a committed artifact, or from a
  cited upstream measurement.
- **simulated** — produced by a model in this repo (the 8-GPU node, the
  fatigue simulator).
- **public** — published by a third party (fleet sizes, prices, ARR).
- **assumed** — a modelling input, named and bounded, with no measurement
  behind it.

| claim | value | provenance | where it comes from |
|---|---|---|---|
| Laptop throughput cost, Quiet vs Balanced power scheme | 6.92 % (Quiet keeps 93.08 % of the work; per-block range 88.4–99.2 %) | measured | `controller/fan-scan/scheme-ab.ps1`, artifact `controller/fan-scan/scheme-ab-latest-summary.json` |
| Laptop thermal-mode A-B-A run | invalid, kept in the repo | measured, rejected | `controller/fan-scan/RESULTS.md`, `controller/fan-scan/mode-20261020-160330/summary.json` |
| Laptop profiles, 20-thread load on AC | stock 25.3 W / 82.2 °C; efficient 17.9 W / 72.5 °C; no-turbo 10.7 W / 67.7 °C; floor 8.7 W / 64.5 °C | measured, single sequential run | `data/profiles.csv` |
| Server fan power at idle | 120 W → 15 W, a 87.5 % cut; 65 → 42 dB | measured, upstream | @0xAlcibiades, [quiet-lab](https://github.com/0xAlcibiades/quiet-lab) (MIT) — 64-core Ampere Altra, CPU server, not a GPU node |
| Fan power law, 95 % → 35 % on a 1 kW tray | 86.25 % cut (881.0 W → 121.1 W); the pure affinity law says 95 % | modelled, fitted to the measurement | `code/fanlaw.py` |
| 8-GPU node, 80 % GPU load, die held at 75 °C — the shipped operating point | duty 52.9 %; fan 881.0 W → 244.9 W; **72.20 %** of fan power saved; **0.00 %** throughput cost | simulated, calibrated | `code/server_thermal_controller.py --node gpu8 --target-temp 75` |
| 8-GPU node at the 83 °C throttle knee | duty 35.3 %; **86.10 %** saved; **26.67 %** throughput cost | simulated | `code/server_thermal_controller.py --node gpu8` |
| Model against the upstream measurement | 86.10 % modelled vs 87.5 % measured — 1.4 points apart | cross-check | the same command, and the self-test that asserts it |
| Throughput-cost ledger | 0.00 % at the shipped duty; 26.67 % at the 83 °C knee; 6.92 % measured on the laptop; 20.60 % (laptop MPC) | simulated, and measured for the laptop | `code/throughput.py` |
| Fatigue damage reduction, controlled vs stock | 1.3–1.8× Coffin-Manson; ≈2.0× with the Norris-Landzberg mean-temperature term | simulated | `code/cycling.py` (17 self-tests) |
| Lambda ATL02, 1,176 nodes | energy $707,449/yr; $0.88–1.04M/yr at 1.3–1.8×; $1,427,749/yr at R=36 | modelled | `code/lambda_case.py`, `code/portfolio.py` |
| Together, 8,000 air-cooled GPUs, 100 % owned | energy $601,572/yr; $0.75–0.88M/yr at 1.3–1.8×; $1,214,072/yr at R=36 | modelled, conditional on ownership | `code/together_case.py`, `code/portfolio.py` |
| Modal | $0 to Modal (the fan bill behind its ARR belongs to 13 capacity providers) | modelled | `code/modal_case.py` |
| Fan tray wattage | 1,000 W on a dense 8-GPU node | assumed | `code/case.py`, `NodeClass.fan_w` |
| Tariff, PUE | $0.08–0.09/kWh, PUE 1.35–1.40 | assumed | parameters of the case scripts |
| Annual failure rate, cycling attribution, replacement cost | 3 %/yr, 35 %, $25k–$60k per node | assumed, bounded | `code/case.py`; the fatigue leg cannot exceed `afr × share × replacement` |
| Thermal swing ratio R = 36 | a 12 °C → 2 °C scenario, **not** the simulator's 1.3–1.8× | assumed | `CASE-STUDY.md` §3 |
| Server fan RPM, dBA at 8-GPU scale, field failure data | — | not measured | — |
| Lambda / Together fleet size, price, ownership share | 18,000-GPU lease; ATL02 12 MW; $3.99/GPU-hr; ~48k GPUs derived from Modal ARR | public | `LAMBDA-CASE.md` §11, `TOGETHER-CASE.md` §11, `MODAL-CASE.md` §11 |

## The claim, decomposed

The quote has two legs and one missing word: **scale**.

| leg | method | unit | status |
|---|---|---|---|
| fan energy | the calibrated affine-cubic law, not the raw affinity law | $/node/yr | physics, one uncertain input (the fan tray wattage) |
| thermal fatigue | swing-ratio scenario; rainflow simulator in `code/cycling.py` | $/node/yr | conditional on three assumptions, and R is not measured |
| composition | sum, then solve for fleet size | $/yr | arithmetic |
| throughput cost | 0.00 % at the shipped duty, 26.67 % at the throttle knee, 6.92 % measured on the laptop | $/node/yr | debited against the saving, see `code/throughput.py` |

The saving is **not a constant**. It is a function of GPU load, because the
duty that holds the die temperature rises with the load. At $0.09/kWh and
PUE 1.4, an air-cooled 8-GPU node with a 1 kW fan tray, uncontrolled at 95 %
duty and controlled at the modelled safe duty of 52.9 %:

```
635.9 W saved × 8,760 h × $0.09/kWh × 1.4 = $701.83 / node / year
```

PUE multiplies the *saving*, not the facility load: a watt removed at the
server also removes its share of cooling overhead.

Per node, at $0.09/kWh and PUE 1.4, with the shipped duty:

| node class | fan base | duty | saved W | fan $/yr | cycling $/yr | total $/yr | nodes for $1M |
|---|---|---|---:|---:|---:|---:|---:|
| Vivobook 15 (client) | 2.5 W | 100 % → 55 % | 1.8 | $2.03 | $6.67 | $8.70 | 114,980 |
| 1U CPU node | 60 W | 80 % → 35 % | 27.9 | $30.75 | $76.56 | $107.31 | 9,319 |
| 4-GPU node | 400 W | 90 % → 52.9 % | 211.0 | $232.87 | $255.21 | $488.08 | 2,049 |
| 8-GPU dense node | 1,000 W | 95 % → 52.9 % | 635.9 | $701.83 | $612.50 | $1,314.33 | 761 |

The claim is a scale claim. Below the fleet size where fan power alone clears
the target, the fatigue leg is arithmetically irrelevant — and the fatigue leg
is an assumption, not a measurement. `CASE-STUDY.md` §5 has the fleet-size
boundaries; `THREE-CASES.md` applies the same arithmetic to three real
fleets and gets three different answers:

| fleet | energy leg | 1.3–1.8× Coffin-Manson | at R=36 | verdict |
|---|---:|---:|---:|---|
| Lambda ATL02, 1,176 nodes | $707,449/yr | $0.88–1.04M/yr | $1,427,749/yr | **qualified** |
| Together, 8,000 air-cooled GPUs, 100 % owned | $601,572/yr | $0.75–0.88M/yr | $1,214,072/yr | **conditional** |
| Modal | $0 to Modal | $0 to Modal | $0 to Modal | **disqualified** |

At the shipped duty, Together at 8,000 GPUs needs **134 %** of the fleet's fan
power at 1.3× and **113 %** at 1.8× to reach $1M — so the eight-thousand-GPU
case only clears seven figures at the R=36 scenario (82.4 % ownership). The
honest boundary is a range, not a point.

**What changed in the recalibration.** The first version of this repo used
the pure affinity law at a fixed 95 % → 35 % duty. That duty is the throttle
knee: it holds the die at 83 °C and costs 26.7 % of the work. The model now
solves for the duty that holds 75 °C, where the GPU still runs at full boost,
and the fan law is the affine-cubic fitted to the upstream measurement rather
than the naive cubic. The case studies, the thread and every number above
were regenerated from the same code. `code/audit.py` §8 pins the strings so a
later edit to any one document fails the audit rather than drifting.

## Quickstart

Python, no dependencies beyond the standard library. `uv run --no-project`
runs the scripts without creating a project environment; `uv run python ...`
works too.

```powershell
# verification
uv run --no-project python code/audit.py           # independent Decimal + provenance audit
uv run --no-project python code/audit.py --strict  # also fails on provenance warnings

# self-tests
uv run --no-project python code/fanlaw.py --selftest                 # 15 checks, fan power law
uv run --no-project python code/cycling.py --selftest                # 17 checks, rainflow + fatigue
uv run --no-project python code/case.py --selftest                   # 16 checks, the composed case
uv run --no-project python code/targets.py --selftest                # 12 checks, fleet arithmetic
uv run --no-project python code/lambda_case.py --selftest            # 13 checks, Lambda case
uv run --no-project python code/together_case.py --selftest          # 16 checks, Together case
uv run --no-project python code/modal_case.py --selftest             # 17 checks, Modal case
uv run --no-project python code/portfolio.py --selftest              # 10 checks, the three verdicts
uv run --no-project python code/throughput.py --selftest             # 21 checks, throughput cost
uv run --no-project python code/server_thermal_controller.py --selftest  # 11 checks, the 8-GPU model

# the numbers
uv run --no-project python code/case.py                              # per node, per year
uv run --no-project python code/case.py --tariff 0.12                # re-price it
uv run --no-project python code/fleet_model.py                       # standalone affinity-law model
uv run --no-project python code/cycling.py --replay data/telemetry-sample.csv
uv run --no-project python code/fanlaw.py                            # calibrated fan law vs cubic
uv run --no-project python code/throughput.py                        # the cost side of the trade
uv run --no-project python code/lambda_case.py                       # three legs, sites, sensitivity
uv run --no-project python code/together_case.py                     # three legs, ownership, boundaries
uv run --no-project python code/modal_case.py                        # derived fleet, pass-through
uv run --no-project python code/portfolio.py                         # the three verdicts side by side
uv run --no-project python code/server_thermal_controller.py --node gpu8
uv run --no-project python code/server_thermal_controller.py --node gpu8 --target-temp 75
```

`code/audit.py` exits 1 when there are hard arithmetic failures, and
`--strict` makes it exit 1 on provenance warnings too. The expected output
ends with `0 hard failure(s), 0 warning(s)`. It is not a snapshot test: it
recomputes the headlines in `Decimal` and then checks the claims the modules
cannot prove.

The controller is Windows-only, model-specific, and needs
`LibreHardwareMonitorLib.dll` at `controller\tools\lhm\` (not vendored here —
see `controller/README.md`). Read-only first:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File controller/fan-scan/run.ps1        # sensor map, elevated
powershell -NoProfile -ExecutionPolicy Bypass -File controller/fan-scan/run-devs.ps1   # prove the write path, restore after
powershell -NoProfile -ExecutionPolicy Bypass -File controller/fan-scan/scheme-ab.ps1  # the clean laptop A/B, no elevation
powershell -NoProfile -ExecutionPolicy Bypass -File controller/install.ps1             # install the governor
powershell -NoProfile -ExecutionPolicy Bypass -File controller/report.ps1              # report
```

## Repository layout

```
README.md              this file
CASE-STUDY.md          the full argument, the equations and the failure conditions
THREE-CASES.md         the three founder cases side by side, and the verdicts
LAMBDA-CASE.md         case 2: Lambda, qualified, three legs
TOGETHER-CASE.md       case 3: Together, conditional on ownership
MODAL-CASE.md          case 4: Modal, disqualified (no fans of its own)
TARGETS.md             who this is for, and why liquid-cooled fleets are excluded
LAMBDA-OUTREACH.md     draft X posts for @stephenbalaban + @LambdaAPI (not posted)
THREE-OUTREACH.md      drafts for all three founders (not posted)
X-THREAD*.md           the public threads, latest first
LICENSE                MIT
CITATION.cff           citation metadata
CONTRIBUTING.md        how to run the tests and the audit
SECURITY.md            what to report, and where
code/
  audit.py             independent Decimal + provenance audit (the verification entry point)
  fanlaw.py            the fan power law, calibrated to a measured duty cut
  throughput.py        the cost side of the trade: work lost, in dollars
  case.py              both legs plus the throughput leg, break-even, sensitivity
  cycling.py           rainflow / Coffin-Manson / Norris-Landzberg / Miner
  fleet_model.py       the affinity-law fleet model, standalone
  lambda_case.py       Lambda energy / fatigue / capacity model, self-tested
  together_case.py     Together model, with the ownership term, self-tested
  modal_case.py        Modal pass-through / qualification model, self-tested
  portfolio.py         the three verdicts, self-tested
  server_thermal_controller.py  steady-state thermal solve + safe duty for an 8-GPU node
  targets.py           fleet-size arithmetic, self-tested
data/
  profiles.csv         measured laptop profile table
  telemetry-sample.csv the trace the cycle counts came from
controller/
  README.md            safety model, the encoding trap, and what it cannot measure
  quiet-vivobook.ps1   the MPC governor
  fan-save.ps1         activate the fan-saving mode (no elevation)
  install.ps1          register the governor as a scheduled task
  report.ps1           report
  config.json          profiles, control band, MPC weights
  fan-scan/            sensor map, write-path proof, mode and scheme harnesses
docs/
  METHOD.md            how the measurement works, and what invalidates a run
  PHYSICS.md           the fan law, the thermal model, the fatigue model
  REPRODUCE.md         how to repeat this on your own hardware
```

## How the measurement works

Every measurement in this repo has the same shape: hold the workload fixed,
change one thing, count completed work and watts, and come back to the
baseline.

**A/B/A.** The baseline is measured twice — before and after the condition
under test — for one reason: to prove the machine did not drift while the
measurement ran. If the second baseline does not reproduce the first, the
comparison is void, no matter how clean the middle looked.

**The laptop, four paired blocks.** `controller/fan-scan/scheme-ab.ps1`
alternates the Balanced and Quiet power schemes in four blocks, with each
order used twice so that a monotonic thermal drift partially cancels. Each
phase runs the same in-process integer load for 60 s, and the work rate is
taken from the load's completed-work counter over the final 40 s steady
window, not from a per-sample rate that a short first interval can skew. The
governor is paused with its own `paused.flag` for the duration, the scheme is
read back after every write, and the original scheme is restored in `finally`.
Result: Quiet keeps 93.08 % of the Balanced work — a 6.92 % cost — with
per-block ratios of 0.9351, 0.9916, 0.9127, 0.8838.

**The run that was kept because it failed.** `controller/fan-scan/RESULTS.md`
documents three artifacts: the write-path proof, an invalid first attempt, and
a valid-but-confounded replacement.

- The first attempt is invalid because the load ran in hidden child processes
  that Windows placed on E-cores under EcoQoS, the run's own load signal
  (`Win32_Processor.LoadPercentage`) reads 4–7 % under real load on this
  hybrid CPU, and the child process died partway through, so the phases were
  not equal length.
- The replacement runs the load in-process with fixed phase lengths, but the
  repeated mode-0 baseline did not reproduce: 37.2 W / 2.12M work in the first
  phase, 16.6 W / 1.00M in the last. Thermal history, charge state or a
  firmware power limit moved under the run.

Both files are committed. Deleting a bad run is how a project starts lying.
What survives from them is narrow and worth stating precisely: the actuator
is real and reversible, the three thermal modes are distinct states, and the
machine restores its baseline cleanly. What does **not** survive is any claim
that mode 1 or mode 2 costs a specific percentage of throughput.

**What invalidates a run.** A repeated baseline that does not reproduce; phases
of unequal length; a load signal that is not completed work; a run on battery
or at an unrecorded charge state; thermal history carried over from the
previous phase; phase order confounded with the condition; a write path that
is not read back. `docs/METHOD.md` has the full list and the statistical
treatment.

## Reproduce it yourself

**The laptop A/B** (Windows, no elevation, ~15 minutes):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File controller/fan-scan/scheme-ab.ps1
```

It writes `controller/fan-scan/scheme-<timestamp>/summary.json` and restores
your original power scheme. The committed run is
`controller/fan-scan/scheme-ab-latest-summary.json`.

**The server simulation** (the 8-GPU node, calibrated to the upstream
measurement):

```powershell
uv run --no-project python code/server_thermal_controller.py --node gpu8
uv run --no-project python code/server_thermal_controller.py --node gpu8 --target-temp 75
```

The first command is the throttle knee (83 °C): duty 35.3 %, fan 881.0 W →
122.5 W, 86.10 % saved, 26.67 % throughput cost. The second is the shipped
operating point (75 °C): duty 52.9 %, fan 881.0 W → 244.9 W, 72.20 % saved,
0.00 % throughput cost. Both are steady-state solves, not timed runs.

**The audit:**

```powershell
uv run --no-project python code/audit.py
```

Expected last line: `0 hard failure(s), 0 warning(s)`. The audit recomputes
the headline numbers in `Decimal`, checks the modules against that reference,
checks the provenance of the claims the modules cannot prove, and checks that
the documents still agree with the code.

`docs/REPRODUCE.md` has the full protocol, including how to measure a real
8-GPU node over 30 days.

## Verify the numbers

`code/audit.py` is the verification entry point and the only file that reads
the documentation:

- it recomputes every headline in `Decimal` from first principles,
- it checks the case modules against that reference,
- it checks scaling invariants and that invalid inputs raise,
- it checks the upstream 120 W → 15 W measurement is reproduced rather than
  extrapolated,
- it checks the fatigue leg's provenance against the cycle simulator,
- it checks that the throughput term is debited, and that the shipped duty is
  the one the thermal model derives, and
- it checks that the documents still say what the code does (section 8).

If you change a number in a document, section 8 may need updating with it.
`CONTRIBUTING.md` has the rule.

## Credits

- **[quiet-lab](https://github.com/0xAlcibiades/quiet-lab)** by @0xAlcibiades
  (MIT) — the upstream project this repo tests. Source of the one real server
  fan-power measurement used here (120 W → 15 W, 65 → 42 dB on a 64-core
  Ampere Altra), and of the EKF + MPC control structure and the
  airflow^0.8 heat-transfer scaling reimplemented in
  `code/server_thermal_controller.py`.
- **[From Watts to Tokens](https://kiankyars.github.io/gigawatt)** by Kian
  Kyars — the PUE, cooling and power-delivery models used to turn watts into
  dollars.
- **Coffin-Manson** — the low-cycle fatigue law `N_f ∝ ΔT^(−n)`, `n ≈ 2` for
  SAC solder, used for the damage-per-cycle term.
- **ASTM E1049-85** — the standard rainflow cycle-counting method, implemented
  in `code/cycling.py`.
- **Norris-Landzberg** — the mean-temperature acceleration correction
  `exp(Ea / kT_max)`, applied on top of Coffin-Manson.
- **Miner's rule** — linear damage accumulation, `D = Σ nᵢ / N_fᵢ`.

## License

MIT. The upstream [quiet-lab](https://github.com/0xAlcibiades/quiet-lab) is
also MIT licensed. See `LICENSE`.

## Contributing

Read `CONTRIBUTING.md` first. In short: run the self-tests and `code/audit.py`
before opening a pull request, match the surrounding Python, and never drop a
provenance label.

Support: open an issue. Anything involving a machine's actuator goes through a
private security report instead — see `SECURITY.md`.
