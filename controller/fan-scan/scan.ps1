#requires -Version 5.1
<#
  differential thermal-surface scan  -  READ ONLY

  Finds which readable surface tracks the cooling system, without writing to
  anything. No DEVS, no FANL, no EC store. Every call below is a read.

  What the first probe established (run-20261020-150607):
    - the EC is not reachable through WindowsEmbeddedControllerIO: 1 non-zero
      register out of 256, and a sweep costs ~27 s
    - ASUS ACPI WMI is reachable via instance ACPI\PNP0C14\ATK_0 when elevated
    - 75 of 82 DSTS device ids return 0xFFFFFFFE ("unsupported"); the rest are
      the real surface and are sampled densely

  Protocol: idle -> load -> cooldown, repeated. A fan register must
    1. move when load starts,
    2. move back when load stops,
    3. do it again on the next cycle.

  Usage (elevated):
    powershell -NoProfile -ExecutionPolicy Bypass -File scan.ps1 -Cycles 2
#>
param(
  [int]$Idle = 20,
  [int]$Load = 90,
  [int]$LoadMax = 200,
  [int]$HotTarget = 82,
  [int]$Cooldown = 60,
  [int]$Cycles = 2,
  [int]$Interval = 2,
  [string]$OutDir
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
if (-not $OutDir) { $OutDir = Join-Path $PSScriptRoot ('run-' + (Get-Date).ToString('yyyyMMdd-HHmmss')) }
New-Item -ItemType Directory -Path $OutDir -Force | Out-Null

$logPath   = Join-Path $OutDir 'scan.log'
$jsonlPath = Join-Path $OutDir 'samples.jsonl'
$sweepPath = Join-Path $OutDir 'sweeps.jsonl'
$preflight = Join-Path $OutDir 'preflight.json'
$metaPath  = Join-Path $OutDir 'meta.json'

# PS 5.1 Out-File and Encoding.UTF8 both emit a BOM. Write UTF-8 without one so
# every consumer can parse the files without a special case.
$utf8 = New-Object System.Text.UTF8Encoding($false)

function Log($m) {
  $line = '{0} {1}' -f (Get-Date).ToString('HH:mm:ss.fff'), $m
  Write-Host $line
  [System.IO.File]::AppendAllText($logPath, $line + "`r`n", $script:utf8)
}
function Json($o) { $o | ConvertTo-Json -Depth 6 -Compress }

$elevated = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
Log "elevated=$elevated  out=$OutDir"
if (-not $elevated) { Log 'REFUSING: hardware surfaces read as zero without elevation'; exit 2 }

# --------------------------------------------------------------------------
# MSR
# --------------------------------------------------------------------------
Add-Type -Path (Join-Path $root 'tools\lhm\LibreHardwareMonitorLib.dll')

$msr = $null; $tjMax = 100; $eexp = 14; $energyUnit = 1.0 / [math]::Pow(2, 14)
try {
  $msr = New-Object LibreHardwareMonitor.PawnIo.IntelMsr
  $tj = [uint64]0
  if ($msr.ReadMsr([uint32]0x1A2, [ref]$tj)) { $tjMax = [int](($tj -shr 16) -band 0xFF) }
  $unit = [uint64]0
  if ($msr.ReadMsr([uint32]0x606, [ref]$unit)) {
    $eexp = [int](($unit -shr 8) -band 0x1F)
    $energyUnit = 1.0 / [math]::Pow(2, $eexp)
  }
  Log "msr ok  tjMax=$tjMax  energyUnit=2^-$eexp"
} catch { Log "msr FAILED: $($_.Exception.Message)" }

function Read-MsrU64([uint32]$idx) {
  if (-not $msr) { return $null }
  $v = [uint64]0
  try { if ($msr.ReadMsr($idx, [ref]$v)) { return $v } } catch { }
  return $null
}

$cores = [int](Get-CimInstance Win32_Processor | Measure-Object NumberOfLogicalProcessors -Sum).Sum
if ($cores -le 0) { $cores = 20 }
$affType = [LibreHardwareMonitor.Hardware.GroupAffinity]
function Get-CoreTemps {
  $out = New-Object 'double[]' $cores
  for ($i = 0; $i -lt $cores; $i++) {
    $eax = [uint32]0; $edx = [uint32]0
    try {
      $ga = $affType::Single([uint16]0, $i)
      if ($msr -and $msr.ReadMsr([uint32]0x19C, [ref]$eax, [ref]$edx, $ga)) {
        $out[$i] = [double]($tjMax - (($eax -shr 16) -band 0x7F))
      } else { $out[$i] = [double]::NaN }
    } catch { $out[$i] = [double]::NaN }
  }
  return $out
}

# --------------------------------------------------------------------------
# EC (swept once, for the record; too slow to sample continuously)
# --------------------------------------------------------------------------
$ec = $null; $ecRead = $null
try {
  $ioType = [LibreHardwareMonitor.Hardware.Motherboard.Lpc.EC.WindowsEmbeddedControllerIO]
  $iface  = [LibreHardwareMonitor.Hardware.Motherboard.Lpc.EC.IEmbeddedControllerIO]
  $ecRead = $iface.GetMethod('Read')
  $ec = New-Object $ioType
  Log 'ec reader constructed'
} catch { Log "ec FAILED: $($_.Exception.Message)" }

function Read-Ec {
  $h = [ordered]@{}
  if (-not $ec) { return $h }
  for ($b = 0; $b -lt 256; $b += 16) {
    $regs = [uint16[]]::new(16); $data = [byte[]]::new(16)
    for ($i = 0; $i -lt 16; $i++) { $regs[$i] = [uint16]($b + $i) }
    try {
      $null = $ecRead.Invoke($ec, @($regs, $data))
      for ($i = 0; $i -lt 16; $i++) { $h[('0x{0:X2}' -f ($b + $i))] = [int]$data[$i] }
    } catch {
      for ($i = 0; $i -lt 16; $i++) { $h[('0x{0:X2}' -f ($b + $i))] = $null }
    }
  }
  return $h
}

# --------------------------------------------------------------------------
# ASUS ACPI WMI
# --------------------------------------------------------------------------
$asus = $null; $asusKind = 'none'; $asusErr = @()

function Resolve-Asus {
  foreach ($n in @('ACPI\PNP0C14\ATK_0','ACPI\PNP0C14\ATK_1','ACPI\PNP0C14\ATK')) {
    $p = 'root\wmi:AsusAtkWmi_WMNB.InstanceName="{0}"' -f $n.Replace('\','\\')
    try {
      $o = [wmi]$p
      $in = $o.PSBase.GetMethodParameters('SPEC')
      $in.Get_specification_or_model_type = [uint32]0
      $null = $o.PSBase.InvokeMethod('SPEC', $in, $null)
      $script:asus = $o; $script:asusKind = $n
      Log "asus wmi ok: $n"
      return
    } catch { $script:asusErr += "${n}: $($_.Exception.Message)" }
  }
}

function Get-Dsts([uint32]$id) {
  if (-not $script:asus) { return $null }
  try {
    $in = $script:asus.PSBase.GetMethodParameters('DSTS')
    $in.Device_ID = $id
    $o = $script:asus.PSBase.InvokeMethod('DSTS', $in, $null)
    $v = [int64]$o['device_status']
    if ($v -eq 4294967294) { return $null }   # 0xFFFFFFFE: id not implemented
    return $v
  } catch { return $null }
}

Resolve-Asus

$wmiIds = @()
$i = 0x00110000; while ($i -le 0x00110040) { $wmiIds += $i; $i++ }
$i = 0x00120070; while ($i -le 0x00120080) { $wmiIds += $i; $i++ }

function Wmi-Sweep {
  $h = [ordered]@{}
  foreach ($id in $wmiIds) { $h[('0x{0:X8}' -f $id)] = Get-Dsts $id }
  return $h
}

# --------------------------------------------------------------------------
# preflight: full WMI sweep, one EC sweep, one timing sample
# --------------------------------------------------------------------------
Log 'preflight: wmi sweep'
$swW = [Diagnostics.Stopwatch]::StartNew()
$wmiAll = Wmi-Sweep
$swW.Stop()
$supported = @($wmiAll.Keys | Where-Object { $null -ne $wmiAll[$_] })
Log ("wmi: {0} supported of {1} in {2:N0} ms" -f $supported.Count, $wmiIds.Count, $swW.Elapsed.TotalMilliseconds)

Log 'preflight: ec sweep (slow, once)'
$swE = [Diagnostics.Stopwatch]::StartNew()
$ecAll = Read-Ec
$swE.Stop()
$ecNonZero = @($ecAll.Keys | Where-Object { $ecAll[$_] -ne 0 -and $null -ne $ecAll[$_] })
Log ("ec: {0} non-zero of 256 in {1:N0} ms" -f $ecNonZero.Count, $swE.Elapsed.TotalMilliseconds)

$script:wmiShort = @($supported | ForEach-Object { [Convert]::ToUInt32($_.Substring(2), 16) })
Log ("sampling {0} live wmi ids: {1}" -f $script:wmiShort.Count, (($script:wmiShort | ForEach-Object { '0x{0:X8}' -f $_ }) -join ' '))

$pf = [ordered]@{
  elevated = $elevated; cores = $cores; tjMax = $tjMax
  msr = ($null -ne $msr); ec = ($null -ne $ec); asus_kind = $asusKind; asus_errors = $asusErr
  battery = $null; ac = $null
  wmi_ids = $wmiIds.Count
  wmi_supported = $supported
  wmi_values = $wmiAll
  wmi_sweep_ms = [math]::Round($swW.Elapsed.TotalMilliseconds, 1)
  ec_nonzero = $ecNonZero
  ec_values = $ecAll
  ec_sweep_ms = [math]::Round($swE.Elapsed.TotalMilliseconds, 1)
  win32_fan = @(); thermal_zones = @()
}
try {
  $b = Get-CimInstance Win32_Battery | Select-Object -First 1
  if ($b) { $pf.battery = $b.EstimatedChargeRemaining; $pf.ac = ($b.BatteryStatus -eq 2) }
} catch { }
try { $pf.win32_fan = @(Get-CimInstance Win32_Fan -ErrorAction SilentlyContinue | Select-Object Name, ActiveCooling, DesiredSpeed) } catch { }
try {
  $pf.dptf_classes = @(Get-CimClass -Namespace root\wmi -ErrorAction SilentlyContinue |
    Where-Object { $_.CimClassName -match 'DPTF|Dynamic.*Thermal' } | ForEach-Object { $_.CimClassName })
} catch { }
try {
  $pf.dptf_devices = @(Get-PnpDevice -ErrorAction SilentlyContinue |
    Where-Object { $_.FriendlyName -match 'Dynamic.*Thermal|DPTF|Dynamic Tuning' } |
    ForEach-Object { '{0} {1}' -f $_.Status, $_.FriendlyName })
} catch { }
try {
  $pf.thermal_zones = @(Get-CimInstance -Namespace root\wmi -ClassName MSAcpi_ThermalZoneTemperature -ErrorAction SilentlyContinue |
    ForEach-Object { [math]::Round(($_.CurrentTemperature / 10.0) - 273.15, 1) })
} catch { }

[System.IO.File]::WriteAllText($preflight, ($pf | ConvertTo-Json -Depth 6), $utf8)

# --------------------------------------------------------------------------
# sampler
# --------------------------------------------------------------------------
$state = @{ lastEnergy = $null; lastT = $null }

function Sample([double]$t, [string]$phase, [int]$cycle) {
  $sw = [Diagnostics.Stopwatch]::StartNew()
  $row = [ordered]@{ t = [math]::Round($t, 2); phase = $phase; cycle = $cycle }

  $swM = [Diagnostics.Stopwatch]::StartNew()
  $temps = Get-CoreTemps
  $valid = @($temps | Where-Object { -not [double]::IsNaN($_) })
  if ($valid.Count -gt 0) {
    $row['t_max']  = [math]::Round(($valid | Measure-Object -Maximum).Maximum, 1)
    $row['t_mean'] = [math]::Round(($valid | Measure-Object -Average).Average, 1)
  } else { $row['t_max'] = $null; $row['t_mean'] = $null }

  # measured while the load is running, not after it is killed
  try { $row['cpu_load'] = [int](Get-CimInstance Win32_Processor | Measure-Object LoadPercentage -Average).Average }
  catch { $row['cpu_load'] = $null }

  $e = Read-MsrU64 0x611
  if ($null -ne $e) { $e = $e -band 0xFFFFFFFF }        # RAPL is a 32-bit counter
  if ($null -ne $e -and $null -ne $state.lastEnergy -and $null -ne $state.lastT -and $t -gt $state.lastT) {
    $delta = $e - $state.lastEnergy
    if ($delta -lt 0) { $delta += [math]::Pow(2, 32) }
    $row['pkg_w'] = [math]::Round(($delta * $energyUnit) / ($t - $state.lastT), 2)
  } else { $row['pkg_w'] = $null }
  $state.lastEnergy = $e; $state.lastT = $t
  $swM.Stop()

  $swW = [Diagnostics.Stopwatch]::StartNew()
  foreach ($id in $script:wmiShort) { $row[('wmi_{0:x8}' -f $id)] = Get-Dsts $id }
  $swW.Stop()

  $row['msr_ms'] = [math]::Round($swM.Elapsed.TotalMilliseconds, 1)
  $row['wmi_ms'] = [math]::Round($swW.Elapsed.TotalMilliseconds, 1)
  $row['sample_ms'] = [math]::Round($sw.Elapsed.TotalMilliseconds, 1)
  return $row
}

# --------------------------------------------------------------------------
# run
# --------------------------------------------------------------------------
$meta = [ordered]@{
  started = (Get-Date).ToString('o')
  params = @{ idle = $Idle; load = $Load; cooldown = $Cooldown; cycles = $Cycles; interval = $Interval }
  bios = (Get-CimInstance Win32_BIOS).SMBIOSBIOSVersion
  model = (Get-CimInstance Win32_ComputerSystem).Model
  load_observed = @()
}

$pausedByUs = $false
try {
  & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root 'profile.ps1') -Mode stock | Out-Null
  $pausedByUs = $true
  Log 'governor paused, stock scheme active'
} catch { Log "could not pause governor: $($_.Exception.Message)" }

$clock = [Diagnostics.Stopwatch]::StartNew()
$child = $null

try {
  for ($c = 1; $c -le $Cycles; $c++) {
    foreach ($ph in @(@('idle', $Idle), @('load', $Load), @('cooldown', $Cooldown))) {
      $name = $ph[0]; $dur = [int]$ph[1]
      Log "cycle $c phase $name ${dur}s"

      if ($name -eq 'load') {
        $child = Start-Process -FilePath 'powershell.exe' -PassThru -WindowStyle Hidden `
          -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',(Join-Path $root 'load.ps1'),
                          '-Seconds', "$($LoadMax + 20)", '-Threads', '20')
      }

      $phaseStart = $clock.Elapsed.TotalSeconds
      $end = $phaseStart + $dur
      $hardEnd = $end
      if ($name -eq 'load') { $hardEnd = $phaseStart + $LoadMax }

      $peakT = $null
      $peakLoad = $null
      while ($clock.Elapsed.TotalSeconds -lt $hardEnd) {
        $t0 = $clock.Elapsed.TotalSeconds
        $row = Sample $t0 $name $c
        [System.IO.File]::AppendAllText($jsonlPath, (Json $row) + "`n", $script:utf8)
        if ($null -ne $row.t_max) { if ($null -eq $peakT -or $row.t_max -gt $peakT) { $peakT = $row.t_max } }
        if ($null -ne $row.cpu_load) { if ($null -eq $peakLoad -or $row.cpu_load -gt $peakLoad) { $peakLoad = $row.cpu_load } }

        # Adaptive load: keep heating past the nominal duration until the fan
        # threshold is crossed, so a hot run is guaranteed rather than hoped for.
        if ($name -eq 'load' -and $clock.Elapsed.TotalSeconds -ge $end -and
            $null -ne $peakT -and $peakT -ge $HotTarget) { break }

        $spent = $clock.Elapsed.TotalSeconds - $t0
        $sleepMs = [int](($Interval * 1000) - ($spent * 1000))
        if ($sleepMs -lt 100) { $sleepMs = 100 }
        Start-Sleep -Milliseconds $sleepMs
      }

      if ($name -eq 'load') {
        if ($child) { try { if (-not $child.HasExited) { Stop-Process -Id $child.Id -Force } } catch { }; $child = $null }
        $meta.load_observed += $peakLoad
        Log ("load phase: peak cpu={0}%  peak t_max={1}C  held {2}s" -f $peakLoad, $peakT,
             [math]::Round($clock.Elapsed.TotalSeconds - $phaseStart, 1))
      }

      # full sweep at every phase boundary: catches an id that only reports
      # under load, which a shortlist built at idle would miss
      $swp = [ordered]@{ t = [math]::Round($clock.Elapsed.TotalSeconds, 2); phase = $name; cycle = $c; wmi = (Wmi-Sweep) }
      [System.IO.File]::AppendAllText($sweepPath, (Json $swp) + "`n", $script:utf8)
      Log "sweep after ${name}: $(@($swp.wmi.Keys | Where-Object { $null -ne $swp.wmi[$_] }).Count) supported"
    }
  }
} finally {
  if ($child) { try { Stop-Process -Id $child.Id -Force } catch { } }
  if ($pausedByUs) {
    try {
      & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root 'profile.ps1') -Mode resume | Out-Null
      Log 'governor resumed'
    } catch { Log "resume FAILED: $($_.Exception.Message)" }
  }
  if ($ec) { try { $ec.Dispose() } catch { } }
  if ($msr) { try { $msr.Close() } catch { } }
  $meta.finished = (Get-Date).ToString('o')
  [System.IO.File]::WriteAllText($metaPath, ($meta | ConvertTo-Json -Depth 6), $utf8)
  Log 'done'
}
