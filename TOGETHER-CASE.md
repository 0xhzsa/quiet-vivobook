# Together AI: the fan bill behind "thousands" of H100s

> The headline is 36,000 GPUs. That cluster is liquid. The claim lives in the
> older air-cooled H100/H200 fleet — and only on the share of it whose power
> bill Together actually pays. That is the conditional.

This is the third case in the project. The first proved the claim on a
24,000-H100 fleet with no founder attached. The second pointed it at Lambda.
This one points it at **Together AI**, co-founder/CEO **@vipulved**, company
**@togethercompute**.

The physics is identical to the Lambda case. The new term is **ownership**. A
fan controller saves a dollar only for the party that pays the meter. Together
operates GPU clusters; it also co-builds them with Hypertec and other providers.
The public record does not say who owns the nodes or pays the power on the
H100/H200 fleet. That single unknown decides whether this is a **$1.5M/yr
saving for Together** or a **$1.5M/yr saving for Hypertec**.

---

## 0. The headline

Base scenario: **8,000 air-cooled H100/H200 GPUs**, 1,000 eight-GPU nodes,
1 kW fan per node, 95 % → 35 % duty, $0.08/kWh, PUE 1.35, H100 at
$3.99/GPU-hr, 60 % utilization. Every number is from `code/together_case.py`.

| air-cooled GPUs | nodes | energy | fatigue | **direct at 100 % owned** | **capacity at 100 %** |
|---:|---:|---:|---:|---:|---:|
| 2,000 | 250 | $0.22M | $0.15M | **$0.38M** | **$3.86M** |
| 4,000 | 500 | $0.45M | $0.31M | **$0.76M** | **$7.72M** |
| **8,000** | **1,000** | **$0.60M** | **$0.61M** | **$1.21M** | **$10.40M** |
| 16,000 | 2,000 | $1.80M | $1.23M | **$3.02M** | **$31.21M** |
| 36,000 (liquid) | 4,500 | $0 | $0 | **$0** | **$0** |

The cost columns are the **R=36 swing scenario**; §4 gives the 1.3–1.8× range.
The 8,000-GPU row is the base **scenario**, not a published count. Together
says "thousands of existing H100 and H200 GPUs across North America"; it does
not say how many, or how many are air-cooled. The 36,000-GPU row is the
headline cluster, and it is liquid: **zero fan watts, zero claim**.

The ownership table is the actual result:

| owned share | Together direct | Together capacity | partner direct |
|---:|---:|---:|---:|
| 100 % | **$1,214,072** | **$10,401,834** | $0 |
| 75 % | **$1,133,452** | **$11,702,064** | $377,817 |
| 50 % | $755,635 | $7,801,376 | $755,635 |
| 25 % | $377,817 | $3,900,688 | $1,133,452 |
| 0 % | $0 | $0 | $1,214,072 |

At 50 % ownership, the direct claim is **$0.76M** — below seven figures. At
**R=36**, the seven-figure boundary is **6,592 owned air-cooled GPUs**. At 8,000
GPUs, Together needs **66.2 %** of the fan power; at 16,000, **33.1 %**. At the
cycle simulator's **1.3–1.8× Coffin-Manson**, the 8k boundary rises to **~85–96 %** ownership
and **~6,800–7,700 owned GPUs**. Below 4,000 GPUs the direct claim cannot reach
$1M at any ownership share.

The capacity column is **revenue capacity, not a saving**. It needs capex for
the extra GPUs, demand to fill them, and a power constraint at the margin.

---

## 1. Why Together

The target filter is **air-cooled, bare metal, thousands of GPUs, reachable on
X, and you pay the fan power.** Together clears the fleet, bare-metal, and reach
tests; the H100/H200 generation can be air-cooled, though the split is not
public. The fifth test — who pays the meter — is the complication.

| criterion | Together |
|---|---|
| air-cooled | H100/H200 HGX nodes can be air-cooled; the air/liquid split is not public; the 36k GB200 NVL72 is liquid |
| bare metal | Together GPU Clusters, Slurm/Kubernetes, Instant Clusters |
| thousands of GPUs | "thousands of existing H100 and H200 GPUs across North America" (Nov 2024) |
| reachable | co-founder/CEO **@vipulved** + **@togethercompute** |
| public price | H100 **$3.99/GPU-hr**, H200 **$5.99/GPU-hr**, B200 **$8.19/GPU-hr** |
| power-constrained | 500 MW of compute commitments (Series C, Jul 2026) |
| owns the node / pays the meter | **not public** — the conditional |

The founder matters for the same reason as Lambda: a CTO can check a claim
against a BMC. But the question for Together is one step earlier than the BMC:
*whose* BMC?

### The ownership evidence

The public record points in both directions:

- Together describes "our fleet of GPU Clusters" and operates the SRE and
  support layer. That implies operational control, including BMC access.
- The 36,000-GPU cluster is **co-built with Hypertec Cloud**, which brings the
  data-center capacity. The 500 MW of commitments are "to be capitalized
  independently by our new investors". That implies the capacity is not all on
  Together's balance sheet.
- In March 2025, Together said it looked forward to "diversifying our fleet in
  the coming year with our own GPU clusters". That implies the fleet at the time
  was substantially partner-hosted.

So the honest verdict is **conditional**: Together can measure the fans, but it
may not be the party that pays for them. The model therefore reports both the
gross fleet saving and the attributable share.

### Why not the others

| candidate | why not |
|---|---|
| **Crusoe** | Abilene is closed-loop liquid; no GPU-tray fan energy. |
| **Modal** | No data centers, no nodes, 13 capacity providers. Covered in `MODAL-CASE.md`. |
| **Lambda** | Qualified; covered in `LAMBDA-CASE.md`. |
| **Voltage Park** | Air-cooled and public, but no founder persona; first case. |
| **CoreWeave / hyperscalers** | Too large to route a cold claim; a growing share is liquid. |

---

## 2. What is public — and what is not

### Public

| fact | value | source |
|---|---|---|
| 36k Blackwell cluster | 36,000 GB200 NVL72 GPUs, co-built with Hypertec, Q1 2025; **liquid-cooled** | Together blog, 2024-11-18 |
| Existing fleet | "thousands of existing H100 and H200 GPUs across North America" | same |
| Secured capacity | "over 100,000 GPUs throughout 2025" | same |
| Funding / capacity | $800M Series C; 500 MW of commitments capitalized independently | Together blog, 2026-07-01 |
| Cluster rating | ClusterMAX Gold (SemiAnalysis) | Together blog, 2025-03-27 |
| H100 price | **$3.99/GPU-hr** on-demand clusters; $1.99 preemptible | Together pricing, 2026 |
| H200 price | **$5.99/GPU-hr** on-demand clusters; $2.99 preemptible | same |
| B200 price | **$8.19/GPU-hr** on-demand clusters; $4.09 preemptible | same |
| Founder | Vipul Ved Prakash, co-founder/CEO, **@vipulved** | Together blog / X |

### Not public

These are the model's inputs, not measurements:

1. **The air-cooled H100/H200 count.** "Thousands" is the only public number.
2. **Who owns the nodes and pays the power.** Together, Hypertec, or a mix.
3. **Fan tray wattage** per node. The load-bearing unknown, same as Lambda.
4. **Site PUE** and **tariff / PPA price**.
5. **Utilization** and whether the fleet is power-constrained at the margin.
6. **The cooling split of the 500 MW commitments.** Not all of it is air.

Every one is a parameter in `together_case.py`. None is presented as a
measurement.

---

## 3. Leg 1 — fan energy: the leg that is physics

For a fixed impeller:

```
airflow  ∝ N
pressure ∝ N²
shaft power ∝ N³
```

From 95 % to 35 % duty:

```
P_ctrl / P_base = (0.35 / 0.95)³ = 0.050
```

95 % of the fan's shaft power disappears. At a 1 kW fan tray, that is **950 W
saved per node**.

```
950 W × 8,760 h / 1,000 = 8,322 kWh/yr
8,322 × $0.08 × 1.35     = $898.77/node/yr
```

| fan tray | saved W | $/node/yr @ $0.08/1.35 | $/node/yr @ $0.09/1.4 |
|---:|---:|---:|---:|
| 1,000 W | 635.9 | **$601.57** | **$701.83** |
| 500 W | 475.0 | $449.38 | $524.28 |
| 300 W | 285.0 | $269.63 | $314.57 |

### At Together's fleet sizes

| air-cooled GPUs | nodes | energy @ 1 kW | energy @ 500 W | energy @ 300 W |
|---:|---:|---:|---:|---:|
| 2,000 | 250 | $224,692 | $112,346 | $67,408 |
| 4,000 | 500 | $449,385 | $224,692 | $134,815 |
| 8,000 | 1,000 | $898,769 | $449,385 | $269,631 |
| 16,000 | 2,000 | $1,797,538 | $898,769 | $539,262 |

At 8,000 GPUs the energy leg alone is **$898,769** — below $1M. The energy-only
claim needs **8,904 GPUs** at 1 kW. That is the first honest boundary.

### The liquid exclusion

The 36,000 GB200 NVL72 GPUs are liquid-cooled. A cold-plate node has no fan
tray to slow down. Applying the model to 36,000 GPUs produces **$6,800,711/yr**
of direct saving and **$70,296,267/yr** of capacity — and both numbers are
false. `together_case.py` prints that trap explicitly so nobody can quote it by
accident.

---

## 4. Leg 2 — thermal fatigue: the leg that is conditional

The dollar leg uses the same **swing-ratio scenario** as the first case, not
the rainflow simulator in `cycling.py`. For an 8-GPU node:

```
failures avoided per node-year = afr · share · (1 − 1/R)
fatigue $/node/yr              = failures avoided · replacement
```

Base: `afr = 3 %/yr`, `share = 35 %`, `replacement = $60,000`, `R = 36`
(a 12 → 2 °C swing scenario, not a measured server result):

```
0.03 × 0.35 × (1 − 1/36) × $60,000 = $612.50/node/yr
```

The ceiling is `0.03 × 0.35 × $60,000 = $630/node/yr`. The model cannot exceed
it, no matter how good the controller is.

| air-cooled GPUs | nodes | fatigue @ $612.50/node |
|---:|---:|---:|
| 2,000 | 250 | $153,125 |
| 4,000 | 500 | $306,250 |
| 8,000 | 1,000 | $612,500 |
| 16,000 | 2,000 | $1,225,000 |

At the cycle simulator's **1.3–1.8×**, fatigue is **$145–$280/node**. The 8,000-GPU
base becomes **$1.04–$1.18M** at 100 % ownership; energy alone is **$0.90M**. So
the seven-figure boundary is **~8,400–9,300 owned GPUs**, not 6,592, and the
ownership needed at 8k is **~85–96 %**, not 66 %. The R=36 table is the best
case.

**This leg is an assumption, not a measurement.** `afr`, `share`, and
`replacement` are not in any public Together document, and this project has no
field-failure data. It is useful because it is bounded — at worst zero, at best
$630/node — but it is not the reason to believe the claim.

At 8,000 GPUs, the fatigue leg is what carries the base case over $1M. If you do
not believe it, use the **energy-only** boundary: 8,904 GPUs.

---

## 5. Leg 3 — capacity: the number that dwarfs the electricity bill

The fans are not just consuming electricity. They are consuming **power that
could be sold as GPUs**. At Together's own list price:

```
freed fan power = nodes × 950 W
extra nodes     = freed power / 10.2 kW
extra GPUs      = extra nodes × 8
revenue capacity = extra GPUs × $3.99/GPU-hr × 8,760 h × utilization
```

At 8,000 GPUs, 1 kW fan, 60 % utilization:

```
1,000 × 950 W            = 0.95 MW
0.95 MW / 10.2 kW        = 93 extra nodes
93 × 8                   = 744 extra GPUs
744 × $3.99 × 8,760 × 0.6 = $15,602,751/yr
```

| air-cooled GPUs | MW freed | extra nodes | extra GPUs | revenue capacity @ 60 % | gross profit @ 40 % |
|---:|---:|---:|---:|---:|---:|
| 2,000 | 0.2375 | 23 | 184 | **$3,858,745** | $1.54M |
| 4,000 | 0.475 | 46 | 368 | **$7,717,490** | $3.09M |
| 8,000 | 0.950 | 93 | 744 | **$15,602,751** | $6.24M |
| 16,000 | 1.900 | 186 | 1,488 | **$31,205,503** | $12.48M |

The extra-node count uses the full 10.2 kW for each new node, rather than its
lower controlled power. That undercounts the extra nodes; the capacity leg is
conservative. The 40 % margin is illustrative, not a Together disclosure.

The capacity leg is **gross revenue capacity**, not a saving:

- It needs **capex** for the additional GPUs — at an assumed ~$28k/GPU, that is
  ~$21M for the 8,000-GPU case, ~$42M for the 16,000-GPU case.
- It needs **demand** to fill the extra nodes.
- It needs the fleet to be **power-constrained at the margin**. With 500 MW of
  commitments, the constraint is plausible, but it is an assumption.

And, like every other leg, it is multiplied by the ownership share. A capacity
dollar on a partner-owned node is the partner's dollar.

---

## 6. The ownership term — the leg that decides the verdict

This is the Together-specific section, and the reason the verdict is
**conditional** rather than **qualified**.

`attributable()` in `together_case.py` splits all three legs by the share of
fan power Together pays for:

```python
def attributable(gpus, owned=1.0, **kwargs):
    r = legs(gpus, **kwargs)
    r["direct"] = r["saving"] * owned
    r["capacity"] = r["revenue"] * owned
    r["partner_direct"] = r["saving"] * (1.0 - owned)
    r["partner_capacity"] = r["revenue"] * (1.0 - owned)
    return r
```

At 8,000 GPUs:

| owned share | direct | capacity | who gets the rest |
|---:|---:|---:|---|
| 100 % | **$1,214,072** | **$10,401,834** | — |
| 75 % | **$1,133,452** | **$11,702,064** | partner: $377,817 |
| 50 % | $755,635 | $7,801,376 | partner: $755,635 |
| 25 % | $377,817 | $3,900,688 | partner: $1,133,452 |
| 0 % | $0 | $0 | partner: $1,214,072 |

At **R=36**, the seven-figure boundary is **6,592 owned air-cooled GPUs**; at
the simulator's 1.3–1.8×, it is **~6,800–7,700**. Put differently (R=36 table):

| air-cooled fleet | ownership needed for $1M direct | verdict at 50 % owned |
|---:|---:|---|
| 2,000 | 264.7 % | impossible |
| 4,000 | 132.3 % | impossible |
| 8,000 | **66.2 %** | $0.76M — below seven figures |
| 16,000 | **41.2 %** | **$1.21M** — clears |
| 36,000 (liquid) | n/a | $0 — no fans |

This is the honest shape of the Together claim:

- If Together owns the whole 8,000-GPU air-cooled fleet, the direct claim is
  **$1.21M/yr at R=36** (**$0.75–0.88M** at the simulator's 1.3–1.8×), and the
  capacity is **$15.6M/yr**.
- If it owns half, the direct claim is **$0.76M** — not seven figures.
- If the air-cooled fleet is 4,000 GPUs, the direct claim cannot reach $1M even
  at 100 % ownership.
- If someone counts the 36,000 liquid GPUs, the claim is **$0** on the fan leg.

That is why the ask to Together is not "measure your fans". It is "tell us who
pays the meter".

---

## 7. The composed case

Cost saving = energy + fatigue, multiplied by ownership. Capacity is reported
separately.

| air-cooled GPUs | direct @ 100 % | direct @ 75 % | direct @ 50 % | capacity @ 100 % |
|---:|---:|---:|---:|---:|
| 2,000 | $377,817 | $283,363 | $188,909 | $3,858,745 |
| 4,000 | $755,635 | $566,726 | $377,817 | $7,717,490 |
| **8,000** | **$1,214,072** | **$601,572** | $607,036 | **$10,401,834** |
| 16,000 | **$2,428,145** | **$1,203,145** | **$1,214,072** | **$20,803,669** |

At the first case's $0.09/kWh and PUE 1.4, the energy column rises by 16.7 %.
At 8,000 GPUs, direct at 100 % becomes **$1,214,072** (energy $601,572 +
fatigue $612,500).

### The knobs, at 8,000 GPUs and 100 % ownership

| knob | low | base | high | effect on direct |
|---|---|---|---|---|
| fan wattage | 300 W | 1,000 W | 1,500 W | **$0.88M – $1.96M** |
| tariff × PUE | $0.06 × 1.2 | $0.08 × 1.35 | $0.12 × 1.5 | **$1.21M – $2.11M** |
| fatigue parameters | −50 % | base | +50 % | **$1.21M – $1.82M** |
| ownership | 50 % | 100 % | 100 % | **$0.61M – $1.21M** |
| utilization (capacity) | 40 % | 60 % | 80 % | $10.4M – $20.8M |

The ranking is the same as the first two cases: **fan wattage dominates**.
Ownership is the new second-order term, and it is the one that decides whether
the claim routes to Together at all.

### The 2D verification table

Direct saving at 100 % ownership, by fleet size and fan wattage:

| air-cooled GPUs | 1 kW | 500 W | 300 W |
|---:|---:|---:|---:|
| 2,000 | $0.38M | $0.27M | $0.22M |
| 4,000 | $0.76M | $0.53M | $0.44M |
| 8,000 | **$1.21M** | **$0.60M** | $0.61M |
| 16,000 | **$3.02M** | **$2.12M** | **$1.76M** |

At 50 % ownership, cut every number in half: the 8,000-GPU / 1 kW cell becomes
$0.76M, and only the 16,000-GPU row clears $1M.

The red zone is the top-left and the right-hand columns: a small air-cooled
fleet, low fan wattage, or low ownership. If Together answers "the H100 fleet is
4,000 GPUs, mostly partner-owned, and the trays draw 300 W", the claim is false.
If it answers "we own 16,000 air-cooled H100/H200 nodes and pay the power", the
claim is **$3.0M/yr** before capacity.

---

## 8. What is not claimed

- **The 36,000-GPU cluster is not air-cooled.** It is GB200 NVL72, liquid. It
  contributes zero to every column.
- **The air-cooled count is not published.** 8,000 is a scenario; the public
  word is "thousands".
- **The fan tray is not measured.** 1 kW is an input.
- **The fatigue dollars are not measured.** `afr`, `share`, and `replacement`
  are assumptions, bounded by the $630/node ceiling.
- **The ownership share is not public.** 100 % is the gross case, not the
  attributed case.
- **The capacity leg is not a saving.** It is gross revenue capacity that
  requires capex, demand, and a power constraint.
- **No liquid nodes.** A cold-plate node has no fan tray to slow down.
- **No throughput credit.** A controller that holds clocks under load is worth
  more than either leg here, and none of it is in this model.
- **No acoustic claim.** Fan RPM is not public for Together's nodes.

---

## 9. What we need from Together

One of these turns the model into a measurement:

1. **The air-cooled H100/H200 node count.** The public word is "thousands".
2. **Who owns the nodes and pays the power** — Together, Hypertec, or a mix.
   This is the conditional.
3. **One BMC reading** from an air-cooled H100/H200 node: `FanPower`,
   `P12V_FAN`, or per-fan watts.
4. **Site PUE** and **tariff / PPA price**.
5. **Utilization and power-constraint status** — only for the capacity leg.
6. **The cooling split of the 500 MW commitments** — how much is air, how much
   is liquid.

The first two decide the verdict. The third decides the headline.

---

## 10. Reproduce it

```powershell
uv run python code/together_case.py --selftest   # 16 checks on the algebra
uv run python code/together_case.py              # three legs, ownership, boundaries
uv run python code/together_case.py --gpus 16000 --owned 0.75
```

Every dollar figure is derived from a printed input. `--selftest` checks the
per-node energy, the fatigue cap, the 8,000-GPU arithmetic, the $1M boundaries,
the 50 % attribution, and the 36,000-GPU liquid trap against hand-computed
values.

---

## 11. Sources

- Together AI, **2024-11-18**: 36,000 GB200 NVL72 GPUs with Hypertec Cloud,
  starting Q1 2025; "immediate access to thousands of H100 and H200 GPUs across
  North America"; "secured data center capacity for over 100,000 GPUs throughout
  2025"; GB200 NVL72 described as liquid-cooled.
  <https://www.together.ai/blog/nvidia-gb200-together-gpu-cluster-36k>
- Together AI, **2026-07-01**: $800M Series C; 500 MW of compute capacity
  commitments to be capitalized independently by investors.
  <https://www.together.ai/blog/announcing-our-series-c>
- Together AI, **2025-03-27**: ClusterMAX Gold; "diversifying our fleet in the
  coming year with our own GPU clusters".
  <https://www.together.ai/blog/clustermax-gold>
- Together AI pricing, 2026: H100 $3.99/GPU-hr, H200 $5.99, B200 $8.19 on-demand
  clusters; preemptible H100 $1.99.
  <https://www.together.ai/pricing>
- Vipul Ved Prakash, co-founder/CEO, @vipulved.
  <https://x.com/vipulved>
- NVIDIA DGX H100: ~10.2 kW per 8-GPU system.
  <https://docs.nvidia.com/dgx/dgxh100-user-guide/introduction-to-dgxh100.html>
- EIA industrial electricity price, ~9 ¢/kWh national average (2026); site
  tariffs vary. <https://www.eia.gov/electricity/monthly/>

---

The method is the same as the first two cases: decompose the claim into
independent legs, implement each with the correct physics instead of a proxy,
calibrate to public data, test the arithmetic, then find the conditions under
which the claim is false. For Together, the decisive condition is not fan
wattage. It is the contract.
