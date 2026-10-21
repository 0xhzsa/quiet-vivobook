# The thread: 6 posts, each under 280 characters

Every post carries four things, because 280 characters is enough if you use
them: WHAT (the mechanism), WHY (the reason), the NUMBER (the evidence), and
WHERE (the artifact).

The full account - every derivation, the per-party economics, and the
conditions that would change our mind - is in `docs/HOW-IT-WORKS.md`.
Post 1 links the repo, which links the method.

Every number here is computed live from `code/` by the build script, and
`code/audit.py` fails the build if a documented number drifts from the code.

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
> Cooling chapter: I asked what it doesn't. Turn the fans down?
> 
> Same heat, less cooling, more throttle. Measured.
> 
> github.com/0xhzsa/quiet-vivobook


---

**2/6**

> Measured on the laptop, not a spreadsheet.
> 
> In-process load, completed-work counter. Balanced vs Quiet, governor paused,
> 4 paired blocks, 60s phases, AC only, restored in finally.
> 
> Quiet keeps 93.08% of the work. Cost 6.92%, range 88.4-99.2%.
> 
> The confounded run is committed too.


---

**3/6**

> Affinity law: P ~ duty^3, so 95->35% should remove 95% of fan power.
> @0xAlcibiades measured 120W -> 15W on a real server: 87.5%.
> 
> Fan motors have a loss floor. Fit P = base(a*d^3 + b*d)/(a+b).
> Duty is a RANGE, so b = 0.085-0.875 and the saving is a BAND.
> 
> code/fanlaw.py


---

**4/6**

> Thermal side, steady state. Die -> heatsink -> inlet -> ambient,
> convection ~ duty^0.8.
> 
> At 80% load the safe duty is 53%, not 35%. 35% is the
> 83C throttle knee: 27% of the work gone. And the
> answer moves with the room: 44% saved at 30C inlet,
> 85% at 18C.
> 
> code/thermal_model.py


---

**5/6**

> Is it better? Measured against itself.
> 
> EKF estimates die temp + sensor bias, MPC picks the duty. Noisy sensor,
> varying load. Closed loop 160 W of fans.
> 
> Cheapest CONSTANT duty at that peak: 221 W. 28% less,
> and it tracks a varying load.
> 
> code/closed_loop.py


---

**6/6**

> What each party gains.
> 
> Lambda @stephenbalaban @LambdaAPI: $1.43M/yr, own meter.
> Together @vipulved @togethercompute: $1.21M/yr, maybe
> @hypertec's. Modal @bernhardsson @modal: $7.31M/yr at its
> providers.
> 
> One BMC trace replaces the biggest assumption.


---

## What each post is doing

| post | what it is doing |
|---|---|
| 1 | the question, and the credit. the course asks where the heat goes; this asks what happens if you turn the fans down |
| 2 | the method. a work counter, paired blocks, AC enforced, restore in `finally` - and the confounded run kept on purpose |
| 3 | the first maths. the affinity law says 95 %, a real server measures 87.5 %, and the fit carries a band because the duty is a range |
| 4 | the second maths. the thermal solve, why 53 % is the duty and 35 % is the knee, and why the answer moves with the room |
| 5 | the result. the controller measured against the cheapest constant duty that holds the same peak temperature |
| 6 | the economics, split by who actually pays the meter, and the one measurement that would settle it |

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
| 8-GPU node, per year | $601.78 at $0.08/kWh, PUE 1.35 | **modelled** |
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
- `controller/fan-scan/scheme-ab.ps1` - the clean laptop A/B harness
- `controller/fan-scan/RESULTS.md` - write-path proof, invalid run, kept on purpose
- `SELF-REVIEW.md` - what is solid in this repo and what is not

## Approval

Not posted. The repo is public at https://github.com/0xhzsa/quiet-vivobook
and every file above is committed.
