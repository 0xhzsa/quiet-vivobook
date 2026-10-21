# The thread, final: laptop as GPU simulator - 6 posts, each under 280 chars

Every number below is measured, modeled, or cited. Provenance is in the repo.
The model was recalibrated after the first draft: the naive affinity law
overstated the fan saving by 9 points, and the fleet numbers came down with it.

Repo: https://github.com/0xhzsa/quiet-vivobook

---

**1/6**

> I don't own a GPU server. I own an ASUS Vivobook.
> 
> So I built a thermal controller on my laptop and made it simulate an 8-GPU node.
> 
> Measured laptop throughput cost. Calibrated server fan model. Public fleet
> arithmetic. Every number traceable to a file.
> 
> thread


---

**2/6**

> Anchor 1, measured: the laptop's throughput cost.
> 
> Thermal A-B-A was confounded (37.2W/2.12M -> 16.6W/1.00M). I kept it.
> 
> Clean A/B: Balanced vs Quiet, governor paused, 4 paired blocks.
> Quiet keeps 93.08% of work. Cost: 6.92%. Range 88.4-99.2%.
> 
> controller/fan-scan/scheme-ab.ps1


---

**3/6**

> Anchor 2, measured by @0xAlcibiades: 120W -> 15W fan on a real
> 64-core Ampere server. 87.5% cut. 65 -> 42 dB.
> 
> The affinity law says 95%. It is wrong. Real fan motors have a loss floor
> that does not vanish with speed. Fit: P = base*(a*d^3 + b*d)/(a+b), b=0.342.
> 
> code/fanlaw.py


---

**4/6**

> The bridge: 8-GPU node, 8x700W, 1kW fan tray, steady state.
> 
> The saving is not a constant. It is a function of GPU load:
> 70% load -> 91% fan saved. 80% -> 86%. 100% -> 55%.
> 
> At 80% load the model lands within 1.4 points of the measured 87.5%.
> 
> code/server_thermal_controller.py


---

**5/6**

> Which duty should you actually run?
> 
> The one that holds 75C, where the GPU still runs at full boost.
> 52.9% duty. 72.2% fan saved. Zero throughput cost.
> 
> The 83C knee saves 86% and costs 26.7% of work.
> Saturated fleet: $8,640 revenue vs $839 power.
> 
> A number, not a plan.


---

**6/6**

> Fleet math, safe duty, $0.08/kWh, PUE 1.35:
> 
> Lambda @stephenbalaban @LambdaAPI: 1,176 nodes, $707k/yr
> Together @vipulved @togethercompute: 8k, $602k/yr
> Modal @bernhardsson @modal: owns no fans. $0.
> 
> One BMC fan trace replaces the biggest input.
> github.com/0xhzsa/quiet-vivobook


---

## Handles

| target | founder | company | notes |
|---|---|---|---|
| **Lambda** | [@stephenbalaban](https://x.com/stephenbalaban) | [@LambdaAPI](https://x.com/LambdaAPI) | CTO + company |
| **Together** | [@vipulved](https://x.com/vipulved) | [@togethercompute](https://x.com/togethercompute) | CEO + company |
| **Modal** | [@bernhardsson](https://x.com/bernhardsson) | [@modal](https://x.com/modal) | CEO + company |
| **quiet-lab** | [@0xAlcibiades](https://x.com/0xAlcibiades) | - | upstream maintainer, 120W -> 15W |
| **Gigawatt** | [@kiankyars](https://x.com/neuralkian) | - | course: PUE, cooling, power |

## Number provenance

| number | value | provenance |
|---|---|---|
| laptop throughput cost | 6.92% | **measured**, this machine, 4 paired blocks |
| quiet-lab fan saving | 87.5% | **measured**, @0xAlcibiades, 64-core CPU server |
| 8-GPU safe duty at 80% load | 52.9% | **modeled**, steady-state thermal solve |
| 8-GPU fan saving at 80% load | 72.2% | **modeled**, calibrated fan law |
| 8-GPU model vs measurement | 86.1% vs 87.5% | **cross-check**, 1.4 points apart |
| 8-GPU fan saving at 100% load | 55.2% | **modeled** |
| Lambda ATL02 energy leg | $707,449/yr | **modeled** on public anchors |
| Together 8k energy leg | $601,572/yr | **modeled** on public anchors |
| Modal | $0 | **disqualified**, no fans, no nodes |

## What to send with the thread

- `code/fanlaw.py` - the calibrated fan power law, with the derivation
- `code/throughput.py` - the throughput debit, in both capacity regimes
- `code/server_thermal_controller.py` - steady-state thermal solve and safe duty
- `code/audit.py` - independent Decimal reference, 0 failures 0 warnings
- `controller/fan-scan/scheme-ab.ps1` - the clean laptop A/B harness
- `controller/fan-scan/RESULTS.md` - write-path proof, invalid run, kept on purpose

## Approval

Not posted. The repo is public at https://github.com/0xhzsa/quiet-vivobook
and every file above is committed.
