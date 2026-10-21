# The controller (Windows, ASUS Vivobook X1502VA)

Source for the machine-side half of the project: an MPC thermal governor that
has no fan telemetry to close the loop on.

**This is model-specific.** It was built and verified on an ASUS Vivobook 15
X1502VA (i9-13900H, BIOS `X1502VA.306`). The ASUS WMI actuator path exists on
other ASUS laptops, but the VIVO thermal-policy encoding and the device ID must
be verified by read-back before you write anything.

## Requirements

- Windows 10/11, administrator rights.
- **PawnIO** — signed, HVCI-compatible MSR driver. It ships with current
  LibreHardwareMonitor builds; `install.ps1` uses the copy embedded in the
  LibreHardwareMonitor executable.
- **LibreHardwareMonitorLib.dll** — not vendored here (14 MB of binaries,
  including debug symbols, does not belong in this repo). Download it from
  [LibreHardwareMonitor releases](https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/releases)
  and place it at:

  ```
  controller\tools\lhm\LibreHardwareMonitorLib.dll
  ```

## Safety model

The actuator is a firmware setting, not a fan command. Before the first write
the harness:

1. reads the current mode and records it as the **baseline** (`thermal-state.json`,
   written once — never overwritten on restart);
2. performs a **no-op write** (current mode → current mode) and verifies the
   read-back;
3. starts an **independent elevated watchdog** holding the restore value;
4. aborts on an over-temperature reading;
5. restores the baseline in `finally`, unconditionally.

The governor applies the configured mode on start and restores the recorded
baseline on exit. If it is killed, the watchdog restores. If both die, the
machine keeps the last mode — which is why the no-op check and the read-back
exist before anything changes.

## Steps

Read-only first. Nothing below writes until step 3, and step 3 restores.

```powershell
# 1. Map the sensors. Read-only; elevated. Writes run-<stamp>\ranked.csv.
.\fan-scan\run.ps1

# 2. Read the thermal-policy state. Read-only. Needs elevation.
. .\thermal-policy.ps1; Get-ThermalMode

# 3. Prove the write path: no-op, silent, restore, overboost, restore.
.\fan-scan\run-devs.ps1

# 4. Install the governor (elevated, registers a scheduled task at logon).
.\install.ps1

# 5. Report.
.\report.ps1
```

`run-devs.ps1` is the one to read before trusting any of this. It writes each
mode, reads it back, and restores. The committed result is in
`fan-scan/devs-20261020-155011/result.json`: `restored_ok: true`, every
read-back matched. `fan-scan/RESULTS.md` explains the two effect runs —
including the one that is invalid, and why.

## Configuration

`config.json`:

| key | meaning |
|---|---|
| `thermalPolicyMode` | `0` balanced, `1` silent, `2` overboost (VIVO encoding) |
| `profiles` | power states the MPC chooses between |
| `targetHigh` / `targetLow` | control band, °C |
| `controller.horizon` | MPC horizon, samples (18 × 5 s = 90 s) |
| `controller.wPerf` | weight on lost work; `wOver` penalises heat |

The profiles in the shipped config are the **measured** ones from this machine
(`data/profiles.csv`). If you run this on different hardware, re-measure them
with `fan-scan\scan.ps1`; do not reuse these numbers.

## The encoding trap

VIVO is not the generic ASUS mapping:

| value | VIVO | generic ASUS |
|---|---|---|
| 0 | balanced | balanced |
| 1 | **silent** | overboost |
| 2 | **overboost** | silent |

Writing `1` expecting overboost silently sets silent. The mapping came from the
Linux `asus-wmi` driver and was confirmed by read-back on this machine. Verify
it on yours.

## What it cannot do

- **No fan RPM.** The embedded controller exposes 0 non-zero registers of 256,
  `Win32_Fan` is empty, DPTF has no fan class, and LibreHardwareMonitor has no
  fan sensor. The loop closes on package power and per-core temperature.
- **No fan power.** Same reason. The fleet model's fan wattage is an input, not
  a measurement from this machine.
- **No acoustic guarantee.** Without RPM or a calibrated microphone, any dB
  claim would be invented.

## Uninstall

```powershell
.\uninstall.ps1
```

Unregisters the task and restores the recorded baseline. The power scheme is
left in place; delete `Quiet (quiet-vivobook)` in `powercfg` if you want it
gone.
