# Lambda: the fan bill inside the 18,000-GPU lease

> 18,000 GPUs. Two air-cooled sites. One public price list. The fan trays are
> the one number Lambda has not published — and the number that decides whether
> this is a **$1.2–1.8M cost story** or an **$18M capacity story**.

This is the second case in the project. The first proved the "7 figure savings"
claim on a 24,000-H100 fleet with no founder attached. This one is aimed at a
**founder-led** operator: Lambda, co-founder/CTO **@stephenbalaban**, company
**@LambdaAPI**.

The difference is not the arithmetic. It is the address. Lambda operates the
air-cooled sites, has a public lease anchor and price list, and is building
through a power constraint. The model **assumes Lambda pays the meter**; the
public record does not state the power contract. That assumption is the first
thing to confirm, not a fact to quote.

---

## 0. The headline

Base case: **$0.08/kWh, PUE 1.35, 1 kW fan per 8-GPU node, 95 % → 35 % duty,
H100 at $3.99/GPU-hr, 60 % utilization.** Every number below is from
`code/lambda_case.py`; every input is printed by the model.

| scope | nodes | GPUs | fan energy | thermal fatigue | **cost saving** | **capacity value** |
|---|---:|---:|---:|---:|---:|---:|
| **ATL02 operating (12 MW)** | 1,176 | 9,408 | $1.06M | $0.72M | **$1.78M/yr** | **$18.3M/yr** |
| ATL02 design (14 MW) | 1,372 | 10,976 | $1.23M | $0.84M | **$2.07M/yr** | **$21.3M/yr** |
| 18,000-GPU lease, if air-cooled | 2,250 | 18,000 | $2.02M | $1.38M | **$3.40M/yr** | **$35.1M/yr** |
| 30 MW EdgeConneX footprint, ceiling | 2,941 | 23,528 | $2.64M | $1.80M | **$4.44M/yr** | **$45.8M/yr** |

The cost column is the **R=36 swing scenario**; §4 gives the 1.3–1.8× range.
Read the **first row as the claim** and the **last row as the ceiling**.

The first row is the most concrete, not the conservative one: ATL02 is a real
forced-air site with a public **12 MW design capacity**. The 1,176-node figure
is a **theoretical maximum at 10.2 kW/node**, not a measured all-H100 fleet; the
actual mix and load may be lower. The 18,000-GPU lease is the public fleet
anchor, but not all of it is guaranteed to be air-cooled. The 30 MW figure is
the whole EdgeConneX footprint, including the new Chicago hybrid build — an
upper bound, not a measured air-cooled count.

The capacity column is **revenue capacity, not a saving**. It is the GPU
revenue the freed watts could support at Lambda's own list price. It needs
capex for the GPUs and demand to fill them. It is reported separately for that
reason — and it is the number that makes the fan tray worth a founder's time.

---

## 1. Why Lambda

The target filter is **air-cooled, bare metal, thousands of GPUs, reachable on
X, and you pay the fan power.** Lambda clears all five, and adds a founder.

| criterion | Lambda |
|---|---|
| air-cooled | ATL02 is forced-air (EdgeConneX: "30 inch raised/under floor forced air plenum"); a second air-cooled site in Chicago |
| bare metal | Lambda sells instances and 1-Click Clusters on its own nodes |
| thousands of GPUs | 18,000 GPUs leased to Nvidia, $1.5B over four years |
| reachable | co-founder/CTO **@stephenbalaban** (16.7K followers) + **@LambdaAPI** |
| public price | H100 SXM **$3.99/GPU-hr**; B200 **$6.69/GPU-hr** |
| power-constrained | 320 MW committed, 3 GW target by 2030; 2 GW+ vision, 1M GPUs by 2030 |

The founder matters for a specific reason. A cold technical claim sent to a
marketing inbox dies. A claim that says *"at 18,000 GPUs your own fans are eating
2.1 MW, and at your own price that is $35M/yr of capacity"* is a claim a CTO can
check against a BMC in five minutes.

### Why not the others

| candidate | why not |
|---|---|
| **Crusoe** | Abilene is closed-loop **liquid**; the GPU trays have no fan energy to save. Best narrative, wrong physics. |
| **Modal** | No data centers, no nodes; the fan bill belongs to 13 capacity providers. Covered in `MODAL-CASE.md`. |
| **Together** | The headline 36,000-GPU fleet is GB200 NVL72, liquid. The air-cooled H100 share is not public. |
| **Voltage Park** | Air-cooled and public, but no founder persona. Already covered by the first case. |
| **CoreWeave / hyperscalers** | Too large to route a cold claim; a growing share is liquid. |

Lambda is the only candidate where the **fan owner**, the **founder**, and the
**public number** are the same target.

---

## 2. What is public — and what is not

### Public

| fact | value | source |
|---|---|---|
| Nvidia lease | ~18,000 GPUs, $1.5B over 4 years; $1.3B for 10,000 high-end, $200M for 8,000 older | The Information / DCD, Sep 2025 |
| ATL02 | 91,980 sq ft; planned up to **14 MW**; 20+ kW/cabinet; forced-air plenum; 12 MW operating per Cleanview | EdgeConneX Atlanta page; Cleanview |
| Chicago/Atlanta build | **30+ MW**; Chicago single-tenant **23 MW**, RFS 2026; two air-cooled sites (ATL02 + Chicago); hybrid liquid + air; 600+ kW/rack | EdgeConneX/Lambda, Aug 21 2025 |
| Lambda cooling | direct-to-chip liquid **and** precision air; DTC improves PUE by >15 % | Lambda AI infrastructure page |
| Lambda footprint | 75 MW+ contiguous; 5–75 MW distributed; Kansas City 100 MW / >10,000 GPUs | Lambda AI infrastructure page |
| Lambda capacity | 320 MW committed; 3 GW target by 2030 | public interviews / DCD |
| H100 price | **$3.99/GPU-hr** (8x on-demand); $4.09–4.29 for smaller instances | Lambda pricing |
| B200 price | **$6.69/GPU-hr** (8x on-demand) | Lambda pricing |
| 1-Click H100 | $5.54–6.16/GPU-hr (16–256 GPUs, 2 weeks–1 year) | Lambda pricing |
| founder | Stephen Balaban, co-founder/CTO, **@stephenbalaban**, 16.7K followers | X profile |

### Not public

These are the model's inputs, not measurements:

1. **Fan tray wattage** per node. The load-bearing unknown.
2. **Air-cooled share** of the 18,000-GPU lease. The lease may include liquid
   nodes; the public air-cooled site is ATL02 (12 MW operating; 14 MW planned).
3. **Site PUE.** Lambda says DTC improves PUE by >15 %, but does not publish an
   air-cooled site PUE.
4. **Tariff / PPA price.** Georgia and Illinois industrial rates vary; the model
   uses $0.08/kWh base, $0.06–0.12 range.
5. **Utilization** and whether the site is **power-constrained at the margin**.
   The capacity leg depends on both.

Every one of these is a parameter in `lambda_case.py`. None is presented as a
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

At the first case's $0.09/kWh and PUE 1.4: **$1,048.56/node/yr**.

| fan tray | saved W | $/node/yr @ $0.08/1.35 | $/node/yr @ $0.09/1.4 |
|---:|---:|---:|---:|
| 1,000 W | 950.0 | **$898.77** | **$1,048.56** |
| 500 W | 475.0 | $449.38 | $524.28 |
| 300 W | 285.0 | $269.63 | $314.57 |

### At Lambda's scale

| scope | nodes | energy @ 1 kW | energy @ 500 W | energy @ 300 W |
|---|---:|---:|---:|---:|
| ATL02 12 MW | 1,176 | $1,056,952 | $528,476 | $317,086 |
| ATL02 14 MW | 1,372 | $1,233,111 | $616,556 | $369,933 |
| 18,000-GPU lease | 2,250 | $2,022,230 | $1,011,115 | $606,669 |
| 30 MW footprint | 2,941 | $2,643,280 | $1,321,640 | $792,984 |

The 18,000-GPU lease at 10.2 kW/node is **22.95 MW** of IT load — inside the
30 MW EdgeConneX footprint, but larger than ATL02 alone. That is exactly why
the air-cooled share is the first thing to ask.

The 12/14/30 MW figures are treated as **IT capacity**. If a site's quoted MW
includes cooling overhead, the node count and every dollar scale down
proportionally; the per-node arithmetic is unchanged.

### The mixed-fleet caveat

The lease is **10,000 high-end + 8,000 older GPUs**. The model applies the H100
node's 1 kW fan to all 18,000. If the older half has smaller fan trays — say
600 W instead of 1 kW — the energy leg falls from $2.02M to **$1.66M**, and the
total from $3.40M to **$3.04M**. Still seven figures. The BMC reading on one
older node resolves it.

---

## 4. Leg 2 — thermal fatigue: the leg that is conditional

The dollar leg uses the same **swing-ratio scenario** as the first case, not
the rainflow simulator in `cycling.py`. For an 8-GPU node:

```
failures avoided per node-year = afr · share · (1 − 1/R)
fatigue $/node/yr              = failures avoided · replacement
```

Base: `afr = 3 %/yr`, `share = 35 %`, `replacement = $60,000`, `R = 36`
(the 12 °C → 2 °C swing scenario; `cycling.py` on the laptop plant gives
1.3–1.8× Coffin-Manson, not 36×):

```
0.03 × 0.35 × (1 − 1/36) × $60,000 = $612.50/node/yr
```

The ceiling is `0.03 × 0.35 × $60,000 = $630/node/yr`. The model cannot exceed
it, no matter how good the controller is.

| scope | nodes | fatigue @ $612.50/node |
|---|---:|---:|
| ATL02 12 MW | 1,176 | $720,300 |
| ATL02 14 MW | 1,372 | $840,350 |
| 18,000-GPU lease | 2,250 | $1,378,125 |
| 30 MW footprint | 2,941 | $1,801,362 |

At the cycle simulator's **1.3–1.8×**, fatigue is **$145–$280/node**, so ATL02
is **$1.23–$1.39M/yr** total; the seven-figure verdict survives on energy plus a
small fatigue credit, not on R=36. At the measured 87.5 % fan curve the energy
alone is **$0.97M**, so the verdict then needs the fatigue leg. That is the
honest boundary.

**This leg is an assumption, not a measurement.** `afr`, `share`, and
`replacement` are not in any public Lambda document, and this project has no
field-failure data. It is useful because it is **bounded** — at worst it is
zero, at best it is $630/node — but it is not the reason to believe the claim.

The 8,000 older GPUs may also have a lower replacement cost than $60,000; the
fatigue leg is an upper bound for that half.

At low fan wattage the fatigue leg carries the total. That is a credibility
risk, and it is stated here rather than hidden: if you do not believe the
fatigue parameters, use the **energy-only** column in §7.

---

## 5. Leg 3 — capacity: the number that dwarfs the electricity bill

This is the part that makes the case worth sending to a founder.

The fans are not just consuming electricity. They are consuming **power that
could be sold as GPUs**. At Lambda's own list price:

```
freed fan power = nodes × 950 W
extra nodes     = freed power / 10.2 kW
extra GPUs      = extra nodes × 8
revenue capacity = extra GPUs × $3.99/GPU-hr × 8,760 h × utilization
```

At 18,000 GPUs, 1 kW fan, 60 % utilization:

```
2,250 × 950 W            = 2.1375 MW
2.1375 MW / 10.2 kW      = 209 extra nodes
209 × 8                  = 1,672 extra GPUs
1,672 × $3.99 × 8,760 × 0.6 = $35,064,248/yr
```

| scope | MW freed | extra nodes | extra GPUs | revenue capacity @ 60 % | gross profit @ 40 % |
|---|---:|---:|---:|---:|---:|
| ATL02 12 MW | 1.117 | 109 | 872 | **$18,287,096** | $7.31M |
| ATL02 14 MW | 1.303 | 127 | 1,016 | **$21,306,983** | $8.52M |
| 18,000-GPU lease | 2.138 | 209 | 1,672 | **$35,064,248** | $14.03M |
| 30 MW footprint | 2.794 | 273 | 2,184 | **$45,801,625** | $18.32M |

The extra-node count uses the full 10.2 kW for each new node, rather than its
lower controlled power. That undercounts the extra nodes; the capacity leg is
conservative. The 40 % margin is illustrative, not a Lambda disclosure.

The capacity leg is **gross revenue capacity**, not a saving:

- It needs **capex** for the additional GPUs — at an assumed ~$28k/GPU, that is
  ~$24M for the ATL02 12 MW case, ~$47M for the 18,000-GPU case.
- It needs **demand** to fill the extra nodes. Lambda's buildout suggests demand
  exists, but this project cannot prove it.
- It needs the site to be **power-constrained at the margin**. If Lambda can
  simply buy more power, the freed watts are worth the tariff, not the GPU
  revenue. At 320 MW committed and a 3 GW target, the constraint is the
  reasonable assumption — but it is an assumption.

Why it matters anyway: the direct saving is **$1.23–1.39M/yr** at 1.3–1.8×
(**$1.78M** at R=36) for ATL02 ($1.06M energy alone at 1 kW), and the capacity is **$18.3M/yr** of revenue at
the same site. The fan tray is a **10–15× lever on the thing Lambda actually
sells**. That is the sentence for the founder, not the electricity bill.

At B200's $6.69/GPU-hr, the same freed capacity is worth 68 % more; the case
uses H100 pricing to stay conservative.

---

## 6. The composed case

Cost saving = energy + fatigue. Capacity is reported separately.

| scope | energy | fatigue | **cost saving** | capacity (not a saving) |
|---|---:|---:|---:|---:|
| **ATL02 12 MW** | $1,056,952 | $720,300 | **$1,777,252** | $18,287,096 |
| ATL02 14 MW | $1,233,111 | $840,350 | **$2,073,461** | $21,306,983 |
| 18,000-GPU lease | $2,022,230 | $1,378,125 | **$3,400,355** | $35,064,248 |
| 30 MW footprint | $2,643,280 | $1,801,362 | **$4,444,642** | $45,801,625 |

The 7-figure claim is true at the **operating** air-cooled site, not just at
the lease or the ceiling. That is the difference between this case and a
spreadsheet about a hypothetical fleet.

### The same numbers at the first case's tariff

At $0.09/kWh and PUE 1.4, the energy column rises by 16.7 %:

| scope | energy @ $0.09/1.4 | total saving |
|---|---:|---:|
| ATL02 12 MW | $1,233,111 | $1.95M |
| ATL02 14 MW | $1,438,630 | $2.28M |
| 18,000-GPU lease | $2,359,269 | $3.74M |
| 30 MW footprint | $3,083,827 | $4.89M |

The model's exact 12 MW energy is **$1,233,111** (1,176 nodes); the total is
**$1,953,411**.

---

## 7. Sensitivity and the two boundaries

### The knobs, at ATL02 12 MW

| knob | low | base | high | effect |
|---|---|---|---:|---|
| fan wattage | 300 W | 1,000 W | 1,500 W | **$1.04M – $2.31M** |
| tariff | $0.04 | $0.08 | $0.12 | ±$0.53M |
| PUE | 0.9 | 1.35 | 1.8 | ±$0.35M |
| fatigue parameters | −50 % | base | +50 % | ±$0.36M |
| duty after | 50 % | 35 % | 20 % | −$0.11M / +$0.05M |
| life ratio R | 9 | 36 | 100 | −$0.06M / +$0.01M |
| utilization (capacity) | 40 % | 60 % | 80 % | $12.2M – $24.4M |

The last row is the **capacity value**, not the cost saving; it is shown at
40–80 % utilization.

The air-cooled share is not a knob at ATL02 — the site is air-cooled. It is the
main knob for the 18,000-GPU lease; the 2D table below prices it directly.

The ranking is the same as the first case, but sharper: **fan wattage
dominates.** Tariff and PUE are material but second-order; duty after and the
fatigue shape are rounding errors next to them.

### Boundary 1 — the total claim (energy + fatigue), at R=36

At 18,000 GPUs, the R=36 best case is seven figures if the air-cooled share
clears:

| fan per node | $/node/yr (total) | nodes for $1M | GPUs for $1M | share of 18k |
|---:|---:|---:|---:|---:|
| 1,000 W | $1,511.27 | 662 | 5,296 | **29.4 %** |
| 500 W | $1,061.88 | 942 | 7,536 | **41.9 %** |
| 300 W | $882.13 | 1,134 | 9,072 | **50.4 %** |

At the cycle simulator's **1.3–1.8×**, the 1 kW boundary rises to
**6,792–7,664 GPUs**, or **37.7–42.6 %** of 18k. At 300 W it rises to
**14,560–19,280 GPUs**, or **80.9–107.1 %** — i.e. the 300 W full claim is not robust.
So the **full claim** survives at 18,000 GPUs at 1 kW above roughly **38–43 %**
air-cooled, not 30 %. The table is the best case.

### Boundary 2 — the energy-only claim

If you do not believe the fatigue leg, the physics-only claim is stricter:

| fan per node | $/node/yr (energy) | nodes for $1M | GPUs for $1M | share of 18k |
|---:|---:|---:|---:|---:|
| 1,000 W | $898.77 | 1,113 | 8,904 | **49.5 %** |
| 500 W | $449.38 | 2,226 | 17,808 | **98.9 %** |
| 300 W | $269.63 | 3,709 | 29,672 | **164.8 %** |

The energy-only claim is **impossible at 300 W** at 18,000 GPUs. It is barely
possible at 500 W if essentially the entire lease is air-cooled. It is
comfortable at 1 kW with half the lease.

This is the honest shape of the claim:

- **At 1 kW fan, half the lease air-cooled:** the physics alone clears $1M.
- **At 500 W, all the lease air-cooled:** the energy-only physics barely clears
  $1M; the full claim is $2.39M, with fatigue making up the difference.
- **At 300 W, all the lease air-cooled:** the energy-only physics does not clear
  $1M; the full claim is $1.98M and depends on the fatigue leg.

### The 2D falsification table

Total saving at 18,000 GPUs, by air-cooled share and fan wattage:

| air-cooled share | nodes | 1 kW | 500 W | 300 W |
|---|---:|---:|---:|---:|
| 100 % | 2,250 | **$3.40M** | **$2.39M** | **$1.98M** |
| 75 % | 1,687 | **$2.55M** | **$1.79M** | **$1.49M** |
| 50 % | 1,125 | **$1.70M** | **$1.19M** | $0.99M |
| 25 % | 562 | $0.85M | $0.60M | $0.50M |

The red zone is the bottom row and the right-hand columns: low air-cooled share
and low fan wattage. If Lambda answers "the 18,000 lease is mostly liquid, and
the air-cooled fans draw 300 W", the claim is false. If it answers "the H100
sites are air-cooled and the tray is ~1 kW", the claim is **$3.4M/yr** before
capacity.

That is why the ask is one reading, not a debate.

---

## 8. What is not claimed

- **Not all 18,000 GPUs are air-cooled.** The public air-cooled site is ATL02
  (12 MW operating; 14 MW planned); the lease may include liquid nodes. The
  18,000-GPU row is a scenario, not a measurement.
- **The fan tray is not measured.** 1 kW is an input. The BMC reading is the
  point of the exercise.
- **The fatigue dollars are not measured.** `afr`, `share`, and `replacement`
  are assumptions, bounded by the $630/node ceiling.
- **The capacity leg is not a saving.** It is gross revenue capacity that
  requires capex, demand, and a power constraint.
- **No liquid-cooled nodes.** A cold-plate node has no fan tray to slow down.
- **No throughput credit.** A controller that holds clocks under load is worth
  more than either leg here, and none of it is in this model.
- **No acoustic claim.** Fan RPM is not public for Lambda's nodes; every dB
  number would be invented.

---

## 9. What we need from Lambda

One of these turns the model into a measurement:

1. **One BMC reading** from an ATL02 or Chicago air-cooled node:
   `FanPower`, `P12V_FAN`, or per-fan watts.
2. **A 30-day trace** of fan duty and node power.
3. **Site PUE** (measured, not design).
4. **The tariff or PPA price** for the site.
5. **The air-cooled share** of the 18,000-GPU lease.
6. **Utilization and power-constraint status** — only needed for the capacity
   leg.

The first one is a five-minute task and decides the headline.

---

## 10. Reproduce it

```powershell
uv run python code/lambda_case.py --selftest   # 13 checks on the algebra
uv run python code/lambda_case.py              # three legs, sites, sensitivity
uv run python code/lambda_case.py --fan-w 500 --tariff 0.12 --pue 1.5
```

Every dollar figure is derived from a printed input. `--selftest` checks the
per-node energy, the fatigue cap, the 18,000-GPU arithmetic, and the 12/14/30 MW
node counts against hand-computed values.

---

## 11. Sources

- EdgeConneX/Lambda press release, **2025-08-21**: 30+ MW Chicago/Atlanta;
  23 MW Chicago single-tenant; two air-cooled sites (ATL02, Chicago); hybrid
  cooling; 600+ kW/rack; 2 GW+ vision; 1M GPUs by 2030.
  <https://lambda.ai/blog/lambda-edgeconnex-dc-pr>
- EdgeConneX Atlanta page: ATL02 91,980 sq ft; planned up to 14 MW; 20+ kW per
  cabinet; 30-inch raised/under-floor forced-air plenum.
  <https://www.edgeconnex.com/locations/americas/atlanta-ga/>
- Cleanview ATL02: 12 MW operating; 91,980 sq ft.
  <https://cleanview.co/data-centers/georgia/1177/edgeconnex-atl02>
- Lambda capacity targets: 320 MW committed, 3 GW by 2030 (public interviews
  and DCD reporting, 2026).
- DataCenterDynamics, **2025-09-08**: Nvidia $1.5B lease, ~18,000 GPUs over four
  years; $1.3B for 10,000 high-end, $200M for 8,000 older.
  <https://www.datacenterdynamics.com/en/news/nvidia-signs-15bn-deal-to-lease-its-gpus-back-from-lambda-report/>
- Lambda AI infrastructure: direct-to-chip liquid + precision air; DTC improves
  PUE by >15 %; 75 MW+ contiguous; 5–75 MW distributed; Kansas City 100 MW /
  >10,000 GPUs. <https://lambda.ai/ai-infrastructure>
- Lambda pricing: H100 SXM $3.99/GPU-hr (8x on-demand); B200 SXM6 $6.69/GPU-hr;
  1-Click H100 $5.54–6.16/GPU-hr. <https://lambda.ai/pricing>
- Stephen Balaban, co-founder/CTO, @stephenbalaban, 16.7K followers.
  <https://x.com/stephenbalaban>
- EIA industrial electricity price, ~9 ¢/kWh national average (2026); site
  tariffs vary. <https://www.eia.gov/electricity/monthly/>
- NVIDIA DGX H100: ~10.2 kW per 8-GPU system (used as the node power).
  <https://docs.nvidia.com/dgx/dgxh100-user-guide/introduction-to-dgxh100.html>

---

The method is the same as the first case: decompose the claim into independent
legs, implement each with the correct physics instead of a proxy, calibrate to
public data, test the arithmetic, then find the conditions under which the
claim is false. §7 is the deliverable.
