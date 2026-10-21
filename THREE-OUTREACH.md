# Outreach: three founders, three different asks

**Status: not posted. Nothing here has been sent.** The Lambda long-form drafts
are in `LAMBDA-OUTREACH.md`; this file is the consolidated version for all three
cases, with the ownership check applied.

The rule from `TARGETS.md` still holds: tag one founder and one company, lead
with their number, ask for one datapoint, and put the failure condition in the
same thread.

---

## Lambda — qualified

**To:** @stephenbalaban + @LambdaAPI. Long-form drafts in `LAMBDA-OUTREACH.md`.

The short version:

> Lambda's ATL02 is a 12 MW air-cooled site: 1,176 eight-GPU nodes. At 1 kW of
> fan per node and a 95 → 35 % duty cut, the fan and fatigue saving is
> **$1.23–1.39M/yr** at 1.3–1.8× (**$1.78M** at R=36). The freed watts are
> **1.1 MW**, which at Lambda's own $3.99/GPU-hr is **$18.3M/yr** of capacity.
>
> The 18,000-GPU Nvidia lease is **$2.35–2.65M/yr** direct at 1.3–1.8×
> (**$3.40M** at R=36) if the whole lease is air-cooled. The 2D verification table is fan wattage × air-cooled share: at
> 300 W and <50 % air-cooled, the seven-figure claim is false.
>
> One BMC fan-power reading from ATL02 would replace the model's only
> load-bearing guess. Code and failure conditions: https://github.com/0xhzsa/quiet-vivobook

**The ask:** one `FanPower` / `P12V_FAN` reading, or a 30-day fan-duty trace.

---

## Together — conditional

**To:** @vipulved + @togethercompute.

### Post 1

> Together's 36,000-GPU cluster is GB200 NVL72. That is liquid — no fan tray, no
> fan saving. The interesting fleet is the air-cooled H100/H200 layer:
> "thousands" of GPUs at $3.99/GPU-hr.
>
> At 8,000 GPUs and 1 kW of fan per node, a 95 → 35 % duty cut is
> **$1.04–1.18M/yr** at 1.3–1.8× in energy + fatigue (**$1.51M** at R=36), and
> only if Together pays the meter. On a partner-owned node, that dollar is
> Hypertec's.
>
> The seven-figure line is **~6,800–7,700 owned air-cooled GPUs**; at 8k that
> means **~85–96 %** of the fleet's power bill. One question decides it: who
> pays the power bill?
>
> Code + verification: https://github.com/0xhzsa/quiet-vivobook

### Post 2 (follow-up in the same thread)

> The 2D table is fleet size × ownership share. At 8,000 GPUs and 50 % owned,
> the direct claim is **$0.52–0.76M** — below seven figures. At 16,000 GPUs and
> 50 % owned, it clears. The claim is a contract question before it is a fan
> question.
>
> The 36,000-GPU liquid cluster contributes **$0** to every column. Counting it
> would produce a false $6.8M/yr. That is the trap this case is built to avoid.

### DM

> Vipul — I built a thermal case study on Together. The short version: the 36k
> GB200 cluster is liquid, so the fan claim does not apply there. The air-cooled
> H100/H200 fleet is the target, but the number depends on who owns the nodes
> and pays the power.
>
> If Together pays the meter on ~6,800–7,700 air-cooled GPUs, the fan + fatigue
> saving is seven figures depending on the cycling assumption. If Hypertec does,
> the saving is Hypertec's. One BMC fan-power reading and one answer on the power
> contract would settle it.
>
> Code and the full verification table: https://github.com/0xhzsa/quiet-vivobook. No ask beyond the
> datapoint.

**The ask:** the air-cooled H100/H200 node count, and who pays the meter.

**Do not say:** "Together owns 8,000 GPUs" or "Together saves $1.51M". The
public record does not support either. The correct phrasing is "at 100 %
ownership, the gross fleet saving would be..." and "the attributable saving
depends on the contract."

---

## Modal — disqualified

**To:** @bernhardsson + @modal. This is optional. The honest move is not to
pitch the fan claim.

### DM / short note

> Erik — I wrote a thermal case study that includes Modal, and the honest result
> is that the fan claim does not route to you. You do not own the data centers
> or the nodes; the fan bill sits on your 13 providers' P&L.
>
> The fan bill behind a $1B-ARR fleet is **$6.3–7.1M/yr** at 1.3–1.8×
> (**$9.1M** at R=36), about **0.63–0.71 %** of revenue (**0.73 %** at R=36).
> Your utilization lever (35 → 60 %) is **~$417M/yr gross**, a
> different business, not a like-for-like saving. The fan claim is not just
> unattributable to Modal; it is immaterial next to the thing you already sell.
>
> Not pitching you the fan claim. If it is useful, the case is here:
> https://github.com/0xhzsa/quiet-vivobook. If Modal ever wants provider-side fan telemetry as a procurement
> term, that is the only version that makes sense.

**The ask:** nothing for the fan claim. If Modal wants to pursue the
provider-side saving, the ask is the provider list and which contracts are
power-indexed.

**Do not say:** "Modal can save $9.1M". It cannot; its providers can. The
correct phrasing is "the fan bill behind Modal's fleet is $6.3–7.1M at 1.3–1.8×,
$9.1M at R=36, and it belongs to the providers."

---

## Pre-post checklist

- [ ] All self-tests pass: `lambda_case` 13, `together_case` 16, `modal_case`
      17, `portfolio` 10, `case` 12, `cycling` 17, `targets` 12 — 97 checks.
- [x] Live repo URL: https://github.com/0xhzsa/quiet-vivobook
- [ ] The post tags **one founder + one company**, not three.
- [ ] The verifier is in the same thread, not buried in the repo.
- [ ] No fan wattage is presented as measured. It is a 1 kW input.
- [ ] No liquid GPU is counted. The 36k GB200 is explicitly excluded.
- [ ] Together's ownership share is described as unknown, not assumed.
- [ ] Modal's fan bill is attributed to its providers, not to Modal.
- [ ] The capacity column is labelled "revenue capacity, not a saving".
- [ ] The user has approved the post.

Until the last box is checked, nothing goes out.
