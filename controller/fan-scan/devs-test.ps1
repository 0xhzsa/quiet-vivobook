#requires -Version 5.1
<#
  devs-test.ps1 - prove the ASUS thermal-policy write path, then put it back.

  Target: 0x00110019 ASUS_WMI_DEVID_THROTTLE_THERMAL_POLICY_VIVO
  Encoding on VIVO is NOT the generic one:
      0 = default (balanced)
      1 = SILENT
      2 = OVERBOOST
  (generic ASUS is 1 = overboost, 2 = silent - do not copy it here)

  Order of operations, deliberately:
    1. read and record the current mode
    2. start an independent elevated watchdog holding the restore value
    3. write the current mode back unchanged (no-op) and read it back
    4. only then change state, one step at a time, restoring after each
    5. create the done flag so the watchdog stands down

  Nothing here runs under sustained load. The question is only whether the
  call path works and whether the firmware reports the change back.
#>
param(
  [uint32]$DeviceId = 0x00110019,
  [string]$OutDir
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
if (-not $OutDir) { $OutDir = Join-Path $PSScriptRoot ('devs-' + (Get-Date).ToString('yyyyMMdd-HHmmss')) }
New-Item -ItemType Directory -Path $OutDir -Force | Out-Null

$logPath = Join-Path $OutDir 'devs.log'
$jsonPath = Join-Path $OutDir 'result.json'
$doneFlag = Join-Path $OutDir 'done.flag'
$utf8 = New-Object System.Text.UTF8Encoding($false)

function Log($m) {
  $line = '{0} {1}' -f (Get-Date).ToString('HH:mm:ss.fff'), $m
  Write-Host $line
  [System.IO.File]::AppendAllText($logPath, $line + "`r`n", $utf8)
}

$elevated = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $elevated) { Log 'REFUSING: write path needs elevation'; exit 2 }

$path = 'root\wmi:AsusAtkWmi_WMNB.InstanceName="{0}"' -f 'ACPI\PNP0C14\ATK_0'.Replace('\', '\\')
Log "resolving $path"
$asus = [wmi]$path

function Get-Dsts([uint32]$id) {
  $in = $asus.PSBase.GetMethodParameters('DSTS')
  $in.Device_ID = $id
  $out = $asus.PSBase.InvokeMethod('DSTS', $in, $null)
  return [int64]$out['device_status']
}

function Set-Devs([uint32]$id, [uint32]$value) {
  $in = $asus.PSBase.GetMethodParameters('DEVS')
  $in.Control_status = $value
  $in.Device_ID = $id
  $out = $asus.PSBase.InvokeMethod('DEVS', $in, $null)
  return [int64]$out['result']
}

function Get-ThermalZoneC {
  try {
    $z = Get-CimInstance -Namespace root\wmi -ClassName MSAcpi_ThermalZoneTemperature -ErrorAction Stop |
      Select-Object -First 1
    if ($z) { return [math]::Round(($z.CurrentTemperature / 10.0) - 273.15, 1) }
  } catch { }
  return $null
}

$result = [ordered]@{
  device_id = ('0x{0:X8}' -f $DeviceId)
  baseline_raw = $null
  baseline_mode = $null
  noop = $null
  silent = $null
  overboost = $null
  restored_raw = $null
  restored_ok = $false
  aborted = $null
  steps = @()
}

$baselineRaw = Get-Dsts $DeviceId
$baselineMode = [int]($baselineRaw -band 0xFFFF)
$result.baseline_raw = $baselineRaw
$result.baseline_mode = $baselineMode
Log ('baseline raw=0x{0:X8} mode={1}' -f $baselineRaw, $baselineMode)

if ($baselineRaw -eq 4294967294) {
  $result.aborted = 'device id not implemented'
  Log 'ABORT: id not implemented'
  [System.IO.File]::WriteAllText($jsonPath, ($result | ConvertTo-Json -Depth 5), $utf8)
  exit 1
}

# Independent restore process, elevated because this process is.
$watchdog = Start-Process -FilePath 'powershell.exe' -PassThru -WindowStyle Hidden -ArgumentList @(
  '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', (Join-Path $PSScriptRoot 'devs-watchdog.ps1'),
  '-DeviceId', $DeviceId, '-RestoreValue', $baselineMode,
  '-DoneFlag', ('"{0}"' -f $doneFlag), '-TimeoutSec', '30', '-Log', ('"{0}"' -f $logPath)
)
Log "watchdog started pid=$($watchdog.Id)"

$history = @()

try {
  # 1. no-op: write the value that is already there
  $tz = Get-ThermalZoneC
  if ($null -ne $tz -and $tz -gt 90) { throw "thermal guard: $tz C before first write" }
  $r = Set-Devs $DeviceId $baselineMode
  $after = Get-Dsts $DeviceId
  $result.noop = [ordered]@{ result = $r; raw = $after; mode = [int]($after -band 0xFFFF) }
  Log ('no-op write value={0} result={1} -> raw=0x{2:X8} mode={3}' -f $baselineMode, $r, $after, ([int]($after -band 0xFFFF)))
  $history += "noop result=$r mode=$([int]($after -band 0xFFFF))"

  if ($r -ne 1) {
    $result.aborted = 'no-op write did not return 1; call path not confirmed'
    Log 'ABORT: no-op did not return 1, not changing state'
    throw 'no-op failed'
  }

  # 2. silent (VIVO: 1)
  $r = Set-Devs $DeviceId 1
  $after = Get-Dsts $DeviceId
  $result.silent = [ordered]@{ result = $r; raw = $after; mode = [int]($after -band 0xFFFF) }
  Log ('silent  write value=1 result={0} -> raw=0x{1:X8} mode={2}' -f $r, $after, ([int]($after -band 0xFFFF)))
  $history += "silent result=$r mode=$([int]($after -band 0xFFFF))"
  $restore1 = Set-Devs $DeviceId $baselineMode
  Log ('restore value={0} result={1} -> raw=0x{2:X8}' -f $baselineMode, $restore1, (Get-Dsts $DeviceId))

  # 3. overboost (VIVO: 2)
  $r = Set-Devs $DeviceId 2
  $after = Get-Dsts $DeviceId
  $result.overboost = [ordered]@{ result = $r; raw = $after; mode = [int]($after -band 0xFFFF) }
  Log ('overboost write value=2 result={0} -> raw=0x{1:X8} mode={2}' -f $r, $after, ([int]($after -band 0xFFFF)))
  $history += "overboost result=$r mode=$([int]($after -band 0xFFFF))"
  $restore2 = Set-Devs $DeviceId $baselineMode
  Log ('restore value={0} result={1} -> raw=0x{2:X8}' -f $baselineMode, $restore2, (Get-Dsts $DeviceId))
} catch {
  $result.aborted = $_.Exception.Message
  Log "ERROR: $($_.Exception.Message)"
} finally {
  # unconditional restore, then verify
  try {
    $null = Set-Devs $DeviceId $baselineMode
    $finalRaw = Get-Dsts $DeviceId
    $result.restored_raw = $finalRaw
    $result.restored_ok = ([int]($finalRaw -band 0xFFFF) -eq $baselineMode)
    Log ('final restore -> raw=0x{0:X8} mode={1} ok={2}' -f $finalRaw, ([int]($finalRaw -band 0xFFFF)), $result.restored_ok)
  } catch {
    Log "FINAL RESTORE FAILED: $($_.Exception.Message)"
  }
  $result.steps = $history
  New-Item -ItemType File -Path $doneFlag -Force | Out-Null
  if ($watchdog) {
    try { $null = $watchdog.WaitForExit(5000) } catch { }
  }
  [System.IO.File]::WriteAllText($jsonPath, ($result | ConvertTo-Json -Depth 5), $utf8)
  Log 'done'
}
