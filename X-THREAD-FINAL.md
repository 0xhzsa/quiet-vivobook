# The thread, final: laptop as GPU simulator — 6 posts, ≤280 chars each

Style: Matty Mo. Bold. Direct. No filler. Every word earns its place.

Repo: https://github.com/0xhzsa/quiet-vivobook. Replace `[TARGET]` before posting.

---

**1/6**

> I don't own a GPU server. I own an ASUS Vivobook.
>
> So I built a thermal controller on my laptop and made it simulate an 8-GPU node.
>
> Laptop measured throughput cost: 6.92%. Simulation calibrated to 120W to 15W.
>
> Two measured anchors. One model. All code public.
>
> thread

---

**2/6**

> Anchor 1: laptop throughput cost (measured)
>
> Thermal A-B-A was confounded (37.2W/2.12M to 16.6W/1.00M). I kept it.
>
> Clean A/B: Balanced vs Quiet, governor paused, 4 blocks.
> Quiet keeps 93.08% of work. Cost: 6.92%. Range: 88.4-99.2%.
>
> Code: scheme-ab.ps1

---

**3/6**

> Anchor 2: server fan saving (measured)
>
> @0xAlcibiades quiet-lab: 64-core Ampere. 120W to 15W fan. 65 to 42 dB. 87.5%.
>
> CPU server, not GPU. But physics transfers: fan affinity (P~N3), BMC duty
> control, A/B/A shape.
>
> The only real fan saving I can cite. Thank you.

---

**4/6**

> The bridge: calibrated 8-GPU simulation
>
> EKF+MPC on laptop. quiet-lab physics + Gigawatt. Calibrated to 87.5%
> (simulated 86.25%).
>
> 8x700W, 1kW fan, 95% to 35%:
> Fan 881 to 121W (save 760W). Work 1.0 to 0.9485 (cost 5.15%).
> Temp 63.8-89.7C. Net $520/node/yr.
>
> server_thermal.py

---

**5/6**

> Fleet math (modeled, not measured)
>
> Lambda: 1,176 nodes: $1.08-1.22M/yr
> Together: 8k air-cooled: $0.91-1.03M/yr
> (36k-GPU headline is liquid: zero fan watts)
> Modal: owns no fans. $0. Disqualified.
>
> BMC access required.

---

**6/6**

> The one-node test:
> 1. Read FanPower via BMC
> 2. Set duty via IPMI raw 0x30 0x70 0x66
> 3. Fixed workload, A/B/A, 30 days
> 4. Count work + watts
>
> Pass: 5.15% loss or less.
>
> Laptop harness: controller/fan-scan/
> Server sim: code/server_thermal.py
> One BMC trace settles it.

---

## Handles

| target | founder | company | notes |
|---|---|---|---|
| **Lambda** | [@stephenbalaban](https://x.com/stephenbalaban) | [@LambdaAPI](https://x.com/LambdaAPI) | CTO + company |
| **Together** | [@vipulved](https://x.com/vipulved) | [@togethercompute](https://x.com/togethercompute) | CEO + company |
| **Modal** | [@bernhardsson](https://x.com/bernhardsson) | [@modal](https://x.com/modal) | CEO + company |
| **quiet-lab** | [@0xAlcibiades](https://x.com/0xAlcibiades) | — | upstream maintainer, 120W to 15W |
| **Gigawatt** | [@kiankyars](https://x.com/neuralkian) | — | course: PUE, cooling, power |

## Approval

Not posted. `[TARGET]` is still a placeholder. The repo is public at
https://github.com/0xhzsa/quiet-vivobook and the package is committed and pushed.