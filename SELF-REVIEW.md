# SELF REVIEW - what is actually solid and what is not

Written as a hostile code review of this repository by the person who built it.
Every claim below was checked against the code, not against my memory of it.

---

## 1. The findings that would get this rejected in a real engineering review

### 1.1 The "87.5 % cross-check" is a tautology, not a validation

This is the worst one, and it is the load-bearing claim of the whole project.

`code/fanlaw.py` is **fitted** so that the quiet-lab duty pair reproduces 87.5 %.
Then `code/server_thermal_controller.py` runs an independent thermal model,
gets a duty of 35.3 %, asks the fitted law what percentage that duty removes,
gets 86.1 %, and I called that "within 1.4 points of the measurement".

The thermal model was never given the fan measurement to fit against. But the
*fan law* was fitted to the exact number being compared against. So the
comparison is only as independent as the thermal model's ability to land on
the duty that quiet-lab happened to use.

And the thermal model was **tuned to land there**. The `r_die_hs` / `r_hs_air` /
`r_air_amb` defaults were chosen to put the die at ~77 °C at full duty. Nothing
in the physics forces the resulting "minimum safe duty" to be near 30 %.

**Verdict: 86.1 % vs 87.5 % is a consistency check, not a cross-validation.**
It is still worth something - two independently-constructed models agreeing to
1.4 points is better than one model - but the README and the thread both
overstate it as validation. Fix: call it a consistency check, and state that
the duty agreement is a consequence of the thermal model's calibration.

### 1.2 `b = 0.342` is one free parameter fitted to one data point

The affine-cubic law has two coefficients. I fixed `a = 1.0` and solved for
`b`. One number out, one number in: **zero degrees of freedom.** There is no
residual, no confidence interval, no way to be wrong.

Worse, the duty points are *assumptions*. quiet-lab states ranges
("80-100 %" and "25-35 %"). I picked the midpoints 90 % and 30 %. Across the
ranges quiet-lab actually states, `b` runs from 0.085 to 0.875 - a 10x spread -
and the resulting 8-GPU fan saving at the shipped duty runs from **79.1 % to
92.1 %**.

I reported 86.1 % to two decimal places. The honest number is a band.

**Verdict: the fan law is a one-point calibration with a wide, unstated
uncertainty.** Fix: report the band, drop the decimals, and state the duty
midpoint assumption every time the law is used.

### 1.3 The "0.00 % throughput cost" hangs on a number I picked

`THROTTLE_START_C = 75.0` is described in the source as coming from "NVIDIA's
own VBIOS behaviour". **I did not find a citation for it.** It is my number.

Its effect on the headline:

| full-boost target | duty | fan saved | work cost |
|---|---|---|---|
| 70 °C | 74.4 % | 43.6 % | 0 % |
| 72 °C | 64.2 % | 59.1 % | 0 % |
| **75 °C** | **52.9 %** | **72.2 %** | **0 %** |
| 78 °C | 44.7 % | 79.5 % | 10.0 % |
| 80 °C | 40.4 % | 82.7 % | 16.7 % |

A 5 °C move in a constant I invented moves the headline by 13 points of fan
saving. **Verdict: "zero throughput cost" is an artifact of a picked
constant.** Fix: treat 75 °C as an assumption with a band, or drop the
zero-cost framing.

### 1.4 Ambient temperature swings the answer more than everything else

| inlet ambient | safe duty | fan saved |
|---|---|---|
| 20 °C | 40.4 % | 82.7 % |
| 25 °C | 52.9 % | 72.2 % |
| 30 °C | 74.4 % | 43.6 % |
| 35 °C | 100 % | **-13.5 %** (cannot cool) |

A real 8-GPU node in a real datacentre sees 18-30 °C inlet. The model has one
ambient (25 °C) and no band. At 30 °C the honest answer is "you get about
44 %, not 72 %". **Verdict: the model has no inlet-temperature band, and the
one it does have is mid-range.** Fix: report the envelope across 18-30 °C.

### 1.5 The 52.9 % duty is a literal in four files, not a derived value

`code/case.py`, `code/lambda_case.py`, `code/together_case.py`,
`code/modal_case.py` and `code/audit.py` all contain the literal `0.529`.
The audit asserts `abs(case.GPU8.duty_ctrl - 0.529) < 1e-3` - it checks that
a literal equals itself.

If someone changes the thermal model tomorrow, the fleet numbers silently keep
the old duty and the audit still passes. **Verdict: the "derived from the
thermal solve" claim is not enforced by anything.** Fix: the fleet modules
must import the duty from the thermal solve, or the audit must recompute it.

### 1.6 The EKF and the MPC are dead code

`code/server_thermal_controller.py` defines `class EKF` and
`class MPCController`. **Neither is instantiated or called anywhere** - not in
`main()`, not in any selftest, not in the fleet models. The thermal solve is
a closed-form steady-state calculation; there is no state estimation and no
control loop in the shipped path.

The README says "EKF+MPC thermal controller" and the thread says
"EKF+MPC on laptop". That is not true of the code that produces the numbers.
**Verdict: the most impressive-sounding part of the repo does not run.**

### 1.7 `mode-effect.ps1` v3 has never been executed

The v3 harness (with the cooldown gate, the null-temperature invalidation,
the mode-drift detection, the `-Modes` string parsing fix) was written, syntax
checked, committed - and **never run**. The only three output directories in
`controller/fan-scan/` are from the old v2. The elevation prompt was declined
during the session, so the v3 path is unexercised.

**Verdict: a firmware-writing harness ships untested.** Fix: either run it
(with an approved UAC prompt) or mark it clearly as unexercised in the file
header and the README.

### 1.8 The 5.15 % throughput cost in `throughput.py` came from a run I later proved invalid

`GPU8_COST = 0.0515` is described as "SIMULATED, calibrated 8-GPU model". It
actually came from a **120-second** run. I later proved - in the same
repository - that 120 s does not reach steady state at low duty, and that the
same duty point settles at a much higher temperature. The number is a transient
measurement presented as a steady-state one.

It is still the default in `throughput.py`, still in `docs/REPRODUCE.md`, and
still in the two older thread drafts. **Verdict: a known-invalid number is
still load-bearing.**

### 1.9 "fan-save.ps1" does not save fan

`controller/fan-save.ps1` sets `boost=3, EPP=60, state=100`. On Windows,
`PERFBOOSTMODE = 3` means **turbo enabled (aggressive)**; only `0` disables
boost. So the script enables aggressive turbo with a middling EPP. It is a
*power* profile, not a *fan* profile, and the name oversells it.

The laptop has no fan telemetry at all (0 of 256 EC registers non-zero,
`Win32_Fan` empty, no tachometer). **I have never measured the laptop's fan
speed, fan power, or noise.** The 6.92 % figure is a *work-rate* cost of a
*power scheme*. No measurement in this repository links a fan to a watt.

**Verdict: "fan-save" is a misnomer, and the repo has zero fan measurements of
its own.** The 87.5 % is quiet-lab's, on a server.

### 1.10 `targets.py` still uses the raw cubic

`code/targets.py:47` is `fan_w * (1.0 - (duty_ctrl / duty_base) ** 3)` - the
exact law the rest of the repo was recalibrated to remove. It has a selftest
that asserts the cubic behaviour. **Verdict: two fan laws live in one repo.**

### 1.11 The 1 kW fan tray is an assumption that scales every dollar

`fan_w = 1000.0` on the 8-GPU node is not sourced from anything. It is the
largest single input to every dollar figure in the repository, and the
sensitivity is linear: 600 W tray → $421/node/yr, 1500 W tray → $1053/node/yr.
It is labelled "assumed" in the README, which is correct and is the only
reason this one is a documentation issue rather than a correctness issue.

---

## 2. What is actually solid

Worth stating, because the list above is not the whole picture.

- **The laptop A/B is real.** 4 paired blocks, Balanced/Quiet alternating so
  monotone drift cancels, governor paused, in-process load with a completed-work
  counter, 40 s steady windows, AC enforced, scheme restored in `finally`.
  The 6.92 % is a genuine measurement with a stated per-block range
  (88.4-99.2 %). The harness is careful.
- **The invalid run is kept and labelled invalid.** `mode-20261020-160330` is
  committed with the reason it failed. That is the single most credibility-
  building thing in the repository.
- **The write-path proof is real.** `devs-20261020-155011` shows every
  `DEVS` call returning 1, every read-back matching, and `restored_ok: true`.
  The actuator is real and reversible.
- **`code/audit.py` is a genuine second implementation.** It re-derives the
  fan law in `Decimal` without importing `fanlaw.py`, and the two agree to
  14 digits across four modules. That is a real defence against a typo.
- **The 10 selftests are real tests.** They assert monotonicity, bounds,
  sign, and the measured-vs-model agreement - not that the code returns its
  own output.
- **The `capacity_constrained` split is correct and important.** Losing 5 % of
  work is free with spare capacity and expensive when saturated. Modelling
  both regimes is the right call and the fleet case uses the honest one.
- **The upstream citation is exact.** 120 W → 15 W, 65 → 42 dB, 87.5 %, MIT
  licensed, attributed to @0xAlcibiades in every document that uses it.

---

## 3. The design flaw underneath all of it

The repository mixes three different kinds of number without a hard boundary
between them:

1. **measured on this machine** (the 6.92 % work cost)
2. **measured elsewhere, on different hardware** (the 87.5 %)
3. **modelled here, calibrated to (2)** (everything 8-GPU)

The 8-GPU numbers are presented with the same visual weight as the laptop
measurement, and the one check that looks like external validation
(§1.1) is a consistency check. A reader skimming the README cannot tell
which is which without reading the provenance column carefully.

**The fix is structural, not cosmetic:** every derived number should carry
the *band* implied by the assumptions it depends on, and the repository
should ship a single command that prints those bands.

---

## 4. What would actually make this defensible

Ranked by how much they buy.

1. **Make the fan law a band, not a point.** `fanlaw.py` should take the duty
   *ranges* quiet-lab states and return a range of savings. One number in, a
   band out. This is a small change and it removes the single worst
   overstatement in the repo.
2. **Fix the tautology.** Report the 87.5 % comparison as a consistency
   check. Better: get a *second* independent fan measurement (any server, any
   duty pair) and fit on one, test on the other. That converts §1.1 from
   rhetoric into evidence.
3. **Delete or wire up the EKF and the MPC.** Dead code that the README
   claims is the core of the system is worse than no code. Either run a real
   closed loop in the simulation (thermal model + controller + load profile,
   showing the controller converging) or delete both classes and the claim.
4. **Derive the duty, do not literal it.** The fleet modules should import
   the safe duty from the thermal solve. If the thermal model changes, the
   fleet numbers change with it. The audit should assert the *derivation*,
   not the constant.
5. **Add the ambient band and the throttle-start band to every headline.**
   At 30 °C inlet the answer is 44 %, not 72 %. Say so.
6. **Run the v3 harness or mark it unexercised.**
7. **Delete the 5.15 % constant** or re-derive it from the steady-state
   solve.
8. **Rename `fan-save.ps1`** to what it does - a power/efficiency profile -
   and state plainly that the laptop's fan is not measured and cannot be.
9. **Unify the fan law.** `targets.py` uses the cubic; everything else uses
   the affine-cubic. One law, one module, one import.
10. **A falsification test suite** that asserts the *predictions* the model
    makes and fails when they break, rather than asserting the model's own
    output.

---

## 5. The GitHub-description problem

The current description says the repo is "a falsification of the 7-figure fan
savings claim", and the case files use "disqualified" and "conditional" as
verdicts on named companies.

Both are wrong for the same reason: they are claims about *other people's
businesses* dressed as findings. The physics is not a verdict on Lambda,
Together, or Modal. What the analysis actually establishes is narrower and
more useful:

- For any air-cooled node, there is a **safe duty** that holds a target
  temperature.
- The fan saving at that duty is a **function of inlet temperature, GPU load,
  and tray wattage** - all of which are measurable on a real node.
- The party that benefits is the party that **pays the meter and controls the
  BMC**. That party is sometimes not the company whose GPUs are on the
  placard: Modal's fan bill belongs to its 13 capacity partners, Together's
  H100/H200 capacity is co-built with **Hypertec**, Lambda's ATL02 is a leased
  site from **EdgeConneX**.

So the honest framing is not "these three companies, three verdicts". It is
"here is the measurement, here is who it applies to, and here is the party
that gets the money - which is sometimes the data centre operator, not the
GPU vendor". That is a stronger thread, because it is actionable for a
specific person rather than an accusation about three.

The tags should therefore include the parties that actually hold the fan
trays and the meters: **@0xAlcibiades**, **@stephenbalaban** / **@LambdaAPI**,
**@vipulved** / **@togethercompute**, **@bernhardsson** / **@modal**,
**@neuralkian**, plus the operators and builders the money flows to -
**@hypertec** (Together's co-builder), **@EdgeConneX** (Lambda's Atlanta
landlord), and the 13 capacity providers behind Modal.

All ten handles were checked against x.com and resolve to live accounts. The
full list is in the "Who to tag" table of X-THREAD-FINAL.md.

---

## 6. Summary judgement

The **method** is good and the **laptop measurement** is real and the **audit
machinery** is genuinely strong. The **8-GPU numbers are a one-point
calibration presented as a validated model**, and the repository currently
does not say so.

The gap is not effort. It is that the interesting claims need bands and
evidence, and I shipped point estimates and a consistency check dressed as
external validation.
