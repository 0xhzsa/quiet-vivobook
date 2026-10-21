#requires -Version 5.1
<#
  set-thermal-mode.ps1 - set the ASUS thermal policy and watch it settle.

  This is the quiet lever: 0 = balanced, 1 = silent, 2 = overboost (VIVO).
  It writes once, verifies by read-back, and then samples temperature and
  package power for ObserveSec so the effect is recorded rather than assumed.
#>
param(
  [ValidateSet(0, 1, 2)][int]$Mode = 1,
  [uint32]$DeviceId = 0x00110019,
  [int]$ObserveSec = 90,
  [string]$OutDir
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
if (-not $OutDir) { $OutDir = Join-Path $PSScriptRoot ('setmode-' + (Get-Date).ToString('yyyyMMdd-HHmmss')) }
New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
$logPath = Join-Path $OutDir 'setmode.log'
$jsonlPath = Join-Path $OutDir 'samples.jsonl'
$summaryPath = Join-Path $OutDir 'summary.json'
$utf8 = New-Object System.Text.UTF8Encoding($false)

function Log($m) {
  $line = '{0} {1}' -f (Get-Date).ToString('HH:mm:ss.fff'), $m
  Write-Host $line
  [System.IO.File]::AppendAllText($logPath, $line + "`r`n", $utf8)
}

$elevated = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $elevated) { Log 'REFUSING: needs elevation'; exit 2 }

$path = 'root\wmi:AsusAtkWmi_WMNB.InstanceName="{0}"' -f 'ACPI\PNP0C14\ATK_0'.Replace('\', '\\')
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

$baselineRaw = Get-Dsts $DeviceId
$baseline = [int]($baselineRaw -band 0xFFFF)
Log ('baseline raw=0x{0:X8} mode={1} -> requesting {2}' -f $baselineRaw, $baseline, $Mode)

$r = Set-Devs $DeviceId ([uint32]$Mode)
$raw = Get-Dsts $DeviceId
$applied = [int]($raw -band 0xFFFF)
Log ('write result={0} readback=0x{1:X8} applied={2}' -f $r, $raw, $applied)

if ($applied -ne $Mode) {
  Log 'write did not stick, restoring baseline'
  $null = Set-Devs $DeviceId ([uint32]$baseline)
  exit 1
}

# ---- observe --------------------------------------------------------------
Add-Type -Path (Join-Path $root 'tools\lhm\LibreHardwareMonitorLib.dll')
$msr = New-Object LibreHardwareMonitor.PawnIo.IntelMsr
$tj = [uint64]0
$tjMax = 100
if ($msr.ReadMsr([uint32]0x1A2, [ref]$tj)) { $tjMax = [int](($tj -shr 16) -band 0xFF) }
$unit = [uint64]0
$eexp = 14
if ($msr.ReadMsr([uint32]0x606, [ref]$unit)) { $eexp = [int](($unit -shr 8) -band 0x1F) }
$energyUnit = 1.0 / [math]::Pow(2, $eexp)
$cores = [int](Get-CimInstance Win32_Processor | Measure-Object NumberOfLogicalProcessors -Sum).Sum
if ($cores -le 0) { $cores = 20 }
$affType = [LibreHardwareMonitor.Hardware.GroupAffinity]

function Get-CoreTemps {
  $out = New-Object 'double[]' $cores
  for ($i = 0; $i -lt $cores; $i++) {
    $eax = [uint32]0; $edx = [uint32]0
    try {
      $ga = $affType::Single([uint16]0, $i)
      if ($msr.ReadMsr([uint32]0x19C, [ref]$eax, [ref]$edx, $ga)) {
        $out[$i] = [double]($tjMax - (($eax -shr 16) -band 0x7F))
      } else { $out[$i] = [double]::NaN }
    } catch { $out[$i] = [double]::NaN }
  }
  return $out
}
function Read-Msr32([uint32]$idx) {
  $v = [uint64]0
  try { if ($msr.ReadMsr($idx, [ref]$v)) { return [uint64]([uint64]$v -band 0xFFFFFFFF) } } catch { }
  return $null
}

$rows = @()
$clock = [Diagnostics.Stopwatch]::StartNew()
$lastE = $null; $lastT = $null
$end = $ObserveSec
while ($clock.Elapsed.TotalSeconds -lt $end) {
  $t0 = $clock.Elapsed.TotalSeconds
  $temps = Get-CoreTemps
  $valid = @($temps | Where-Object { -not [double]::IsNaN($_) })
  $tmax = if ($valid.Count) { [math]::Round(($valid | Measure-Object -Maximum).Maximum, 1) } else { $null }
  $e = Read-Msr32 0x611
  $w = $null
  if ($null -ne $e -and $null -ne $lastE -and $t0 -gt $lastT) {
    $d = $e - $lastE
    if ($d -lt 0) { $d += [math]::Pow(2, 32) }
    $w = [math]::Round(($d * $energyUnit) / ($t0 - $lastT), 2)
  }
  $lastE = $e; $lastT = $t0
  $row = [ordered]@{ t = [math]::Round($t0, 2); t_max = $tmax; pkg_w = $w }
  [System.IO.File]::AppendAllText($jsonlPath, (($row | ConvertTo-Json -Compress)) + "`n", $utf8)
  $rows += $row
  Start-Sleep -Seconds 2
}

$tt = @($rows | Where-Object { $null -ne $_.t_max } | ForEach-Object { $_.t_max })
$ww = @($rows | Where-Object { $null -ne $_.pkg_w } | ForEach-Object { $_.pkg_w })
$first = @($tt | Select-Object -First 5)
$last = @($tt | Select-Object -Last 5)
$summary = [ordered]@{
  requested_mode = $Mode
  baseline_mode = $baseline
  applied_mode = $applied
  restore_at_end = $false
  observed_sec = $ObserveSec
  t_start = if ($first.Count) { [math]::Round(($first | Measure-Object -Average).Average, 1) } else { $null }
  t_end = if ($last.Count) { [math]::Round(($last | Measure-Object -Average).Average, 1) } else { $null }
  t_mean = if ($tt.Count) { [math]::Round(($tt | Measure-Object -Average).Average, 1) } else { $null }
  t_peak = if ($tt.Count) { ($tt | Measure-Object -Maximum).Maximum } else { $null }
  w_mean = if ($ww.Count) { [math]::Round(($ww | Measure-Object -Average).Average, 2) } else { $null }
  samples = $rows.Count
}
Log ('mode {0} applied; temp {1} -> {2} C, peak {3}, mean power {4} W' -f $Mode, $summary.t_start, $summary.t_end, $summary.t_peak, $summary.w_mean)
if ($msr) { try { $msr.Close() } catch { } }
[System.IO.File]::WriteAllText($summaryPath, ($summary | ConvertTo-Json -Depth 5), $utf8)
Log 'done'
