# Fan observability on the Vivobook X1502VA — findings

Read-only investigation, 2026-10-20. Every claim below traces to a run in this
directory or to a named source.

## The interface that works

The legacy `\\.\ATKACPI` device opens but `DeviceIoControl` fails. The live path
is the ASUS ACPI WMI method class:

    root\wmi:AsusAtkWmi_WMNB.InstanceName="ACPI\PNP0C14\ATK_0"

- GUID `{97845ED0-4E6D-11DE-8A39-0800200C9A66}` (same as Linux `asus-wmi`)
- methods: `INIT`, `DSTS`, `DEVS`, `FANL`, `SFUN`, `SPEC`, `BSTS`, `WDOG`, ...
- **requires elevation**: unelevated returns access denied or silent zeros
- `DSTS` returns `0xFFFFFFFE` for device ids the firmware does not implement

## Live device ids (82 swept, 7 implemented)

| id | Linux name | value observed |
|---|---|---|
| `0x00110013` | `CPU_FAN_CTRL` | 65555 / 65556 (flickers by 1) |
| `0x00110014` | `GPU_FAN_CTRL` | 0 (constant) |
| `0x00110015` | — | 0 (constant) |
| `0x00110016` | — | 0 (constant) |
| `0x00110019` | `THROTTLE_THERMAL_POLICY_VIVO` | 50528256 = `0x03030000` |
| `0x0011001F` | — | 0 (constant) |
| `0x00120078` | — | 0 (constant) |

Source: `include/linux/platform_data/x86/asus-wmi.h`. Thermal policy modes are
0 = default, 1 = overboost, 2 = silent (`asus-wmi.c`).

**None of these are tachometers.** They are control/status registers. A run at
≤71 °C on battery showed no movement in any of them except a one-count flicker
on `0x00110013`, which is consistent with a counter, not a measurement.

## Surfaces that are definitively not available

- **EC**: `WindowsEmbeddedControllerIO` reads 0 non-zero registers out of 256,
  and a sweep costs ~32 s. Not a bank issue we can fix blind; the transport is
  not reaching the EC. Do not sample it in a time series.
- **`Win32_Fan`**: empty.
- **Intel DPTF**: device present, but no DPTF fan WMI class exists. Only
  `MSAcpi_ThermalZoneTemperature` (one zone, 55.1 °C idle).
- **LHM**: no Fan sensors; its EC path is the same dead one.

## Open question (needs AC)

On battery the package plateaus at ~71 °C, which may be below the fan start
threshold. On AC stock this machine reaches 82.2 °C at 37.6 W. The decisive test
is the same scan on AC with a hot target of 82 °C: if `0x00110013`'s low bits
rise with the fan, it is a fan-level read-back; if nothing moves, the fan is not
observable through any user-mode surface on this model.

## Write path (not yet exercised)

`DEVS(dev_id, value)` exists and `FANL(control_func)` exists. Both are writes.
The plan before the first write:

1. record the current `DSTS` value of the target id as the restore value
2. write that same value back (no-op) and confirm `DEVS` returns 1 and `DSTS`
   is unchanged — this proves the call path without changing state
3. change one thing at a time, with a watchdog that restores the recorded value
   if the process dies or the temperature crosses the critical limit
4. verify by read-back and by temperature, not by assumption

## Harness

- `scan.ps1` — read-only, elevated; MSR + live WMI ids at 2 s; adaptive load
  that holds until `t_max >= HotTarget`; full WMI sweep at phase boundaries;
  one EC sweep for the record; pauses and restores the governor in `finally`.
- `rank.py` — rise / return / repeat test, lagged correlation, power-image
  rejection. Rejects monotone counters and constant registers.
- `selftest.py` — synthetic ground truth: finds a fan in both polarities,
  rejects a counter, labels a power rail. 5/5.
