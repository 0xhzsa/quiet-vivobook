# REPRODUCE

Three levels of reproduction, from cheapest to most valuable:

1. **The model** — run the code on your own machine, no hardware needed.
2. **The laptop A/B** — repeat the throughput measurement on the machine in
   front of you.
3. **A real 8-GPU node** — the measurement that would replace the largest
   assumption in this repository.

---

## 0. What you need

**For level 1**

- Python 3.10 or newer, and [uv](https://docs.astral.sh/uv/) (`uv --version`).
- Nothing else. The code has no third-party dependency and there is no
  `pyproject.toml`.

```powershell
git clone https://github.com/0xhzsa/quiet-vivobook.git
cd quiet-vivobook
```

**For level 2**

- Windows 10 or 11.
- AC power. The harness refuses to run on battery.
- Administrator rights for the part that creates the Quiet power scheme
  (a registry write under `HKLM\SYSTEM\CurrentControlSet\Control\Power`).
  The A/B itself does not need elevation.
- A quiet room is not required; a quiet *machine* is. Do not run anything
  else on it.

**For level 3**

- A BMC you can reach with `ipmitool`, and permission to change fan duty on
  a node you own.
- A fixed workload whose completed work you can count.
- A PDU or wall meter if the BMC cannot see the fan power — on some
  chassis the fan tray sits on a separate rail that the BMC does not meter.

---

## 1. Run the model

```powershell
# the verification entry point: expect "0 hard failure(s), 4 warning(s)"
uv run --no-project python code/audit.py

# every module that has a self-test
uv run --no-project python code/fanlaw.py --selftest
uv run --no-project python code/cycling.py --selftest
uv run --no-project python code/case.py --selftest
uv run --no-project python code/targets.py --selftest
uv run --no-project python code/lambda_case.py --selftest
uv run --no-project python code/together_case.py --selftest
uv run --no-project python code/modal_case.py --selftest
uv run --no-project python code/portfolio.py --selftest
uv run --no-project python code/throughput.py --selftest
uv run --no-project python code/server_thermal_controller.py --selftest

# the 8-GPU simulation, calibrated to the upstream 120 W -> 15 W measurement
uv run --no-project python code/server_thermal_controller.py --node gpu8 --duration 120
```

Expected from the last command:

```
Fan: 880.98W -> 121.14W (save 759.84W = 86.25%)
Work: 1.0 -> 0.9485 (cost 5.15%)
Temp: 63.75C -> 89.73C
Annual fan saving: $839/node
```

**The duration is part of the claim.** `--duration 120` is the operating point
the published 5.15 % comes from. The default `--duration 300` runs the same
model longer, into thermal throttling, and reports a much larger cost
(31.41 % at 300 s). Anyone quoting the 5.15 % must quote the duration with it.

`code/cycling.py --replay data/telemetry-sample.csv` replays the committed
1.67 h trace: 109 full cycles, mean ΔT 5.9 °C, 65.5 cycles/hour, and 15 % of
the cycles carrying 55 % of the damage.

---

## 2. The laptop A/B

The clean measurement in this repository, on your own machine.

```powershell
# 1. Create the "Quiet (quiet-vivobook)" power scheme if it does not exist.
#    It duplicates the stock scheme and renames it, then applies the
#    'efficient' profile. Needs elevation.
powershell -NoProfile -ExecutionPolicy Bypass -File controller/profile.ps1 -Mode efficient

# 2. Run the A/B. No elevation. Takes about 15 minutes.
powershell -NoProfile -ExecutionPolicy Bypass -File controller/fan-scan/scheme-ab.ps1
```

What it does, and why each part is there, is in `docs/METHOD.md` §1. The
short version: it pauses the governor with `controller/paused.flag`, warms up,
then runs four blocks of Balanced and Quiet in alternating order, measuring
the completed-work rate over the last 40 s of each 60 s phase, and restores
your original power scheme in `finally`.

Output lands in `controller/fan-scan/scheme-<timestamp>/`:

| file | contents |
|---|---|
| `summary.json` | the block ratios, the mean, and the throughput cost |
| `samples.jsonl` | one line per sample: timestamp, scheme, work counter, live thread count |
| `scheme.log` | the human-readable trace |

The committed run is `controller/fan-scan/scheme-ab-latest-summary.json`:

```
block 1  balanced,quiet   quiet/balanced = 0.9351
block 2  quiet,balanced   quiet/balanced = 0.9916
block 3  balanced,quiet   quiet/balanced = 0.9127
block 4  quiet,balanced   quiet/balanced = 0.8838
mean 0.9308  ->  6.92% throughput cost
```

Two things to know before you run it:

- The harness measures the difference between the two schemes **as they are
  configured**. If you want a different Quiet profile, change it in
  `controller/config.json` and re-run `profile.ps1` first.
- `profile.ps1` leaves the governor paused, and the harness only removes the
  pause flag if it created it. Hand control back afterwards:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File controller/profile.ps1 -Mode resume
```

If you want the thermal-policy actuator instead of the power scheme, read
`controller/README.md` first. It documents the safety model, the VIVO encoding
trap (writing `1` expecting overboost silently sets silent), and the
read-back proof. Do not skip the no-op write.

---

## 3. A real 8-GPU node: the 30-day protocol

This is the measurement that would replace the largest assumption in the
repository. The fan tray wattage is a model input; everything downstream of it
is arithmetic.

### 3.1 Read the fan power

```bash
ipmitool sensor list
ipmitool sdr elist | grep -i -E "fan|power"
```

Look for `FanPower`, `P12V_FAN`, `FAN1`..`FAN8`, `SYS_FAN_PWR`, or any SDR
whose reading is in watts and whose name mentions a fan.

If nothing does, the BMC does not meter the fan rail. Measure it externally:
a PDU on the fan PSU, or a clamp meter on the fan harness, logged alongside
the BMC data. Do not substitute a vendor datasheet number for a reading in
your own chassis — the whole point of this measurement is the chassis in
front of you.

Record: the full fan wattage at 100 % duty, and the node's IT power at the
same time.

### 3.2 Set the duty

The command upstream uses, and the one this protocol assumes:

```bash
# set manual (FULL) fan mode
ipmitool raw 0x30 0x45 0x01 0x01

# set one zone's duty, e.g. zone 0x00 to 35%
ipmitool raw 0x30 0x70 0x66 0x01 0x00 0x23

# read it back
ipmitool sensor list | grep -i pwm
```

Byte by byte: `0x30` is the chassis control command, `0x70`/`0x66` select the
fan zone and the duty parameter, `0x01` is the byte count, then the zone id
and the duty byte (`0x23` = 35 %).

**Know your failsafe before you start.** Upstream's is: set the mode to FULL
and every zone to 100 %.

```bash
ipmitool raw 0x30 0x45 0x01 0x01
ipmitool raw 0x30 0x70 0x66 0x01 0x00 0x64   # and every other zone
```

Also know that most BMCs will not let you go below a vendor floor (upstream's
controller refuses to go below 25 % for stall reasons), and that some will
ignore manual mode entirely. Verify by reading the PWM sensor back after
every write, the way `controller/` does for the laptop.

### 3.3 Hold a fixed workload

- One fixed job per GPU, the same job every time, the same input size.
- **Count completed work, not wall-clock time.** Completed iterations, tokens,
  frames or training steps. A faster clock on an idle GPU is not work.
- Record the workload's own duration and its result checksum, so a truncated
  or failing job is visible.
- Do not change anything else on the node: no driver updates, no container
  image changes, no other tenants starting and stopping.

### 3.4 Run A/B/A, repeatedly

```
| baseline (95 %) | controlled (35 %) | baseline (95 %) |   -> one block
```

- The closing baseline must reproduce the opening baseline. If it does not,
  the block is void — and that is a finding, not a nuisance: it means the node
  drifts, and a drift of that size over a 30-day run is itself worth knowing.
- Alternate the order of the two conditions, as the laptop harness does.
- Fix the length of every phase, and log the actual length. A phase that dies
  early is not comparable.

### 3.5 Run it for 30 days

One day is an anecdote. Thirty days covers the weekly cycle of ambient
temperature and tenant load, which is the thing most likely to invalidate a
short test.

Log, every minute:

| field | why |
|---|---|
| fan power (W) | the quantity being modelled |
| fan duty (%) per zone | the actuator state, so a rejected write is visible |
| node IT power (W) | the context for the saving |
| GPU temperature (°C) | the constraint the duty change is trading against |
| completed work | the cost side |
| job id and checksum | so a truncated job is visible |

### 3.6 Decide

Compare the measured throughput loss with the fan saving, using the same
ledger the code uses:

```powershell
uv run --no-project python code/throughput.py --fan-saving <measured $/node/yr>
```

**The pass criterion depends on the fleet's capacity regime:**

- **Spare capacity** (utilisation below ~95 %): the work that did not happen
  was work the node could not have sold anyway. The immediate revenue cost
  is zero; what you lose is headroom. This is the regime most operators are
  actually in, and it is why the fan leg looks good on paper.
- **Capacity-constrained** (utilisation at 100 %): every GPU-hour the cluster
  cannot deliver is one the customer is paying for. The loss bills back at
  list price, and the project can go negative. At the modelled $839/node/yr
  fan saving against a $167,772/node/yr revenue basis, **the break-even is a
  0.50 % throughput loss** (`code/throughput.py` prints it as
  `breakeven_cost_fraction`).

Reference points from the model, for calibration of expectations:

| throughput estimate | value | provenance |
|---|---:|---|
| measured laptop A/B | 6.92 % | measured, this machine |
| simulated 8-GPU model at 95 % → 35 %, 120 s | 5.15 % | simulated, calibrated |
| simulated laptop MPC controller | 20.6 % | simulated |
| break-even on a saturated fleet | 0.50 % | arithmetic |

If the measured loss is above the break-even on a saturated fleet, the honest
answer is that the duty has to be gentler — 95 % → 50 % instead of 95 % → 35 %
— or the fleet has to have spare capacity. Both of those are decisions, and
they are better than a spreadsheet.

### 3.7 Publish the artifact

Commit the raw log and a summary in the shape of
`controller/fan-scan/scheme-ab-latest-summary.json`: one record per block,
with the ratios, the mean, the range, and the conditions. If any block is
void, keep it and say why.
