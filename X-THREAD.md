# The thread

Twelve posts. One node class: an air-cooled **8-GPU node with a 1 kW fan tray**.
Every number is checkable against `CASE-STUDY.md`, `THREE-CASES.md`, and
`code/audit.py`. Repo: https://github.com/0xhzsa/quiet-vivobook. Replace `[TARGET]` before posting.

The audience is the founder/CTO of an air-cooled GPU cloud who **controls the
BMC and pays the power bill**. If the fans belong to a landlord or a capacity
provider, this is not that operator's saving. Say that early; it is the whole
positioning.

The hook is the gap between the textbook and the measurement: the fan law says
95 % of fan power disappears at 35 % duty; the upstream project's one real
server measurement says 87.5 %. That gap is the argument.

---

**1/12**

> The cheapest megawatt in AI is the fan tray.
>
> The textbook says 95 % of its power disappears at 35 % duty. The upstream
> server measurement says 87.5 %.
>
> That gap is the whole argument. 🧵
>
> For operators who own the fans and pay the meter.

---

**2/12**

> Fan law: shaft power ∝ duty³.
>
> 95 → 35 %: (35/95)³ = 0.05.
>
> A tray drawing 1 kW at 95 % drops to 50 W; 950 W saved.
>
> 950 W × 8,760 h × $0.09/kWh × PUE 1.4 = **$1,048/node/yr**.
>
> PUE 1.4 means 1.4 W at the meter per server watt. Ideal cubic; everyone
> quotes it.

---

**3/12**

> Now the measurement.
>
> Upstream `quiet-lab` measured a 64-core Ampere server: 120 W → 15 W fan power,
> 65 → 42 dB.
>
> That is **87.5 %**, not 95 %.
>
> At 1 kW: **875 W**, or **$966/node/yr**.
>
> Seven figures moves from **954 nodes** to **1,036**.

---

**4/12**

> Keep one node class: 8 GPUs, 1 kW fan tray.
>
> 1,000 nodes: **$1.05M/yr** ideal, **$0.97M** measured.
>
> 24k H100s = 3,000 nodes = **$2.9–3.1M/yr**.
>
> 300 W fans? Divide by 3.3: **~$315/node**; **3,179 nodes** for $1M.
>
> Scale claim, not universal.

---

**5/12**

> Fatigue gets oversold.
>
> Failures avoided/node-yr = afr × share × (1 − 1/R).
>
> afr 3 %/yr, share 35 %, $60k replacement:
> R=36 → **$612/node/yr**
> R=1.8 → **$280**
> R=1.3 → **$145**
>
> R=36 is a 12→2 °C scenario. Our laptop cycle simulator's **Coffin-Manson**
> range is **1.3–1.8×**.

---

**6/12**

> Ownership is the founder question.
>
> Direct saving = your share × (energy + fatigue).
>
> Capacity is not a saving: it needs capex, demand, and a power constraint.
>
> If you don't pay the meter, the dollar belongs to your landlord.
>
> Three cases next.

---

**7/12**

> **Lambda ATL02**: 1,176 nodes, $0.08/kWh, PUE 1.35.
>
> $1.06M energy at 1 kW; $0.97M at the measured curve.
>
> At 1 kW the energy leg alone is seven figures. Qualified.
>
> At the measured curve it needs a small fatigue credit.
>
> One BMC reading or trace settles which.

---

**8/12**

> **Together 8k**: $0.08/kWh, PUE 1.35. $0.90M energy; **$1.04–1.18M** with
> fatigue.
>
> At 8k it needs **~85–96 %** of the power bill.
>
> Boundary: **~6,800–7,700 owned GPUs**.
>
> The 36k GB200 headline is liquid: zero fan watts, zero claim.
>
> Conditional.

---

**9/12**

> **Modal** owns no fans and no nodes. At $0.08/kWh, PUE 1.35, the
> **$6.3–7.1M** fan bill is **0.63–0.71 %** of ARR at 1.3–1.8×; **$9.1M**
> at R=36. It belongs to its providers.
>
> Its own lever is utilization, a different business, not a like-for-like
> saving.
>
> Disqualified as a target.

---

**10/12**

> Where the claim dies: throughput.
>
> The controller I could test: a laptop CPU power governor. Simulation retains
> **77–81 %** of stock work.
>
> An 8-GPU node grosses ~$167,772/yr. A 20.6 % work loss is **~$34,568**.
> Modeled saving is **~$1.0–1.5k**.
>
> A 1 % throughput loss exceeds it.

---

**11/12**

> The test:
>
> One BMC reading — `FanPower`, `P12V_FAN`, per-fan watts, or a 30-day trace.
>
> One answer: **who pays the meter?**
>
> If the tray is 300 W, the number shrinks. If throughput drops, the saving is
> fake. If the site is liquid, zero.
>
> The reading decides.

---

**12/12**

> Code, math, falsification: https://github.com/0xhzsa/quiet-vivobook
>
> If you run an air-cooled GPU cloud and control the BMC, I'll send the model.
> One reading replaces the load-bearing physical guess.
>
> [TARGET] — want to check it on one node?

---

## Single-post version

> Every 1,000 air-cooled 8-GPU nodes hides **~$0.97–1.05M/yr** in fan power at
> $0.09/kWh, PUE 1.4, 95 → 35 % duty.
>
> The fan law says 95 % of that power disappears. The upstream server
> measurement says 87.5 %. That gap is the whole argument.
>
> 24k H100s ≈ **$2.9–3.1M/yr**. The seven-figure line is **~954–1,036 nodes**.
>
> Code + model + falsification: https://github.com/0xhzsa/quiet-vivobook

## Do not tag (Crusoe)

> @CrusoeAI — your Abilene campus is closed-loop liquid. The GPU trays have no
> fan energy to save, so this claim does not apply. Leaving you out on purpose.

Crusoe is the best narrative fit and the wrong physics. Tagging it with a fan
claim would be the fastest way to lose the argument.

## Numbers to have ready in replies

| question | answer |
|---|---|
| "What if fans draw 300 W?" | ~$315/node/yr; **3,179 nodes** for $1M |
| "What if PUE is 1.1?" | multiply by 1.1/1.4 = **0.79** |
| "What if duty only falls 95→60 %?" | `(0.6/0.95)³` = 0.25, so 75 % of fan power is saved; 1,000 nodes = **~$0.83M** |
| "Liquid-cooled?" | excluded; no fan tray, no claim |
| "Did you measure an 8-GPU server?" | no. The 120→15 W number is a 64-core CPU server; the 8-GPU case is a model. That is exactly what the BMC ask is for |
| "Is the fatigue leg real?" | conditional: **$145–$280/node** at 1.3–1.8×; $612 is the R=36 best case |
| "Why not just cap CPU power?" | that is the laptop actuator, not a server fan controller. The fan claim needs BMC/fan-duty control at constant compute |
| "What about the capacity upside?" | not a saving. It is gross revenue that needs capex, demand, and a power constraint |
| "Why not Modal?" | it owns no fans and no nodes; the bill belongs to its providers |

## Posting checklist

- [x] Repo is public: https://github.com/0xhzsa/quiet-vivobook
- [ ] `uv run --no-project python code/case.py --selftest` passes on a clean machine
- [ ] `uv run --no-project python code/audit.py` exits 0; `--strict` exits 1 by design and the four warnings are disclosed
- [ ] The tag is one qualified operator, not a list; do not tag liquid-only sites
- [ ] The post says **air-cooled** and **8-GPU node** explicitly
- [ ] The first number quoted is the **875–950 W range**, not a point estimate
- [ ] The reply to any challenge is a number, not a defense
- [ ] No claim of measured server fans, server dBA, or field failures
- [ ] No claim that the laptop controller is a server fan controller
- [ ] Publication and tagging await approval
