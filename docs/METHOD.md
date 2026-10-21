# METHOD

How a measurement in this repository is made, what can invalidate it, and how
the numbers are treated statistically.

The short version: hold the workload fixed, change one thing, count completed
work and watts, and come back to the baseline. Everything below is the detail
of that sentence, and the list of ways it can go wrong.

---

## 1. The A/B/A design

The comparison is **A/B/A**: the baseline is measured before the condition
under test and again after it.

```
| warm-up | A | B | A |
```

The reason is not ceremony. A single A→B comparison cannot distinguish "B is
slower" from "the machine got slower". A second A can: if the two A phases
agree, the plant held still and the B phase measures B. If they do not agree,
the run is void, and no amount of confidence in the middle phase rescues it.

A/B/A costs one extra baseline phase. That is cheap, and it is the cheapest
insurance in the repository — it is what turned the thermal-mode experiment
from "a result" into "no result, for a documented reason".

### The laptop A/B, in detail

`controller/fan-scan/scheme-ab.ps1` is the clean measurement. Its shape:

| element | value | why |
|---|---|---|
| conditions | Windows power schemes *Balanced* and *Quiet (quiet-vivobook)* | the actuator is a power scheme, so no firmware write is needed and no elevation is needed |
| blocks | 4 | see §4 |
| order within a block | alternating: balanced→quiet, quiet→balanced, balanced→quiet, quiet→balanced | each order twice, so a monotonic thermal drift cancels |
| warm-up | 30 s, discarded | the CPU has to leave its idle clock before the first phase is meaningful |
| phase length | 60 s | long enough that the steady window dominates the transient |
| steady window | the final 40 s of each phase | the tail, not the transient, is what is compared |
| between phases | 45 s | a fixed gap so that no phase starts on another's residual heat |
| load | 8 threads, in-process, integer work, fixed | the workload must be identical in every phase |
| work rate | completed-work counter over the steady window | a completed-work count cannot be faked by a faster clock on idle threads |
| governor | paused with `controller/paused.flag` for the duration | otherwise the governor changes the power profile mid-phase |
| power state | AC required; the harness refuses to run on battery | and it records the battery charge percentage |
| restore | the original scheme is reactivated in `finally` | the harness never leaves the machine in a state it did not find |

Result, from `controller/fan-scan/scheme-ab-latest-summary.json`:

| block | order | quiet / balanced work |
|---:|---|---:|
| 1 | balanced, quiet | 0.9351 |
| 2 | quiet, balanced | 0.9916 |
| 3 | balanced, quiet | 0.9127 |
| 4 | quiet, balanced | 0.8838 |

Mean 0.9308 → a **6.92 %** throughput cost for the Quiet scheme, with a
per-block range of 88.4 %–99.2 %.

---

## 2. The confounds, and how each is controlled

Each of these is a way a run can produce a number that is about something else
entirely.

### Thermal history

A phase inherits the die temperature of the phase before it. The second phase
of a block therefore starts hotter than the first, and the comparison is
contaminated by a thermal gradient that has nothing to do with the condition.

*Controlled by:* fixed phase lengths, a fixed 45 s gap between phases, a
discarded warm-up, and the A/B/A structure that returns to the baseline at the
end of the run. *Not controlled by:* nothing makes each phase start from the
same temperature. A run that starts each phase from a fixed temperature would
be better, and that is the single change most likely to tighten the
block-to-block spread.

### Baseline drift

The plant changes during a run: charge state, firmware power limits, ambient
temperature, driver state, and on a laptop the thermal envelope itself.

*Controlled by:* the closing A phase. If the closing baseline does not
reproduce the opening baseline, the run is invalid and is reported as
invalid. This is the only control that can detect drift rather than correct
it, and it is the reason the A/B/A structure exists.

### Order effects

Within a block, whichever condition runs second inherits the other's heat and
the other's clock state.

*Controlled by:* alternating the order, so each condition appears first twice
and second twice. A pure monotonic drift then contributes with opposite signs
to the two conditions and largely cancels in the block ratio.

### EcoQoS and child-process pinning

Windows places background and child work on efficiency cores under EcoQoS. A
load that runs in a child process can therefore measure a different CPU than
the one it was intended to measure — on this machine's hybrid i9-13900H, the
hidden-child run drew **26.9 W where the in-process harness later drew
37.2 W** for nominally the same work.

*Controlled by:* running the load in-process, on a fixed thread count, with a
fixed priority, and verifying the live thread count in every sample. The
harness records `alive_threads` per sample so that a dying thread is visible
in the artifact rather than hidden in an average.

### A load signal that is not load

`Win32_Processor.LoadPercentage` read 4–7 % under real load on this hybrid
CPU. It is not a load signal.

*Controlled by:* counting completed work. The work counter is the measurement;
power is the second measurement; nothing else is used as evidence of load.

### Unequal phases

In the first mode-effect run, the child process died partway through, so the
phases were not the same length and the means were not comparable.

*Controlled by:* fixed phase durations, a recorded sample count per phase, a
minimum number of steady-window samples, and an explicit `invalid` field that
aborts the run instead of averaging through it.

### Mode drift

The thermal policy is a firmware setting. It can be changed by the governor,
by a driver, or by the BIOS, and the machine will not tell you it happened
unless you look.

*Controlled by:* reading the setting back after every write and recording it
in the artifact. The committed write-path proof
(`controller/fan-scan/devs-20261020-155011/result.json`) shows every read-back
matching and `restored_ok: true`.

### Governor interference

The quiet-vivobook governor switches power profiles on a 5 s poll. Left
running, it will change the condition under test in the middle of a phase.

*Controlled by:* pausing it. The harness creates `controller/paused.flag`
itself if it does not exist, and removes it in `finally` — so the flag is
never left behind, and the pause is visible in the log rather than implied.

### Machine state

*Controlled by:* refusing to run on battery, recording AC state and charge
percentage in the artifact, and restoring the original power scheme in
`finally`.

---

## 3. What invalidates a run

A run is invalid if any of these is true. None of them is a judgement call, and
none of them is negotiable after the fact.

1. The closing baseline does not reproduce the opening baseline.
2. A phase ran for a different length than the others, or the load died
   mid-phase.
3. The work signal is missing, or a phase has fewer than three samples in its
   steady window.
4. The load ran in a different process, on a different core set, or at a
   different thread count than the other phases.
5. The machine was not on AC, or the charge state was not recorded.
6. The controller was not paused, and it changed the condition mid-phase.
7. A write was not read back.
8. The order of the conditions was not recorded, so the order effect cannot be
   assessed.

Two runs in this repository fail one of these tests. Both are committed:

- `controller/fan-scan/mode-20261020-155110/summary.json` — invalid. Hidden
  child processes on E-cores, a meaningless load signal, and a child that died
  mid-run.
- `controller/fan-scan/mode-20261020-160330/summary.json` — valid phases, but
  the closing mode-0 baseline did not reproduce the opening one (37.2 W /
  2.12M work against 16.6 W / 1.00M), so no mode-to-mode throughput claim is
  supported by it.

The file is committed because deleting a bad run is how a project starts
lying.

---

## 4. The statistical treatment

### Paired block ratios, not pooled samples

Each block produces one ratio:

```
ratio_b = work_rate(quiet) / work_rate(balanced)
```

The reported number is the **mean of the block ratios**, and the reported
uncertainty is the **range of the block ratios**.

The alternative — pooling every sample from both conditions and comparing the
means — is wrong here, because it treats 21 samples from one phase as
independent observations of a condition that was in fact measured once, under
one thermal state, for one minute. It would shrink the apparent uncertainty by
roughly the square root of the number of samples per phase while the real
uncertainty lives between the phases. Pairing is what makes the comparison
honest.

### Range before mean

The mean (0.9308) is the point estimate. The range (0.8838–0.9916) is the
honest uncertainty, and it is wider than the effect. That is not a footnote:
it means the spread of this machine's block-to-block behaviour is of the same
order as the 6.92 % being measured. The spread is a property of the machine
and the workload, not of the power schemes.

No p-value is quoted. Four blocks cannot support one, and the interval below
shows why.

### What four blocks buys, and what three would not

With the observed block-to-block standard deviation, s = 0.0457:

| blocks | 95 % interval on the mean ratio | verdict |
|---:|---|---|
| 3 | 0.817 – 1.044 | useless: the interval swallows a 18 % loss *and* a 4 % gain |
| 4 | 0.858 – 1.003 | still crosses 1.0 |
| 5 | 0.874 – 0.988 | clears 1.0 |
| 10 | 0.898 – 0.964 | tight enough to quote a number with a range |

**Three repeats are underpowered.** The t-multiplier for two degrees of
freedom is 4.303, and the sample is tiny; at the spread this machine shows,
resolving a 6.92 % effect with three repeats would need the interval to be
narrower than 0.23 — and it is 0.227, so it fails on the boundary. The
honest statement is that three repeats of an A/B/A gives two paired
comparisons and cannot separate a 7 % effect from this machine's noise.

**Four blocks of a paired design is a pilot, not a proof.** It is enough to
establish that the effect is in the right direction in all four blocks, that
the estimate is stable enough to act on, and that the design is sound enough
to scale up. It is not enough to claim a demonstrated effect: the 95 %
interval on four blocks is 0.858–1.003, and it crosses 1.0. So the repo says
**6.92 %**, and says in the same sentence that the per-block range is
88.4–99.2 %.

Scaling the same design to five blocks would clear the effect at 95 % if the
spread stays where it is. That is the next run, and it is the reason the
harness takes a block count rather than a fixed list of phases.

---

## 5. What this method cannot do

- It cannot measure fan power on this machine. The embedded controller
  exposes 0 non-zero registers of 256, `Win32_Fan` is empty, DPTF has no fan
  class, and LibreHardwareMonitor has no fan sensor. The loop closes on
  package power and per-core temperature.
- It cannot measure acoustics. No RPM, no calibrated microphone, no dB.
- It cannot generalise the laptop's 6.92 % to a server's duty change. The
  laptop actuator is a CPU power scheme; the server actuator is a BMC fan
  duty. The *shape* of the measurement transfers. The number does not.
- It cannot turn the 8-GPU simulation into a measurement. That requires a BMC
  trace from a real node; `docs/REPRODUCE.md` has the protocol.
