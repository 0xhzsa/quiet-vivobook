# The thread: laptop as GPU simulator - 6 posts, each under 280 chars

Built from `code/` as it stands. Every number is computed by the repository's
own modules, and `code/audit.py` fails the build if a documented number
drifts from the code.

The framing is deliberately not "three companies, three verdicts". The
physics is identical everywhere; what changes is who holds the fan tray and
who pays the meter. That is the party worth talking to.

Repo: https://github.com/0xhzsa/quiet-vivobook

---

**1/6**

> I don't own a GPU server. I own an ASUS Vivobook.
> 
> So I built a thermal controller on my laptop and made it simulate an 8-GPU node.
> 
> Then I tried to break my own model and published what broke.
> 
> Every number traceable to a file. github.com/0xhzsa/quiet-vivobook


---

**2/6**

> Measured: the laptop's throughput cost.
> 
> Thermal A-B-A was confounded (37.2W/2.12M -> 16.6W/1.00M). I kept it.
> 
> Clean A/B: Balanced vs Quiet, governor paused, 4 paired blocks.
> Quiet keeps 93.08% of work. Cost: 6.92%. Range 88.4-99.2%.
> 
> controller/fan-scan/scheme-ab.ps1


---

**3/6**

> Measured by @0xAlcibiades: 120W -> 15W fan on a real 64-core
> Ampere server. 87.5% cut.
> 
> The affinity law says 95%. Wrong: fan motors have a loss floor that
> does not vanish with speed.
> 
> But quiet-lab gives duty RANGES, not points. So every saving is a BAND.
> 
> code/fanlaw.py


---

**4/6**

> 8-GPU node, 8x700W, 1kW tray, steady state.
> 
> The saving is not a constant, it is a function of the room.
> 30 C inlet: 44% of fan power. 18 C: 85%.
> 
> The duty that holds full boost is 53%, not 35%.
> At 35% you sit on the throttle knee: 27% of
> the work gone.
> 
> code/thermal_model.py


---

**5/6**

> So I built the controller and measured it against itself.
> 
> EKF estimates die temp + sensor bias. MPC picks the duty.
> Noisy sensor, load that changes.
> 
> Closed loop: 160 W of fans. Cheapest CONSTANT duty at
> the same peak: 221 W. 28% less.
> 
> code/closed_loop.py. The test can fail.


---

**6/6**

> The meter decides who gets this.
> 
> Lambda @stephenbalaban @LambdaAPI: $1.43M/yr
> Together @vipulved @togethercompute: $1.21M/yr, meter shared with
> Hypertec. Modal @bernhardsson @modal: $7.31M/yr, at its providers.
> 
> One BMC trace replaces the biggest assumption.


---

## Number provenance

| number | value | provenance |
|---|---|---|
| laptop throughput cost | 6.92 % (Quiet keeps 93.08 % of the work; per-block 88.4-99.2 %) | **measured**, this machine |
| quiet-lab fan saving | 87.5 % (120 W -> 15 W, 65 -> 42 dB) | **measured**, @0xAlcibiades, 64-core CPU server |
| fan-law uncertainty | b spans 0.085-0.875 over quiet-lab's stated duty ranges | **derived from the measurement** |
| 8-GPU safe duty at 80 % load | 52.9 % (holds 75 C, full boost) | **modelled**, steady-state thermal solve |
| 8-GPU fan saving at 80 % load | 72.2 %, band 54.4-74.5 % | **modelled**, calibrated law + thermal model |
| 8-GPU saving vs inlet | 43.6 % at 30 C, 85.1 % at 18 C | **modelled**, same solve |
| throttle-knee operating point | 35.3 % duty, 86.1 % saved, 26.7 % work cost | **modelled** |
| closed loop vs constant duty | 27.6 % less fan power at the same peak temperature | **measured in simulation** |
| Lambda ATL02 | energy $707,692/yr; $1,427,992/yr at R=36 | **modelled** on public anchors |
| Together 8k | energy $601,779/yr; $1,214,279/yr at R=36 | **modelled**; the meter is shared with partners |
| Modal | $0 to Modal; $7,312,387/yr at its 13 node providers | **modelled** |
| fan tray wattage | 1,000 W on a dense 8-GPU node | **assumed**, no source; scales every dollar |

## Who to tag, and why

| tag | role | why |
|---|---|---|
| **@0xAlcibiades** | upstream maintainer, quiet-lab | the 120 W -> 15 W measurement everything else is calibrated against |
| **@stephenbalaban** / **@LambdaAPI** | Lambda CTO + company | holds the BMC and the meter at ATL02; the Atlanta landlord is **EdgeConneX** |
| **@vipulved** / **@togethercompute** | Together CEO + company | operates the clusters; the H100/H200 capacity is co-built with **Hypertec** |
| **@bernhardsson** / **@modal** | Modal CEO + company | no fans of its own; the $7.31M/yr fan bill sits with its 13 capacity providers |
| **@kiankyars** | Gigawatt course author | PUE, cooling and power models used in the fleet arithmetic |
| **Hypertec** | Together's co-builder | holds capacity, and possibly the meter, on part of the fleet |
| **EdgeConneX** | Lambda's Atlanta landlord | holds the site under the lease |
| Modal's 13 capacity providers | the actual meter holders | where $7.31M/yr of fan power actually sits |

## What to send with the thread

- `code/fanlaw.py` - the calibrated fan law, with the band it carries
- `code/thermal_model.py` - steady-state solve, safe duty, inlet-temperature envelope
- `code/closed_loop.py` - EKF + MPC, and the experiment that compares them
- `code/audit.py` - independent Decimal reference; 0 failures, 0 warnings
- `code/server_thermal_controller.py` - the CLI over the two modules above
- `controller/fan-scan/scheme-ab.ps1` - the clean laptop A/B harness
- `controller/fan-scan/RESULTS.md` - write-path proof, invalid run, kept on purpose
- `SELF-REVIEW.md` - what is solid in this repo and what is not

## Approval

Not posted. The repo is public at https://github.com/0xhzsa/quiet-vivobook
and every file above is committed.
