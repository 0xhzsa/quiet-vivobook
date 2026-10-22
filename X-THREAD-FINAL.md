# The thread: 6 posts, each under 280 characters

Post 2 is the result the whole project rests on, and it is a negative one:
on a laptop, moving the FAN CURVE costs no measurable work, while moving the
CPU POWER LIMIT costs 6.92 %. That is the argument for why the fan is the
right lever on a GPU node - the GPU is the work, and the fan is not the CPU's
problem. It was arrived at by measurement, not assertion.

Post 3 is where the naive physics breaks. The affinity law says a 95 % -> 35 %
duty cut removes 95 % of fan power; the only real measurement of a server
fan duty cut says 87.5 %, and quiet-lab states duty as ranges, so the honest
answer is a band and not a number.

Every number is computed live from the repository's own modules and from
the committed run artifacts by the build script. `code/audit.py` fails the
build if a documented number drifts from the code.

Post 1 is the course post. It goes first because it is the one @neuralkian
and @freeCodeCamp have a reason to share: it quotes the course accurately,
credits it, and asks the question the course leaves open.

The framing is deliberately not "three companies, three verdicts". The
physics is identical everywhere; what changes is who holds the fan tray and
who pays the meter. That is the party worth talking to.

Repo: https://github.com/0xhzsa/quiet-vivobook
Method: https://github.com/0xhzsa/quiet-vivobook/blob/main/docs/HOW-IT-WORKS.md
Course: https://kiankyars.github.io/gigawatt/

---

**1/6**

> @neuralkian's "From Watts to Tokens" (@freeCodeCamp) follows one watt from
> the grid to GPU transistors and back out as heat.
> 
> Cooling chapter: I asked what it doesn't. What if you turn the fans down?
> 
> Measured on a laptop. Built the node model.
> github.com/0xhzsa/quiet-vivobook


---

**2/6**

> Measured on a Vivobook, 3 replicates per mode, paired:
> 
> Fan curve (Silent vs Balanced): NOT RESOLVED. -1.09 W, t=-0.61.
> CPU power limit (Quiet vs Balanced): 6.92% of work gone.
> 
> The fan is the cheap lever. The power limit is expensive.
> 
> controller/fan-scan/analyze-mode-run.py


---

**3/6**

> The maths, where the naive answer breaks.
> 
> Affinity law P~duty^3: a 95->35% cut should remove 95% of fan power.
> @0xAlcibiades measured 120W->15W on a real server: 87.5%.
> 
> Motors have a loss floor. And duty is a RANGE, so every saving is a
> BAND: 54.4-74.5%.
> 
> code/fanlaw.py


---

**4/6**

> 8-GPU node, 8x700W, 1kW tray, steady state.
> 
> The saving is a function of the room: 44% of fan power at
> 30C inlet, 85% at 18C.
> 
> The duty holding full boost is 53%, not 35%. At 35% you
> sit on the 83C throttle knee: 27% of the work
> gone.
> 
> code/thermal_model.py


---

**5/6**

> So I built the controller and measured it against itself.
> 
> EKF (die temp + sensor bias) -> MPC -> duty, on the same thermal
> model, noisy sensor, load that changes.
> 
> 160W of fans vs 221W for the cheapest constant
> duty at the same peak. 28% less.
> 
> code/closed_loop.py


---

**6/6**

> Where the meter sits decides who gets this.
> 
> Lambda @stephenbalaban @LambdaAPI: $1.43M/yr, own meter.
> Together @vipulved @togethercompute: $1.21M/yr, meter maybe
> @hypertec's. Modal @bernhardsson @modal: $7.31M/yr at its providers.
> 
> One BMC trace replaces the biggest assumption.


---

## Number provenance

| number | value | provenance |
|---|---|---|
| laptop: fan curve cost | **not resolved** (-1.09 W, paired t = -0.61) | **measured**, 3 replicates per mode, 317 samples, all on AC |
| laptop: CPU power limit cost | **6.92 %** of work | **measured**, 4 paired blocks, per-block range 88.4-99.2 % |
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
| full-boost threshold | 75 C | **assumed**; 5 C moves the headline 13 points |

## Who to tag, and why

Every handle below was checked against x.com and resolves to a live account.

| tag | role | why |
|---|---|---|
| **@neuralkian** | Kian Kyars, "From Watts to Tokens" | the cooling, PUE and power models the fleet arithmetic uses |
| **@freeCodeCamp** | hosts the course | 8 hours of the same physics, free |
| **@0xAlcibiades** | upstream maintainer, quiet-lab | the 120 W -> 15 W measurement everything is calibrated against |
| **@stephenbalaban** / **@LambdaAPI** | Lambda CTO + company | holds the BMC and the meter at ATL02 |
| **@EdgeConneX** | Lambda's Atlanta landlord | holds the site under the lease |
| **@vipulved** / **@togethercompute** | Together CEO + company | operates the clusters |
| **@hypertec** | Together's co-builder | brought the capacity, and may hold part of the meter |
| **@bernhardsson** / **@modal** | Modal CEO + company | no fans of its own; the $7.31M/yr bill is its providers' |
| **@CrusoeAI** | Crusoe | the same capacity-provider class |
| **@VoltagePark** | Voltage Park | owns air-cooled capacity, controls its own BMCs |
| **@WHITEFIBER** | WhiteFiber | a known Modal capacity customer |

## What to send with the thread

- `docs/HOW-IT-WORKS.md` - **the full account**: mechanism, derivations, per-party economics, falsification conditions
- `docs/METHOD.md` - the measurement method, confounds, and what invalidates a run
- `docs/PHYSICS.md` - the models and where every constant comes from
- `docs/REPRODUCE.md` - step by step, including the 30-day 8-GPU BMC protocol
- `code/fanlaw.py` - the calibrated fan law, with the band it carries
- `code/thermal_model.py` - steady-state solve, derived duty, inlet envelope
- `code/closed_loop.py` - EKF + MPC and the experiment that compares them
- `code/audit.py` - independent Decimal reference; 0 failures, 0 warnings
- `controller/fan-scan/mode-effect.ps1` - the v4 harness (the one that runs)
- `controller/fan-scan/analyze-mode-run.py` - the paired analysis and the noise floor
- `controller/fan-scan/mode-20261022-025525/` - the committed laptop run
- `controller/fan-scan/scheme-ab.ps1` - the power-scheme A/B harness
- `controller/fan-scan/RESULTS.md` - every run and what it does and does not prove
- `SELF-REVIEW.md` - the eleven defects we found in our own work, and what we did about them

## Approval

Not posted. The repo is public at https://github.com/0xhzsa/quiet-vivobook
and every file above is committed.
