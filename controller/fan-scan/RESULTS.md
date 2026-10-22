# What each run proves, and what it does not

Three artifacts are committed. One is the write-path proof. One is an invalid
run kept on purpose. One is a valid run with a confound that limits what it can
claim.

## `devs-20261020-155011/result.json` — the write path

Baseline mode `0`. The harness wrote `0` (no-op), `1`, `2`, then restored `0`.
Every `DEVS` call returned `result=1`, every read-back matched the raw value,
and `restored_ok` is `true`.

This proves the actuator is real and reversible. It says nothing about
performance.

## `mode-20261020-155110/summary.json` — invalid, kept as evidence

The first attempt at measuring the mode effect. **Do not use these numbers.**

Why it is invalid:

- The load ran in hidden child processes, which Windows placed on E-cores under
  EcoQoS. The package drew 26.9 W in "mode 0" where the in-process harness later
  drew 37.2 W.
- `Win32_Processor.LoadPercentage` read 4–7 % under real load on this hybrid
  CPU, so the run's own load signal was meaningless.
- The child process died partway through, so the phases are not equal length.

The file is committed because deleting a bad run is how a project starts lying.

## `mode-20261020-160330/summary.json` — valid phases, confounded comparison

The replacement harness runs the load **in-process**, counts completed work
iterations, auto-tunes thread count, and runs an A-B-A sequence (mode 0 → 1 →
2 → 0) with fixed phase lengths.

| phase | mode | steady °C | steady W | work rate |
|---|---|---|---|---|
| p0 | 0 | 89.5 | 37.22 | 2.12M |
| p1 | 1 | 84.47 | 26.33 | 1.54M |
| p2 | 2 | 67.78 | 12.50 | 0.96M |
| p3 | 0 | 72.70 | 16.64 | 1.00M |

`restored_ok: true`.

**The confound:** p3 is the same mode as p0 and did not reproduce it. Work rate
halved and power fell from 37.2 W to 16.6 W. Something in the plant drifted
across the four phases — thermal history, charging state, or a firmware power
limit.

That means:

- **Valid:** the three modes are distinct states, the write/read-back path is
  sound, and the machine restores cleanly.
- **Invalid:** any claim that mode 1 or 2 costs a specific percentage of
  throughput, or that mode 2 is "faster" or "slower" than mode 0. The repeated
  baseline moved too much to support a between-mode comparison.

## What would make it a clean measurement

1. Randomize phase order and repeat each mode three times.
2. Insert a fixed cool-down between phases, or start each phase from a fixed
   temperature.
3. Hold the package on AC and at a fixed charge state.
4. Measure wall power with an external meter, not just RAPL.
5. Run long enough that the tail, not the transient, dominates.

None of that changes the actuator or the controller. It changes what can be
claimed about their performance cost — which is currently: **not measured**.

## `mode-20261022-025525` - the run that works

A/B/A/B/A/B: thermal mode 0 (balanced) and 1 (silent), six phases of 100 s
at 12 threads, 50 s steady window, on AC, with a 66 C cooldown gate before
every phase. 317 samples. Every phase valid; every mode read-back matched.

| phase | mode | pkg W | die C | work/s | n | AC |
|---|---|---|---|---|---|---|
| p0-m0 | 0 | 16.48 | 73.3 | 1,086,729 | 23 | ac |
| p1-m1 | 1 | 12.19 | 69.6 | 1,046,800 | 24 | ac |
| p2-m0 | 0 | 16.13 | 71.6 | 1,067,426 | 22 | ac |
| p3-m1 | 1 | 15.29 | 75.1 | 1,057,743 | 23 | ac |
| p4-m0 | 0 | 11.74 | 69.5 | 1,061,856 | 21 | ac |
| p5-m1 | 1 | 13.60 | 71.6 | 1,058,289 | 22 | ac |

Paired analysis (`analyze-mode-run.py`, output committed as
`analysis-20261022-025525.txt`):

| quantity | mode 0 | mode 1 | paired mean | t (df 2) | verdict |
|---|---|---|---|---|---|
| package power | 14.78 W | 13.69 W | -1.09 W | -0.61 | not resolved |
| work rate | 1,072,004 | 1,054,277 | -17,726/s | -1.58 | not resolved |
| die temperature | 71.5 C | 72.1 C | +0.61 C | +0.28 | not resolved |

**What this proves.** Moving the ASUS thermal policy from balanced to silent
changes nothing measurable on this machine at this load. The between-replicate
standard deviation of package power is 3.08 W on a 14 W mean, so the noise
floor is larger than any plausible fan effect here.

**Why that is the useful result, not a null one.** On a laptop the fan is
not the constraint: 12 threads never push the machine past 75 C in a way the
fan curve can change. So the fan curve is free - which is exactly the
argument for why it is the right lever on a GPU node, where the GPU is the
work and the fan is what limits it. The measurement on this machine says the
fan curve costs nothing here, and the power scheme costs 6.92 % of the work
(`scheme-ab-latest-summary.json`).

**What it does not prove.** Nothing about a server. The die never got hot
enough here for the fan to be the binding constraint, so this run says
nothing about what a fan control costs on a node running a 700 W GPU. That
is what the 30-day BMC protocol in `docs/REPRODUCE.md` is for.

**The three defects that had to be fixed to get this run.** The v3 harness
was committed but had never executed. Running it exposed:

1. The sampler was starved. The load ran at `ThreadPriority.Highest` with
   the process at `High`, and the ASUS ACPI WMI provider - which runs at
   Normal - stopped being scheduled. The per-sample mode read blocked for
   minutes. Fixed: load at `AboveNormal`, process at `Normal`, and the mode
   is read back once per phase instead of once per sample.
2. The first MSR read costs about 28 seconds. That is PawnIO
   initialising, and it was happening inside the first measured phase, so
   the steady window could not fill. Fixed: the driver is warmed before the
   clock starts, and the cost is logged.
3. The warmup was shorter than the steady window, so the window could never
   fill. Fixed: `SteadySec` is clamped to the phase length, and a phase that
   cannot fill its window is invalidated rather than reported.

**The defect the run itself exposed.** The first A/B/A/B lost the mains
part-way through and the last phase ran on battery, where Windows caps the
CPU at a lower thermal envelope: package power decayed 11.7 -> 8.0 W with
the die at 58.1 +/- 0.3 C. That phase would have been silently averaged
into the result. The harness now checks the AC state before and during
every phase and voids the run if the mains is lost, and the analysis tool
refuses to report a run with a non-AC phase.

**A fourth thing that did not work.** `battery-fan-power.ps1` reads the
battery discharge rate, which on this machine is the only whole-system power
meter available. It works - but the meter is too noisy to resolve a 1 W
fan difference against a 3 W noise floor, and on battery the CPU power
limit changes underneath the measurement. It is kept as a script and
reported as a null result, not as a fan measurement.

