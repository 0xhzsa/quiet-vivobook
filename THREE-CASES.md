# Three founder-led cases: one arithmetic, three different meters

> The same arithmetic, applied to three fleets, produces three different
> answers. That is the point. A fan controller needs three things: a fan, a
> BMC, and a power bill you actually pay. Lambda has the fan and a plausible
> BMC/power bill; the last two are assumptions to verify. Together has the
> first two and only part of the third. Modal has none of them.

This is the consolidated result of the three founder-led cases:

| case | anchor | direct saving | capacity value | verdict |
|---|---|---:|---:|---|
| **Lambda** | ATL02 12 MW, 9,408 GPUs | **$1.23–1.39M/yr** | **$18.3M/yr** | **the operator** |
| **Together** | 8,000 H100/H200, 1,000 nodes | **$0.75[‐‑‒–—―-]0.88M/yr** at 1.3[‐‑‒–—―-]1.8[‐‑‒–—―-] | **$10.4M/yr** | **operator or partner** |
| **Modal** | 48,177 derived H100-equivalents | **$0** to Modal | **$0** to Modal | **$7.31M at the 13 providers** |

The direct range is the cycle simulator's 1.3–1.8× Coffin-Manson scenario. At
the R=36 best case, Lambda rises to **$1.43M** and Together to **$1.21M**.
Capacity is **revenue capacity, not a
saving**: it needs capex, demand, and a power constraint. Modal's row is zero
because the fan bill lands on its 13 capacity providers, not on Modal.

Every number is produced by the code in `code/`. No number is a measurement of
fan power; the one load-bearing unknown is still a BMC reading.

---

## 1. Why these three

The first case proved the tweet's claim on a 24,000-H100 fleet with no founder
attached. The second case pointed it at Lambda. The third and fourth were the
obvious next names on the shortlist: Together AI, because it publishes a
36,000-GPU cluster and a price list, and Modal, because it is the most
developer-visible GPU platform of the cycle.

| criterion | Lambda | Together | Modal |
|---|---|---|---|
| air-cooled fleet | ATL02 forced-air; second air-cooled site in Chicago; 23 MW build hybrid | H100/H200 nodes can be air-cooled; 36k GB200 is liquid | none of its own |
| thousands of GPUs | 18,000-GPU Nvidia lease | "thousands" of H100/H200; 100k+ secured capacity | ~48k derived from ARR |
| owns/operates the node | operates the site; lease/ownership not fully public | operates; co-builds with partners | no |
| controls the BMC | **assumed**; not public | **assumed**; cluster operator | no |
| pays the fan power | **assumed**; not public | partly; partner-dependent | no |
| public price | $3.99/GPU-hr H100 | $3.99/GPU-hr H100 | $3.95/GPU-hr H100 |
| founder reachable | @stephenbalaban | @vipulved | @bernhardsson |
| where the meter sits | **the operator** | **operator or partner** | **the node providers** |

Lambda's BMC and power-payment cells are **assumptions**, not disclosures. The
is assumed, not disclosed. Together's are unknown. The code's `meter_payer()`
is a filter, not due diligence. The table is the model's answer under the stated
assumptions.

The filter is not "is this a good company". It is "can a fan controller be
installed, measured, and paid for by this target". That is why the verdicts
diverge.

---

## 2. The four questions

Every case answers the same four questions. The last two decide the verdict.

| target | site | node control | BMC | pays fan power | verdict |
|---|---|---|---|---|---|
| Lambda | lease (EdgeConneX) | yes | yes | yes | **the operator** |
| Together | partner + own | partial | yes | partial | **operator or partner** |
| Modal | none | no | no | no | **the node providers** |

A controller without a BMC is a software idea. A controller with a BMC but
without the power bill is a gift to the landlord. That is the whole difference
between the three rows.

---

## 3. The numbers side by side

Per 8-GPU node at 1 kW fan, 95 % → 35 % duty, $0.08/kWh, PUE 1.35:

```
energy   $898.77/node/yr
fatigue  $612.50/node/yr
total  $1,214.07/node/yr
```

| target | nodes | GPUs | energy | fatigue | direct | capacity |
|---|---:|---:|---:|---:|---:|---:|
| Lambda ATL02 12 MW | 1,176 | 9,408 | $0.71M | $0.72M | **$1.43M** | **$12.2M** |
| Lambda 18,000 lease | 2,250 | 18,000 | $2.02M | $1.38M | **$3.40M** | **$35.1M** |
| Together 8k, 100 % owned | 1,000 | 8,000 | $0.60M | $0.61M | **$1.21M** | **$10.4M** |
| Together 8k, 50 % owned | 1,000 | 8,000 | — | — | **$0.76M** | **$7.80M** |
| Modal underlying fleet | 6,022 | 48,176 modeled | $3.62M | $3.69M | **$7.31M** | **$62.3M** |

The table is the **R=36 fatigue scenario**. At the cycle simulator's 1.3–1.8×
Coffin-Manson, the direct ranges are **$1.23–1.39M** for Lambda ATL02,
**$0.75–0.88M** for Together 8k at 100 % owned, and **$4.50–5.31M** for the
Modal underlying fleet. The R=36 table values are the best-case upper bound,
not part of those 1.3–1.8× ranges.
The Modal row is the fan bill of the fleet behind its ARR. It is not Modal's
saving: 100 % of it accrues to the capacity providers under the current model.
Modal's direct row in the headline is therefore zero.

---

## 4. The verifiers

Each case has one number that can kill it. They are different numbers.

### Lambda: the air-cooled share

At 18,000 GPUs, the full claim survives at 1 kW unless the air-cooled share
falls below **29.4 %**. At 500 W the boundary is **41.9 %**; at 300 W it is
**50.4 %**. The energy-only claim is stricter: 49.5 % / 98.9 % / impossible.
The 2D table is in `LAMBDA-CASE.md` §7.

### Together: the ownership share

The public count is "thousands", not a number. The 36,000-GPU headline is
liquid and contributes zero. The case is therefore a two-dimensional table:
fleet size × ownership share.

| air-cooled GPUs | 100 % owned | 75 % | 50 % | 25 % | 0 % |
|---:|---:|---:|---:|---:|---:|
| 2,000 | $0.38M | $0.28M | $0.19M | $0.09M | $0 |
| 4,000 | $0.76M | $0.57M | $0.38M | $0.19M | $0 |
| 8,000 | **$1.21M** | **$0.60M** | $0.61M | $0.30M | $0 |
| 16,000 | **$2.43M** | **$1.20M** | **$1.21M** | $0.61M | $0 |

At **R=36**, the seven-figure boundary is **6,592 owned air-cooled GPUs**. At
8,000 GPUs Together needs to own **66.2 %** of the fleet's fan power; at 16,000
GPUs, **33.1 %**. At the cycle simulator's **1.3–1.8×**, the 8k requirement is
**~85–96 %** and the boundary is **~6,800–7,700 owned GPUs**. Below 4,000 GPUs
the direct claim cannot reach $1M at any ownership share.

The energy-only claim needs **8,904 GPUs** at 1 kW. At the 8,000-GPU base, the
energy leg alone is $601,779 — below $1M. The fatigue leg is what carries the
base case over the line. That is a credibility risk, and it is stated rather
than hidden.

### Modal: the ownership test

Modal owns no data centers and no nodes. Its capacity pool spans 20+ clouds and
13 named partners. The fan bill behind its $1B ARR is real — about
**$4.50–5.31M/yr** at 1.3–1.8× (**$7.31M** at R=36) on the derived fleet — but
it is **0.45–0.53 % of ARR** (**0.73 %** at R=36), and it belongs to the
providers. To capture $1M directly, Modal would need to own
**6,592–9,100 GPUs** depending on the fatigue ratio; it owns zero.

The lever Modal actually has is utilization. Packing the same fleet from 35 %
to 60 % yields **1.71×** billable GPU-hours, or about **$416.7M/yr gross** at
list price. That is a different business, not a like-for-like saving; the fan
claim is not just unattributable to Modal, it is immaterial next to the thing
Modal already sells.

---

## 5. What the package proves

1. **The tweet's claim is a scale claim with an ownership term.** At fleet scale
   the physics clears seven figures; at homelab scale it does not. The first
   case already showed the scale boundary. The three founder cases show the
   ownership boundary.
2. **Lambda is the clean case.** One operating air-cooled site, one public
   price, one founder. $1.43M/yr direct and $12.2M/yr of capacity at ATL02.
3. **Together splits the bill.** The physics works on the air-cooled
   H100/H200 fleet, but the dollars only route to Together on the share of the
   fleet whose power it pays for. The 36k headline is a liquid trap.
4. **Modal is the wrong target.** The fan bill is real but sits on 13 providers'
   P&L; Modal's own lever is utilization, a different business.
5. **The method is reusable.** The same three-leg arithmetic, the same fatigue
   cap, the same capacity formula, and the same qualification test run on all
   three.

---

## 6. What is not claimed

- **No fan wattage is measured.** 1 kW/node is an input in all three cases.
- **No PUE or tariff is measured.** $0.08/kWh and PUE 1.35 are parameters.
- **No fatigue parameter is measured.** `afr`, `share`, and `replacement` are
  assumptions, capped at $630/node/yr.
- **No liquid node is counted.** The 36k GB200 fleet and any DLC nodes are
  excluded.
- **No throughput credit or debit, no acoustics.** A controller that holds
  clocks is worth more than either leg; none of it is modelled. The laptop
  controller retains only **77–81 %** of stock work; on a revenue fleet that is
  a cost, not a saving.
- **Modal's ≈48,177 GPUs are derived from ARR**, not published. It is a scale
  estimate, not an upper bound: lower price or utilization raises it.
- **Together's 8,000 GPUs are a scenario**, not a measured air-cooled count.
- **The capacity column is not a saving.** It is gross revenue capacity that
  needs capex, demand, and a power constraint.

---

## 7. The ask, one per target

| target | the one thing that turns the model into a measurement |
|---|---|
| **Lambda** | one BMC fan-power reading (`FanPower`, `P12V_FAN`, or per-fan watts) from an ATL02 or Chicago air-cooled node |
| **Together** | who pays the meter on the H100/H200 fleet, and how many air-cooled nodes are in it |
| **Modal** | nothing for this claim; if useful, require fan telemetry from the 13 providers as a procurement term |

The first is a five-minute task. The second is a contract question. The third is
a different business.

---

## 8. Reproduce

```powershell
uv run python code/lambda_case.py --selftest    # 13 checks
uv run python code/together_case.py --selftest  # 16 checks
uv run python code/modal_case.py --selftest     # 17 checks
uv run python code/portfolio.py --selftest      # 10 checks
uv run python code/portfolio.py                 # the three verdicts
```

All 56 checks in the four case scripts pass. The full repo is 97, including the
original `case.py`, `cycling.py`, and `targets.py`. The source of truth is the
code, not this document.

---

## 9. Sources

- Lambda: `LAMBDA-CASE.md` §11; EdgeConneX/Lambda 2025-08-21; Lambda pricing;
  DCD 2025-09-08 (18,000-GPU Nvidia lease).
- Together: `TOGETHER-CASE.md` §11; Together/Hypertec 2024-11-18 (36k GB200,
  "thousands" of H100/H200, 100k+ secured capacity); Together pricing (H100
  $3.99, H200 $5.99); Series C 2026-07-01 (500 MW); ClusterMAX Gold 2025-03-27.
- Modal: `MODAL-CASE.md` §11; Modal Series D 2026-10-14 ($1B ARR, $750M,
  $15.75B); DCD 2026-10-16 (no data centers, 13 cloud partners); Modal pricing
  (H100 $0.001097/sec); Latent Space 2026-07-08 (CTO: "We don't have our own
  data centers").

---

The original claim was one sentence about fan power and thermal cycling. The
package now has three founder-led answers: one clear yes, one yes-with-a-contract,
and one no. The no is as useful as the yes. It tells you which founder not to
pitch, and why.
