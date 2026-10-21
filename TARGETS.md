# Who this is for

The claim is a **scale** claim and an **ownership** claim. Both terms are
arithmetic, not vibes.

## The filter

A target qualifies only if all five are true:

1. **Air-cooled.** A cold-plate node has no fan tray to slow down. GB200 NVL72
   and most new liquid-cooled builds are out — not as a caveat, as a
   disqualification.
2. **Node control.** The claim is about node-level control, not a managed
   abstraction. You need the BMC, or someone who will give you the reading.
3. **Thousands of GPUs.** Fan power alone reaches $1M/yr at ~1,425 eight-GPU
   nodes. Below ~500 nodes the claim is arithmetically impossible, no matter
   how good the controller is.
4. **Reachable and identifiable on X.** A public fleet count makes the number
   checkable; an active account makes the ask land.
5. **You pay the fan power.** A controller saves a dollar only for the party
   that pays the meter. A platform on top of someone else's nodes can measure
   the fan but cannot capture the saving. This is the term that separates the
   three founder cases.

The first four get you a **measurement**. The fifth gets you a **saving**.

## The shortlist

Fan-only figures use $0.09/kWh, PUE 1.4, 1 kW fan tray, 95 % → 35 % duty.

| target | handle | public fleet | air-cooled anchor | verdict | case |
|---|---|---|---|---|---|
| **Voltage Park** | **@VoltagePark** | 24,000 H100 SXM5 (2024); 12,000 enterprise GPUs cited in 2026 | six Tier 3+ sites; HGX air-cooled | **first case** | `CASE-STUDY.md` |
| **Lambda** | **@stephenbalaban + @LambdaAPI** | 18,000 GPUs leased to Nvidia + own fleet | ATL02 forced-air, 12–14 MW; Chicago air-cooled | **qualified** | `LAMBDA-CASE.md` |
| **Together** | **@vipulved + @togethercompute** | "thousands" of H100/H200; 36,000 Blackwell NVL72 (liquid) | H100/H200 can be air-cooled; 36k is liquid | **conditional** | `TOGETHER-CASE.md` |
| **Modal** | **@bernhardsson + @modal_labs** | ~48,177 derived from $1B ARR | none; 13 capacity providers | **disqualified** | `MODAL-CASE.md` |
| Crusoe | @CrusoeAI | "thousands of nodes" | Abilene closed-loop liquid | **disqualified** | — |

Even the conservative Voltage Park count — 12,000 GPUs, 1,500 nodes — is
**$1.57M/yr from fan power alone**, before any fatigue credit.

**But that number is a function of fan wattage**, which is the whole reason for
the ask. At 1,500 nodes:

| fan per node | $/node/yr | 1,500 nodes |
|---|---|---|
| 1,000 W | $701.83 | **$1.05M** |
| 500 W | $524.28 | **$786k** |
| 300 W | $314.57 | **$472k** |

At 500 W the claim is not 7 figures at 12,000 GPUs — it needs ~15,300. Restoring
the 1 kW total takes 24,000. This is not a weakness in the argument; it is the
argument. One BMC reading decides it.

The current founder-facing shortlist is **Lambda (qualified)**, **Together
(conditional)**, and **Modal (disqualified)**. Voltage Park remains the clean
public-count example, not the only target.

## The original case: Voltage Park (@VoltagePark)

Why this one:

- **The count is public and exact.** 24,000 H100 SXM5 GPUs across six Tier 3+
  data centers, announced with a price and a date. The arithmetic can be checked
  by anyone, which is the point.
- **Air-cooled HGX.** The fan tray is a real line item, not a cold plate.
- **Bare metal.** The claim's own words.
- **Small enough to answer.** A six-site operator with a public support address
  is more likely to reply than a hyperscaler.
- **Mission framing.** Non-profit heritage; efficiency is on-brand.

The post should lead with the conservative number, not the big one:

> 12,000 GPUs = 1,500 eight-GPU nodes. At 1 kW of fan per node and a 95 → 35 %
> duty cut, that is ~$1.57M/yr in fan power alone. One node's BMC fan-power
> reading would tell us whether that is real.

If they answer with 24,000, the number doubles. If they answer with "our fans
draw 300 W", the model updates and the claim shrinks. Both outcomes are good.

## Founder-led: Lambda (qualified)

**`LAMBDA-CASE.md`**. Lambda clears all five filters and adds a founder:

- **Air-cooled anchor:** ATL02 is 91,980 sq ft, planned up to **14 MW**, with a
  forced-air plenum; EdgeConneX also operates a second air-cooled Lambda site in
  Chicago. The new 23 MW Chicago build is hybrid, so it is an upper bound, not
  a confirmed air-cooled count.
- **Public fleet:** 18,000 GPUs leased to Nvidia, $1.5B over four years.
- **Public price:** H100 SXM **$3.99/GPU-hr**, B200 **$6.69**.
- **Founder + company:** @stephenbalaban (co-founder/CTO, 16.7K followers) and
  @LambdaAPI. A technical founder can check a BMC reading; a marketing inbox
  cannot.
- **Power-constrained:** 320 MW committed, 3 GW target by 2030. Every MW of fan
  power is a MW not sold as GPUs.
- **Assumed to pay the meter:** Lambda operates the sites, but the public record
  does not state the power contract. This is the first thing to confirm, not a
  fact to quote.

The most concrete number is the **operating ATL02 site**, not the lease. It is a
theoretical maximum at 10.2 kW/node, not a measured all-H100 fleet:

| scope | nodes | cost saving (R=36 best case) | capacity value |
|---|---:|---:|---:|
| ATL02 12 MW | 1,176 | **$1.43M/yr** | **$12.2M/yr** |
| ATL02 14 MW | 1,372 | **$2.07M/yr** | **$21.3M/yr** |
| 18,000-GPU lease | 2,250 | **$3.40M/yr** | **$35.1M/yr** |

The 18,000-GPU row assumes the whole lease is air-cooled. The cost column above
is the **R=36 best case**; at the simulator's 1.3–1.8× Coffin-Manson, ATL02 is
**$1.23–1.39M**, ATL02 14 MW is **$1.43–1.62M**, and the 18,000-GPU lease is
**$2.35–2.65M**. The case prints the
2D verification table: at 300 W fans and <50 % air-cooled share, the 7-figure
claim is false.

Lead with ATL02, not the lease. The post is in **`LAMBDA-OUTREACH.md`**.

## Founder-led: Together (conditional)

**`TOGETHER-CASE.md`**. Together clears the physics and the reach, but not the
ownership term cleanly:

- **The headline is liquid.** 36,000 GB200 NVL72 GPUs, co-built with Hypertec.
  Liquid-cooled. Zero fan watts. Counting it produces a false $6.8M/yr.
- **The claim is the older fleet.** "Thousands of existing H100 and H200 GPUs
  across North America." Air-cooled nodes, public price $3.99/GPU-hr.
- **The conditional:** Together operates the clusters, but co-builds them with
  partners. The public record does not say who owns the nodes or pays the power
  on the H100/H200 fleet. As of March 2025, "our own GPU clusters" was described
  as a coming diversification; the 500 MW of commitments are capitalized
  independently by investors.

At 8,000 air-cooled GPUs, the direct saving is **$1.21M/yr at 100 % ownership
at R=36** (**$1.04–1.18M** at the simulator's 1.3–1.8× Coffin-Manson) and **$0.76M at 50 %**.
The seven-figure boundary is **6,592 owned air-cooled GPUs at R=36**, or
**~6,800–7,700** at the lower ratios. The ask is not "measure your fans"; it is
"who pays the meter".

## Founder-led: Modal (disqualified)

**`MODAL-CASE.md`**. Modal is the most developer-visible GPU platform of the
cycle and a bad target for this claim:

- **No data centers, no nodes.** Modal's CTO: "We don't have our own data
  centers." DCD: "does not own/operate data centers"; 13 cloud partners.
- **The fan bill is real but not Modal's.** The ~48k-GPU fleet behind its $1B
  ARR has a **$6.3–7.1M/yr** fan bill at 1.3–1.8× (**$9.1M** at R=36) —
  **0.63–0.71 %** of revenue (**0.91 %** at R=36) — and it lands on the providers.
- **Modal's lever is utilization.** Packing 35 % → 60 % is worth ~$416.7M/yr
  gross, a different business from a cost saving. That is already the product.

Do not pitch Modal the fan claim. Pitch the providers, or pitch Modal the
utilization story it already knows.

## Disqualified, and why

| target class | reason |
|---|---|
| CoreWeave, hyperscalers | too large to route a cold technical claim; many liquid-cooled |
| GB200 NVL72 / cold-plate operators | **no fan energy to save** |
| platforms on top of other people's nodes | can measure the fan, cannot capture the saving |
| labs under ~500 nodes | the claim is arithmetically impossible there |
| crypto-mining conversions | fan control is already the business; no gap |

## How to post

1. **Tag one, not five.** A post that tags five companies reads as spam and
   gets ignored by all five.
2. **Lead with their number, not ours.** "1,500 nodes × $702" is checkable.
   "We built a controller" is not.
3. **Ask for one datapoint.** A BMC fan-power reading is a five-minute task for
   an operator and a decisive input for the model.
4. **Offer the code, not a service.** The repo runs; the ask is validation.
5. **State the failure condition in the same thread.** It is the strongest
   credibility signal in the post — and it is true.
6. **Tag the founder, not just the company.** A technical founder can check a
   BMC reading; a marketing inbox routes it to a queue. Founder + company is
   the maximum — never three accounts.
7. **Check ownership before you write the post.** If the target does not pay
   the fan power, the saving is someone else's. That is the Modal lesson.

## The ask, verbatim

> One reading from one node: `FanPower`, `P12V_FAN`, or per-fan watts from the
> BMC. Or a 30-day trace of fan duty and node power. That replaces the model's
> only load-bearing guess with a measurement.

For Together, add: **"and tell us who pays the meter on the H100/H200 fleet."**
For Modal, the ask is nothing; the claim does not route.
