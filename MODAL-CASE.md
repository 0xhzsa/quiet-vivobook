# Modal: the fan bill Modal cannot capture

> Modal's $1B run rate implies roughly 48,000 active H100-equivalents. The fan
> bill behind that fleet is **$6.3–7.1M/yr** at 1.3–1.8× — real, and
> **0.63–0.71 % of revenue** (**$9.1M / 0.91 %** at R=36). Modal owns none of it. The
> company is a platform on top of 13
> capacity providers, not a fleet owner. The physics applies; the bill does not
> the cleanest demonstration of why ownership is the first term.

This is the fourth case in the project, and the third founder-led one. The
first proved the claim on a 24,000-H100 fleet with no founder attached. The
second pointed it at Lambda (qualified). The third pointed it at Together
(a partner). This one points it at **Modal** and at the providers behind it, founder/CEO
**@bernhardsson**, company **@modal_labs**.

The result is not a smaller win. It is a **different answer**: the fan claim does
not route to Modal at all.

---

## 0. The headline

Modal does not publish a GPU count. The fleet below is **derived** from its $1B
annualized run rate, its H100 list price, and an assumed 60 % utilization:

```
$1,000,000,000 / ($3.9492/GPU-hr × 8,760 h × 0.60) ≈ 48,177 H100-equivalents
floor(48,176.53 / 8) = 6,022 eight-GPU nodes = 48,176 modeled GPUs
```

This is a **scale estimate, not an upper bound**. Non-GPU revenue lowers the
true count; a lower realized price or lower utilization raises it. The direction
of the error is not known, so treat it as a scenario.

| item | value |
|---|---:|
| derived active fleet | **≈48,177 H100-equivalents (48,176 modeled)** |
| nodes | **6,022** |
| fan energy | **$5,412,388/yr** |
| thermal fatigue | **$3,688,475/yr at R=36; $0.88–$1.69M at 1.3–1.8×** |
| **fan bill, at the providers** | **$7,311,143/yr at R=36; $4.50–$5.31M at 1.3–1.8×** |
| as % of ARR | **0.63–0.71 % at 1.3–1.8×; 0.91 % at R=36** |
| capacity value of freed watts | $92,991,338/yr gross |
| **Modal's direct saving** | **$0** |
| **Modal's capacity value** | **$0** |
| utilization lever, 35 % → 60 % | **$416,666,667/yr gross** |

The fan bill is real, but it is only **0.63–0.71 % of ARR** at 1.3–1.8×
(**0.91 %** at R=36). The utilization
lever is a different business, not a like-for-like saving: it is gross revenue
at list price, and it requires demand, not just packing. The comparison is a
scale check, not a claim that one dollar of fan saving equals one dollar of
utilization revenue.

The capacity value is not a saving, and it is not Modal's: it is the GPU revenue
the freed watts could support at Modal's list price, on nodes owned by someone
else.

---

## 1. Why Modal was on the list

Modal is the most developer-visible GPU platform of the cycle. It clears the
scale and reach parts of the filter:

| criterion | Modal |
|---|---|
| air-cooled | its providers' H100/H200 nodes can be air-cooled; Modal does not control them |
| bare metal | no; serverless containers on a multi-cloud capacity pool |
| thousands of GPUs | ~48k derived from $1B ARR |
| reachable | founder/CEO **@bernhardsson** + **@modal_labs** |
| public price | H100 **$3.95/GPU-hr**, H200 **$4.54/GPU-hr**, B200 **$6.25/GPU-hr** |
| owns the node / BMC / power bill | **no / no / no** |

The filter is not "is this a good company". It is "can a fan controller be
installed, measured, and paid for by this target". Modal fails the third
question, and that is decisive.

---

## 2. What Modal actually is

Modal is a serverless compute platform. It built its own container runtime,
scheduler, filesystem, and networking, and it pools capacity across other
providers:

- **20+ clouds** in the capacity pool (Modal, Oct 2026).
- **13 cloud partners** (DCD, Oct 2026).
- A known customer of **WhiteFiber** (DCD).
- **$1B annualized run rate**, **$750M Series D** at a **$15.75B** post-money
  valuation (Oct 2026).
- **$355M Series C** five months earlier at **$4.65B**; **$80M Series B** at
  **$1.1B** (Sep 2025).
- 200+ employees across NY, SF, and Stockholm.

The decisive public statements:

> "We don't have our own data centers. We just run across a lot of..."
> — Akshat Bubna, co-founder/CTO, Latent Space, 2026-07-08

> "The company does not own/operate data centers, but works with other cloud
> providers. Currently, it has 13 cloud partners."
> — DataCenterDynamics, 2026-10-16

That is the ownership question in two sentences. A fan controller needs a fan, a
BMC, and a power bill. Modal has none of the three on its own balance sheet.

**Correction worth making explicit:** some press coverage quotes a neocloud CEO
saying it is "looking at land and considering building our own facilities" about
two years out. That quote belongs to **Neysa**, the Indian AI cloud, not Modal.
Modal's public position is that it does not own or operate data centers. Do not
attribute the build-out quote to Modal.

---

## 3. The fleet behind the ARR

The derived fleet scales linearly with ARR. The fan bill is the **R=36**
scenario; at 1.3–1.8× it is 0.63–0.71 % of ARR:

| ARR | active GPUs | nodes | fan bill | % of ARR |
|---:|---:|---:|---:|---:|
| $0.25B | 12,044 | 1,505 | $2,274,460 | 0.91 % |
| $0.50B | 24,088 | 3,011 | $4,550,431 | 0.91 % |
| **$1.00B** | **48,177** | **6,022** | **$7,312,387** | **0.73 %** |
| $2.00B | 96,353 | 12,044 | $18,201,725 | 0.91 % |

Under R=36 the percentage is constant because both sides scale with ARR. That
is the point: **the fan bill is a fixed fraction of revenue under this model**,
and it is a small fraction. At $1B ARR, every $1M of fan saving is 0.1 % of revenue.

The derivation is deliberately conservative in one direction and generous in
another:

- **Generous:** it assumes every revenue dollar is an H100 GPU-hour at list
  price. CPU, memory, storage, and sandboxes are not free, so the true GPU count
  is lower.
- **Conservative:** it assumes 60 % utilization. A lower utilization would imply
  more GPUs for the same revenue, and a larger fan bill.

Both assumptions are printed by `modal_case.py`. Neither is a measurement.

---

## 4. The fan bill is real but not Modal's

Using the same per-node physics as the other cases — 1 kW fan, 95 % → 35 %
duty, $0.08/kWh, PUE 1.35 — the derived fleet's fan bill is:

| item | value |
|---|---:|
| energy | **$5,412,388/yr** |
| fatigue | **$3,688,475/yr** |
| **total** | **$7,312,387/yr** |
| capacity (gross) | **$92,991,338/yr** |

Across 13 providers, the average share is:

```
$7,312,387 / 13 = $562,491/yr per provider
```

That is the size of the prize for each capacity provider — not for Modal. The
pass-through function makes the split explicit:

| provider share of the saving | providers keep | Modal keeps |
|---:|---:|---:|
| 100 % (current model) | **$7,312,387** | **$0** |
| 50 % | $4,550,431 | $4,550,431 |
| 0 % | $0 | **$7,312,387** |

Under the current model, the providers own the nodes, pay the power, and keep
the saving. Modal keeps nothing. The only way Modal captures it is a
**power-indexed contract** with its providers — lower wholesale rates in exchange
for the controller. There is no public evidence of such a contract, and it is
not Modal's stated business.

---

## 5. The lever Modal actually has: utilization

Modal's business is not fan power. It is packing demand onto a fleet so that
GPUs are not idle. The same fleet at 35 % and 60 % utilization:

```
extra GPU-hours = 48,176.53 × 8,760 × (0.60 − 0.35)
                ≈ 105,506,600 GPU-hours/yr
gross revenue   ≈ 105,506,600 × $3.9492
                ≈ $416,666,667/yr
multiplier      = 0.60 / 0.35 = 1.71×
```

| lever | annual value | ratio (not like-for-like) |
|---|---:|---:|
| fan bill (providers' P&L) | $4.50–5.31M at 1.3–1.8×; $7.31M at R=36 | 1× |
| utilization 35 % → 60 % | **$416,666,667** | **46–66×** |

The utilization number is **gross revenue at list price**, not profit, and the
35 % / 60 % endpoints are illustrative. The ratio is a scale check, not a claim
that one dollar of fan saving equals one dollar of utilization revenue. The
honest conclusion is smaller: the fan bill is under 1 % of ARR and belongs to
the providers; Modal's own lever is a different business.

This is also why the tweet's claim, even where true, is not a universal pitch.
The right target is the party that owns the fan and pays the meter. For Modal,
that party is 13 other companies.

---

## 6. The qualification test

`modal_case.py` encodes the test as a pure function:

```python
def qualification(owns_datacenter, owns_nodes, controls_bmc, pays_power):
    if controls_bmc and pays_power:
        return "qualified"
    if controls_bmc and not pays_power:
        return "partner"
    return "provider"
```

The three cases:

| target | owns DC | owns nodes | controls BMC | pays power | verdict |
|---|---|---|---|---|---|
| Lambda | no (leases) | yes | yes* | yes* | **qualified** |
| Together | no | partial | yes* | partial | **operator or partner** |
| Modal | no | no | no | no | **the node providers** |

\* Lambda's BMC and power-payment cells are assumptions, not public disclosures.

At 1 kW and R=36, to capture $1M directly a provider would need to own **6,592 GPUs**
(662 eight-GPU nodes); at 1.3–1.8× the count is **6,792–7,664**. It owns zero.
The **verdict** does not depend on those parameters. The exact GPU count does.

---

## 7. What would change the verdict

The verdict is about the current model, not about Modal's ability to execute.
Four things would change it:

1. **Modal builds or leases its own data centers.** Not in the public record
   today; the "considering own facilities" quote is Neysa's, not Modal's.
2. **Modal acquires a neocloud or signs a power-indexed lease** with BMC access
   and a share of the energy saving. Then `pays_power` becomes true and the
   verdict moves to qualified.
3. **Modal requires fan telemetry from its 13 providers as a procurement term.**
   That gives it measurement, not capture. The saving still lands on the
   provider unless the contract passes it through.
4. **Modal's platform fee is a share of provider cost.** If Modal takes 20 % of
   a provider's saving, the R=36 $9.1M becomes $1.8M to Modal; at 100 %, $9.1M.
   No public evidence of either, but it is the mechanism to watch.

Until one of those happens, the honest answer is: **do not pitch Modal the fan
claim.** Pitch the providers, or pitch Modal a utilization story it already
knows.

---

## 8. What is not claimed

- **Modal does not own fans.** The fan bill is its providers', not its own.
- **The ≈48,177-GPU fleet is derived**, not published. It is a scale estimate, not an upper bound: lower price or utilization raises it.
- **The 1 kW fan, PUE, tariff, and fatigue parameters are assumptions**, the
  same ones used in the other cases.
- **The utilization gain is illustrative.** 35 % and 60 % are endpoints, and the
  revenue is gross at list price, not profit.
- **No claim that Modal is a bad company.** It is a bad *target for this claim*,
  which is a different statement.
- **No liquid-node claim.** Modal's providers may run liquid nodes; the model
  applies only to air-cooled H100/H200-class nodes.
- **No throughput or acoustic credit.**

---

## 9. What we need from Modal

For the fan claim: **nothing**. The claim does not route to Modal.

If Modal wants to pursue the provider-side saving anyway, the data ask is:

1. The provider list and which provider owns the nodes.
2. Which contracts are power-indexed, and who keeps an energy saving.
3. BMC access and fan telemetry on one air-cooled node.
4. PUE and tariff per site.
5. The GPU mix and utilization, for the utilization comparison.

For the utilization claim, the ask is different: actual utilization, take rate,
and GPU mix. That is Modal's own data, and it is the number that matters to
Modal.

---

## 10. Reproduce it

```powershell
uv run python code/modal_case.py --selftest   # 17 checks on the algebra
uv run python code/modal_case.py              # derived fleet, pass-through, utilization
uv run python code/modal_case.py --arr 2e9 --provider-share 0.5
```

Every number is derived from a printed input. `--selftest` checks the
ARR-to-GPU derivation, the fan bill, the pass-through split, the qualification
function, and the utilization gain against hand-computed values.

---

## 11. Sources

- Modal, **2026-10-14**: $1B annualized run rate; $750M Series D at $15.75B;
  capacity pool across 20+ clouds. <https://modal.com/blog/1-billion-annualized-run-rate-series-d>
- DataCenterDynamics, **2026-10-16**: Modal "does not own/operate data centers";
  13 cloud partners; WhiteFiber customer; Series C $355M at $4.65B; Series B
  $80M at $1.1B. <https://www.datacenterdynamics.com/en/news/ai-cloud-modal-raises-750m-in-series-d-funding-round/>
- Latent Space, **2026-07-08**: Akshat Bubna, "We don't have our own data
  centers." <https://www.latent.space/p/modal2026>
- Modal pricing, 2026: H100 SXM5 $0.001097/sec ($3.9492/hr); H200 SXM
  $0.001261/sec ($4.5396/hr); B200 $0.001736/sec ($6.2496/hr).
  <https://modal.com/pricing>
- Erik Bernhardsson, founder/CEO, @bernhardsson.
  <https://x.com/bernhardsson>
- NVIDIA DGX H100: ~10.2 kW per 8-GPU system.
  <https://docs.nvidia.com/dgx/dgxh100-user-guide/introduction-to-dgxh100.html>

---

The method is the same as the other three cases. The difference is the answer:
for Modal, the correct output is **zero**, and the correct next step is to stop
pitching the fan claim and look at the utilization business the company already
owns.
