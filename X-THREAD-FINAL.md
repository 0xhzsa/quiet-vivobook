# The thread: 6 posts, each under 280 characters

Built by `code/` as it stands. Every number in every post is computed live
from the repository's own modules by the build script, and `code/audit.py`
fails the build if a documented number drifts from the code.

Post 1 is the course post. It goes first because it is the one
@neuralkian and @freeCodeCamp have a reason to share: it quotes the course
accurately, credits it, and asks the question the course leaves open.

The framing is deliberately not "three companies, three verdicts". The
physics is identical everywhere; what changes is who holds the fan tray and
who pays the meter. That is the party worth talking to.

Repo: https://github.com/0xhzsa/quiet-vivobook
Course: https://kiankyars.github.io/gigawatt/

---

**1/6**

> Kian Kyars' "From Watts to Tokens" (@neuralkian, @freeCodeCamp) follows
> one watt from the grid to GPU transistors and back out as heat.
> 
> I took the cooling chapter and asked what the course doesn't: what if you
> turn the fans down?
> 
> github.com/0xhzsa/quiet-vivobook


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

> The fan law is where the naive answer breaks.
> 
> Affinity law says 95%. @0xAlcibiades measured 120W -> 15W on a real
> server: 87.5%.
> 
> Real fan motors have a loss floor. And quiet-lab gives duty RANGES, so the
> fit spans b = 0.085-0.875. Every saving is a BAND.
> 
> code/fanlaw.py


---

**4/6**

> 8-GPU node, 8x700W, 1kW fan tray, steady state.
> 
> The saving is not a constant, it is a function of the room.
> 30 C inlet: 44% of fan power. 18 C: 85%.
> 
> The duty that holds full boost is 53%, not 35%.
> At 35% you sit on the throttle knee: 27% of the
> work gone.
> 
> code/thermal_model.py


---

**5/6**

> So I built the controller and measured it against itself.
> 
> EKF estimates die temp + sensor bias. MPC picks the duty.
> Noisy sensor, load that changes.
> 
> Closed loop 160 W of fans. Cheapest CONSTANT duty at the
> same peak: 221 W. 28% less.
> 
> code/closed_loop.py. The test can fail.


---

**6/6**

> Where the meter sits decides who gets this.
> 
> Lambda @stephenbalaban @LambdaAPI: $1.43M/yr at R=36
> Together @vipulved @togethercompute: $1.21M/yr, meter
> with @hypertec. Modal @bernhardsson @modal: $7.31M/yr at
> its 13 providers.
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
| Lambda ATL02 | $1,427,992/yr at R=36; energy $707,692/yr | **modelled** on public anchors |
| Together 8k | $1,214,279/yr at R=36; energy $601,779/yr | **modelled**; the meter is shared with partners |
| Modal | $0 to Modal; $7,312,387/yr at its 13 node providers | **modelled** |
| fan tray wattage | 1,000 W on a dense 8-GPU node | **assumed**, no source; scales every dollar |

## Who to tag, and why

Every handle below was checked against x.com and resolves to a live account.

| tag | role | why |
|---|---|---|
| **@neuralkian** | Kian Kyars, "From Watts to Tokens" | the cooling, PUE and power models the fleet arithmetic uses |
| **@freeCodeCamp** | hosts the course | the course is 8 hours of the same physics, free |
| **@0xAlcibiades** | upstream maintainer, quiet-lab | the 120 W -> 15 W measurement everything is calibrated against |
| **@stephenbalaban** / **@LambdaAPI** | Lambda CTO + company | holds the BMC and the meter at ATL02 |
| **@EdgeConneX** | Lambda's Atlanta landlord | holds the site under the lease |
| **@vipulved** / **@togethercompute** | Together CEO + company | operates the clusters |
| **@hypertec** | Together's co-builder | brought the capacity, and may hold part of the meter |
| **@bernhardsson** / **@modal** | Modal CEO + company | no fans of its own; the $7.31M/yr bill is its providers' |
| **@CrusoeAI** | Crusoe | named in the same capacity-provider class |
| **@VoltagePark** | Voltage Park | owns air-cooled capacity, controls its own BMCs |
| **@WHITEFIBER** | WhiteFiber | a known Modal capacity customer |

## What to send with the thread

- `code/fanlaw.py` - the calibrated fan law, with the band it carries
- `code/thermal_model.py` - steady-state solve, derived duty, inlet envelope
- `code/closed_loop.py` - EKF + MPC and the experiment that compares them
- `code/audit.py` - independent Decimal reference; 0 failures, 0 warnings
- `code/server_thermal_controller.py` - the CLI over the two modules above
- `controller/fan-scan/scheme-ab.ps1` - the clean laptop A/B harness
- `controller/fan-scan/RESULTS.md` - write-path proof, invalid run, kept on purpose
- `SELF-REVIEW.md` - what is solid in this repo and what is not

## Approval

Not posted. The repo is public at https://github.com/0xhzsa/quiet-vivobook
and every file above is committed.
