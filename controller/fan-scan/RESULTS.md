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
