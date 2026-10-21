# The thread, v2: laptop first, then the fleets

Positioning: **founder/CTO of an air-cooled GPU cloud who controls the BMC and
pays the power bill.** Liquid-cooled and landlord-owned capacity are excluded.

The thread leads with the thing that was actually built and measured: a
closed-loop thermal controller on an ASUS Vivobook, its real write/read-back
path, and the fact that the A-B-A throughput run was confounded. That refusal
is the credibility. Then it bridges to servers with the same measurement shape,
and finally to the founders.

Replace `[REPO_URL]` and `[TARGET]` before posting.

---

**1/15**

> I don't own a GPU server. I own an ASUS Vivobook.
>
> So I built the thermal controller on the laptop first: real actuator, real
> power/temperature logs, real work counts.
>
> Then I used it to test the "7-figure fan savings" claim.
>
> The laptop said: not free. 🧵

---

**2/15**

> Machine: Vivobook 15 X1502VA, i9-13900H, 14C/20T, 16 GB, Windows 11, BIOS
> 306.
>
> Stack: PowerShell + LibreHardwareMonitor. Writes the ASUS thermal mode, reads
> it back, logs package W, temps, work/s.
>
> Artifacts: `data/profiles.csv`, `controller/fan-scan/`. [REPO_URL]

---

**3/15**

> Four profiles, same workload:
>
> stock: 25.3 W, 2,187 work/s
> efficient: 17.9 W, 1,784 (81.6%)
> no-turbo: 10.7 W, 868 (39.7%)
> no-turbo80: 8.7 W, 695 (31.8%)
>
> Power falls. Work falls with it. That is the whole tension.

---

**4/15**

> The honest part: my A-B-A run was confounded.
>
> mode 0: 37.2 W, 2.12M work
> mode 1: 26.3 W, 1.54M
> mode 2: 12.5 W, 0.96M
> mode 0 again: 16.6 W, 1.00M
>
> The baseline did not reproduce. So I do not claim a clean throughput cost.

---

**5/15**

> What is proven:
> - actuator writes, reads back, restores
> - modes are distinct power/thermal states
> - harness counts work, not just watts
>
> Not proven:
> - any server fan saving
> - any clean throughput cost
>
> I kept the invalid run. Deleting it is how a project starts lying.

---

**6/15**

> On a laptop, 29% less power for 18% less work can be fine.
>
> On a GPU cloud, work is revenue. 18% is not a trade. It is an outage.
>
> That is why the next test is a server A/B, not a bigger spreadsheet.

---

**7/15**

> The method transfers:
> read fan power -> set duty -> hold a fixed workload -> A/B/A -> count work.
>
> The laptop actuator is CPU power. The server actuator is a BMC fan duty.
>
> The measurement is the same shape. The hardware is not.

---

**8/15**

> The fan math, one 8-GPU air-cooled node:
>
> 1 kW tray at 95% duty.
> 95 -> 35%: (35/95)^3 = 0.05.
> 950 W saved.
> 950 W x 8,760 h x $0.09/kWh x PUE 1.4 = $1,048/node/yr.
>
> 1,000 nodes = $1.05M/yr.

---

**9/15**

> The only real server measurement I can cite is @0xAlcibiades' quiet-lab:
>
> 64-core Ampere server: 120 W -> 15 W fan power, 65 -> 42 dB.
>
> That is 87.5%, not 95%.
>
> At 1 kW: 875 W, $966/node/yr. Seven figures moves from 954 to 1,036 nodes.
>
> Thank you for publishing the trace.

---

**10/15**

> Fatigue is the second leg, and it gets oversold:
>
> failures avoided = afr x share x (1 - 1/R)
> 3%/yr x 35% x (1 - 1/36) x $60k = $612/node/yr
> R=1.3: $145
> R=1.8: $280
>
> R=36 is a 12->2 C scenario. My laptop simulator says 1.3-1.8x. Quote the
> range.

---

**11/15**

> Now real fleets. Any air-cooled node with a BMC and a power meter can run the
> same test.
>
> The fleet numbers below are a model, not a measurement.
>
> Liquid is excluded: no fan tray, no claim.
>
> The next three cases differ on three things: fan, BMC, and who pays the meter.

---

**12/15**

> Lambda: @stephenbalaban + @LambdaAPI.
>
> ATL02 is 12 MW air-cooled, 1,176 nodes.
> At 1 kW: $1.23-1.39M/yr at 1.3-1.8x ($1.78M at R=36).
>
> One BMC fan trace from ATL02 replaces the model's biggest guess.
>
> Qualified on the public record; conditional on the power contract.

---

**13/15**

> Together: @vipulved + @togethercompute.
>
> 8,000 air-cooled H100/H200: $1.04-1.18M/yr at 1.3-1.8x.
> The 36,000-GPU headline is liquid: zero fan watts, zero claim.
>
> At 8k it needs ~85-96% of the power bill.
>
> Conditional: air-cooled count and ownership are not public.

---

**14/15**

> Modal: @bernhardsson + @modal.
>
> Owns no fans and no nodes. The $6.3-7.1M fan bill belongs to its 13
> providers. $0 to Modal.
>
> Its lever is utilization, a different business.
>
> Disqualified for this claim, not for competence.

---

**15/15**

> The test I want on one node:
> 1. read FanPower / P12V_FAN / per-fan W
> 2. set duty via BMC
> 3. fixed workload, A/B/A, 30 days
> 4. count work and watts
>
> Pass: <=0.625% throughput loss. Fail: ~20.6% (my simulation) or >1%.
>
> Code: [REPO_URL]. One trace settles it.

---

## Handles

| target | founder | company | notes |
|---|---|---|---|
| **Lambda** | [@stephenbalaban](https://x.com/stephenbalaban) | [@LambdaAPI](https://x.com/LambdaAPI) | CTO + company |
| **Together** | [@vipulved](https://x.com/vipulved) | [@togethercompute](https://x.com/togethercompute) | CEO + company |
| **Modal** | [@bernhardsson](https://x.com/bernhardsson) | [@modal](https://x.com/modal) | CEO + company |
| **quiet-lab** | [@0xAlcibiades](https://x.com/0xAlcibiades) | — | upstream maintainer; GitHub `0xAlcibiades/quiet-lab`; commit author Alcibiades Athens |

## What to send with the thread

- `data/profiles.csv` — the four measured laptop profiles.
- `controller/fan-scan/RESULTS.md` — write-path proof, invalid run, confounded run.
- `controller/fan-scan/run.ps1` — read-only sensor map.
- `controller/fan-scan/run-devs.ps1` — write/read-back/restore proof.
- `code/cycling.py` — rainflow, Coffin-Manson, Norris-Landzberg, Miner.
- `code/case.py` — fan + fatigue model, R=36 scenario.
- `code/audit.py` — independent Decimal/provenance audit.

## Approval

Not posted. `[REPO_URL]` and `[TARGET]` are placeholders. Nothing committed or
pushed; the directory is not a git repository.
