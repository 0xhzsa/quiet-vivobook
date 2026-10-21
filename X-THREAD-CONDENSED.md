# The thread, condensed: laptop as GPU simulator

Positioning: **I don't own a GPU server. I own an ASUS Vivobook. So I made the laptop simulate one.**

Repo: https://github.com/0xhzsa/quiet-vivobook. Replace `[TARGET]` before posting.

---

**1/6**

> I don't own a GPU server. I own an ASUS Vivobook.
>
> So I built a thermal controller on the laptop and made it simulate an 8-GPU node.
>
> The laptop measured its own throughput cost. The simulation, calibrated to
> @0xAlcibiades' real 120W→15W server trace, produced the fan saving.
>
> Two measured anchors. One model bridge. All the code is public.
>
> 🧵

---

**2/6**

> **Anchor 1: laptop throughput cost (measured).**
>
> Mode 0→1→2→0 thermal run was confounded (37.2W/2.12M → 16.6W/1.00M).
> I kept it. Deleting bad runs is how projects start lying.
>
> Then I ran a clean power-scheme A/B: Balanced vs Quiet, governor paused,
> 4 blocks, balanced order, 8 threads, 60s phases.
>
> Result: quiet keeps 93.08% of balanced work. Cost: 6.92%.
> Range: 88.4% – 99.2%. All 4 blocks valid.
>
> Code: `controller/fan-scan/scheme-ab.ps1`
> Artifact: `controller/fan-scan/scheme-ab-latest-summary.json`

---

**3/6**

> **Anchor 2: server fan saving (measured, @0xAlcibiades).**
>
> 64-core Ampere server (Supermicro ARS-210M-NR):
> 120W → 15W fan power. 65 → 42 dB. 87.5% cut.
>
> That's a CPU server, not an 8-GPU node. But the physics transfers:
> fan affinity law (power ~ speed³), BMC duty control, A/B/A measurement shape.
>
> The only real fan saving I can cite. Thank you for publishing the trace.

---

**4/6**

> **The bridge: calibrated 8-GPU simulation.**
>
> I built an EKF+MPC thermal controller on the laptop using quiet-lab's
> physics and Kian Kyars' Gigawatt course models (PUE, cooling, power).
> Calibrated to match the 87.5% measurement (simulated: 86.25%).
>
> 8-GPU node (8×700W, 1kW fan tray), 95%→35% duty:
>   Fan: 881W → 121W (save 760W = 86.25%)
>   Work: 1.0 → 0.9485 (cost 5.15%)
>   Temp: 63.8C → 89.7C
>   Net: $520/node/yr ($839 fan − $318 throughput)
>
> Code: `code/server_thermal_controller.py`

---

**5/6**

> **The fleet math (modeled, not measured):**
>
> Lambda @stephenbalaban @LambdaAPI — ATL02, 1,176 air-cooled nodes:
>   $1.08–1.22M/yr at 1.3–1.8× fatigue. $1.56M at R=36.
>
> Together @vipulved @togethercompute — 8k air-cooled H100/H200:
>   $0.91–1.03M/yr. (36k-GPU headline is liquid: zero fan watts.)
>
> Modal @bernhardsson @modal — owns no fans. $0 to Modal.
>   $5.5–6.2M belongs to 13 providers. Disqualified for this claim.
>
> All conditional on air-cooled count, BMC access, and power contract.

---

**6/6**

> **The one-node test:**
> 1. Read FanPower / P12V_FAN / per-fan W via BMC
> 2. Set duty via IPMI raw 0x30 0x70 0x66
> 3. Fixed workload, A/B/A, 30 days
> 4. Count work and watts
>
> Pass: ≤5.15% throughput loss (simulated). Fail: >5.15% or >1%.
>
> Laptop harness: `controller/fan-scan/` (mode-effect v3 + scheme-ab)
> Server sim: `code/server_thermal_controller.py`
> Audit: `code/audit.py` (0 hard failures)
>
> One BMC trace settles it. Who has an air-cooled 8-GPU node?
>
> @0xAlcibiades @stephenbalaban @LambdaAPI @vipulved @togethercompute
> @bernhardsson @modal @kiankyars

---

## Handles

| target | founder | company | role |
|---|---|---|---|
| **Lambda** | [@stephenbalaban](https://x.com/stephenbalaban) | [@LambdaAPI](https://x.com/LambdaAPI) | CTO + company |
| **Together** | [@vipulved](https://x.com/vipulved) | [@togethercompute](https://x.com/togethercompute) | CEO + company |
| **Modal** | [@bernhardsson](https://x.com/bernhardsson) | [@modal](https://x.com/modal) | CEO + company |
| **quiet-lab** | [@0xAlcibiades](https://x.com/0xAlcibiades) | — | upstream maintainer |
| **Gigawatt** | [@kiankyars](https://x.com/neuralkian) | — | course author (PUE, cooling, power) |

## What to send with the thread

- `data/profiles.csv` — four measured laptop profiles
- `controller/fan-scan/scheme-ab.ps1` — clean A/B harness (no elevation)
- `controller/fan-scan/scheme-ab-latest-summary.json` — 4-block results (6.92%)
- `code/server_thermal_controller.py` — EKF+MPC 8-GPU sim, calibrated
- `code/audit.py` — independent Decimal/provenance audit (0 hard failures)

## Approval

Not posted. `[TARGET]` is still a placeholder. The repo is public at
https://github.com/0xhzsa/quiet-vivobook and the package is committed and pushed.