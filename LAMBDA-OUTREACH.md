# Lambda outreach — draft only, do not post

**Status: not posted. Not scheduled. Nothing sent.** This file exists so the
claim can be reviewed before it is addressed to a real person.

Target: **@stephenbalaban** (co-founder/CTO, 16.7K followers) and
**@LambdaAPI** (company). The case is in `LAMBDA-CASE.md`; the model is
`code/lambda_case.py`.

The rule for this account: **lead with their number, ask for one datapoint,
state the failure condition in the same thread.** No pitch, no service, no
"thought leadership".

---

## 1. The main post (under 280 characters)

> @stephenbalaban @LambdaAPI ATL02 is ~12 MW air-cooled. At 1 kW fan/node, a
> 95→35% duty cut is $1.23–1.39M/yr in fan + fatigue at 1.3–1.8× ($1.78M at
> R=36) — and ~1.1 MW of freed capacity, ~$18M/yr at your $3.99 H100 price.
> One BMC fan reading settles it. https://github.com/0xhzsa/quiet-vivobook

Character count: ~265. Fits a standard post.

Why this order:

1. **ATL02 is theirs and public.** Not "a hypothetical fleet".
2. **$1.23–1.39M is the honest operating-site range; $1.78M is the R=36 best
   case.** The $3.4M lease number assumes all 18,000 GPUs are air-cooled.
3. **$18M is the number that makes a CTO look.** It is their own list price,
   not an analyst's TAM.
4. **The ask is one reading**, not a meeting.

---

## 2. The follow-up (the method, 1/3)

> The model is three legs: fan affinity (P ∝ duty³), a swing-ratio fatigue
> scenario (with a separate rainflow simulator), and capacity at Lambda's own
> $3.99/GPU-hr. 13 self-tests. It also prints where the claim fails: at 300 W
> fans and <50% air-cooled share, the 7-figure number is not supported by the
> ideal fan curve alone.

Why: it proves the work is verifiable, not a pitch. The failure condition is
the most credible line in the thread.

---

## 3. The follow-up (the ask, 2/3)

> The ask is one datapoint: `FanPower`, `P12V_FAN`, or per-fan watts from one
> ATL02 or Chicago node. Or a 30-day trace of fan duty and node power. That
> replaces the model's only load-bearing guess with a measurement. If it comes
> back at 300 W, the number shrinks and the case says so.

Why: it gives Lambda an easy exit and makes the model's honesty concrete.

---

## 4. The DM (only if there is a prior interaction)

> Stephen — I built a self-tested model of fan-energy and thermal-fatigue
> savings on air-cooled GPU nodes. Applied to ATL02's 12 MW, it is
> $1.23–1.39M/yr at 1.3–1.8× ($1.78M at R=36) in cost and ~$18M/yr of capacity
> at Lambda's $3.99 H100 price. The one
> unknown is the fan tray wattage. Would you be open to one BMC reading from an
> ATL02 node? I can send the model first; it prints its own failure conditions.

Do **not** send this cold. A DM before a public post reads as a pitch and gets
ignored. The public post is the introduction.

---

## 5. Reply handling

| if Lambda says | response |
|---|---|
| "Our fans are 300 W" | Update the model, publish the lower number, thank them. At ATL02 12 MW the total is still ~$1.04M/yr; the energy-only claim drops to ~$317k. The claim shrinks — that is the point. |
| "Those sites are liquid-cooled" | Clarify the case is ATL02/air-cooled only; ask which sites are air-cooled. If none, the case does not apply and we say so. |
| "We already do this" | Ask for the measured fan power and duty trace. If they have it, the model becomes a measurement instead of a model. |
| "Send the deck" | Send the repo, not a deck. The code runs; the case prints its own failure conditions. |
| "What do you want?" | Nothing. One reading, credit for the data, and the model stays public. |
| No reply | One follow-up after 5–7 days, then stop. No tagging the CEO, no quote-tweeting, no "bumping". |

---

## 6. What not to do

- **Do not tag more than two accounts.** Founder + company is the maximum. A
  post that tags five operators reads as spam.
- **Do not lead with the 18,000-GPU number as if it were all air-cooled.** It
  is a lease, not a cooling map. The public air-cooled site is ATL02.
- **Do not present the capacity leg as a saving.** It is revenue capacity that
  needs capex and demand. The post says "freed capacity", not "savings".
- **Do not claim the fan tray is 1 kW.** It is an input. The ask is the reading.
- **Do not attach a PDF.** Link the repo. The code is the credibility.
- **The repo is public: https://github.com/0xhzsa/quiet-vivobook.**

---

## 7. Pre-post checklist

- [ ] `uv run python code/lambda_case.py --selftest` → 13/13
- [ ] `LAMBDA-CASE.md` numbers match the model output (last check: 2026-10-20)
- [x] Repo URL: https://github.com/0xhzsa/quiet-vivobook
- [ ] Repo is public and the README links `LAMBDA-CASE.md`
- [ ] The post says "ATL02", not "Lambda's fleet"
- [ ] The post says "if it comes back at 300 W, the number shrinks"
- [ ] The account has a profile, a pinned post, and a real history
- [ ] No other company is tagged in the same post

---

## 8. The one-sentence version

If only one sentence survives:

> **Lambda's ATL02 air-cooled site is ~12 MW; at 1 kW of fan per node, the fan
> power and cycling are worth $1.23–1.39M/yr at 1.3–1.8× ($1.78M at R=36) —
> and the same watts are ~$18M/yr of H100 capacity at Lambda's own price. One
> BMC reading decides which number is real.**
