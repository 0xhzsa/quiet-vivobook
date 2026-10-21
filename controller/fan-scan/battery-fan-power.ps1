#requires -Version 5.1
<#
  battery-fan-power.ps1 - measure what the fan is actually costing.

  This machine has no fan telemetry: no tachometer, no EC fan register, no
  Pwm. What it DOES have, while it is running on battery, is a battery
  discharge rate - and that is a meter for the WHOLE machine.

      system power  =  Win32_BatteryStatus.DischargeRate  (mW, DC side)
      package power =  MSR 0x611                        (W, CPU package)
      everything else = system - package

  "Everything else" is the fan plus the VRM, the display, the chipset and
  the loss in the DC converter. The VRM and chipset draw is roughly constant
  and the display is constant, so the DIFFERENCE between two thermal modes at
  the same workload is the fan.

  That is the measurement this project has been missing on its own hardware:
  not a fan RPM, not an acoustic number, but watts.

  WHY BATTERY, NOT AC: on AC the adapter's input is not exposed, so there is
  no system-power meter. On battery the BMC publishes the discharge rate. The
  cost is that the CPU is power-limited on battery, so the absolute numbers
  are not the AC numbers - but the comparison between modes is still valid,
  because both modes run under the same battery power envelope.

  The run is A/B/A so a drifting baseline invalidates itself rather than
  producing a number. Every phase reads the mode back, and the phase is
  marked invalid if the mode drifted.

  Output: summary.json, samples.jsonl, fanpower.log
#>
[CmdletBinding(PositionalBinding = $false)]
param(
  [int]$LoadSec = 75,
  [int]$SteadySec = 45,
  [int]$CooldownSec = 60,
  [double]$CooldownTargetC = 60.0,
  [int]$CooldownMaxSec = 240,
  [int]$Interval = 3,
  [int]$Threads = 8,
  [string]$Modes = '0,1,2,0',
  [uint32]$DeviceId = 0x00110019,
  [double]$AbortTempC = 95.0,
  [string]$OutDir
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
if (-not $OutDir) { $OutDir = Join-Path $PSScriptRoot ('batteryfan-' + (Get-Date).ToString('yyyyMMdd-HHmmss')) }
New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
$OutDir = (Resolve-Path -LiteralPath $OutDir).Path

$logPath = Join-Path $OutDir 'fanpower.log'
$jsonlPath = Join-Path $OutDir 'samples.jsonl'
$summaryPath = Join-Path $OutDir 'summary.json'
$utf8 = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($logPath, '', $utf8)
[System.IO.File]::WriteAllText($jsonlPath, '', $utf8)

function Log($m) {
  $line = '{0} {1}' -f (Get-Date).ToString('HH:mm:ss.fff'), $m
  Write-Host $line
  [System.IO.File]::AppendAllText($logPath, $line + "`r`n", $utf8)
}

$elevated = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $elevated) { Write-Host 'REFUSING: needs elevation (MSR reads)'; exit 2 }

# The mode list is a string so a comma list cannot bind positionally to
# DeviceId or AbortTempC.
$modeList = @(
  $Modes -split '[,\s]+' | Where-Object { $_ -ne '' } | ForEach-Object {
    $p = 0
    if (-not [int]::TryParse($_, [ref]$p)) { throw "invalid mode token: $_" }
    if ($p -lt 0 -or $p -gt 2) { throw "mode out of range: $p" }
    $p
  }
)
if ($modeList.Count -lt 2) { throw 'need at least two modes' }

# --- power state ---------------------------------------------------------
$bat = Get-CimInstance -Namespace root\wmi -ClassName BatteryStatus -ErrorAction Stop | Select-Object -First 1
if ($bat.PowerOnline) { throw 'This script needs the machine ON BATTERY: on AC there is no system-power meter. Unplug the charger and re-run.' }
Log ("battery: powerOnline={0} discharging={1} rate={2} mW voltage={3} mV" -f $bat.PowerOnline, $bat.Discharging, $bat.DischargeRate, $bat.Voltage)

# --- ASUS thermal policy --------------------------------------------------
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
function Set-Mode([int]$m) {
  for ($try = 1; $try -le 3; $try++) {
    $r = Set-Devs $DeviceId ([uint32]$m)
    Start-Sleep -Milliseconds 200
    $raw = Get-Dsts $DeviceId
    $applied = [int]($raw -band 0xFFFF)
    Log ('mode {0}: try {1} write={2} readback=0x{3:X8} applied={4}' -f $m, $try, $r, $raw, $applied)
    if ($applied -eq $m) { return $applied }
    Start-Sleep -Milliseconds 300
  }
  throw "mode $m did not stick"
}

# --- MSR ------------------------------------------------------------------
# Add-Type -Path fails on this assembly with "Unable to load one or more of
# the requested types" (it tries to resolve every type in the DLL, including
# ones whose dependencies are missing). The types we need load fine, so the
# assembly is loaded directly and the failure is non-fatal.
$dllPath = Join-Path $root 'tools\lhm\LibreHardwareMonitorLib.dll'
try { Add-Type -Path $dllPath -ErrorAction Stop } catch {
  Log "Add-Type -Path failed (non-fatal): $($_.Exception.Message)"
}
if (-not ('LibreHardwareMonitor.PawnIo.IntelMsr' -as [type])) {
  [void][System.Reflection.Assembly]::LoadFrom($dllPath)
}
if (-not ('LibreHardwareMonitor.Hardware.GroupAffinity' -as [type])) {
  [void][System.Reflection.Assembly]::LoadFrom($dllPath)
}
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
function Get-SystemW {
  try {
    $b = Get-CimInstance -Namespace root\wmi -ClassName BatteryStatus -ErrorAction Stop | Select-Object -First 1
    if ($b.PowerOnline) { return $null }
    if (-not $b.Discharging) { return $null }
    return [double]($b.DischargeRate / 1000.0)
  } catch { return $null }
}

# --- load -----------------------------------------------------------------
$loadSrc = @'
using System;
using System.Threading;
public static class FanLoad {
    public static volatile bool Stop;
    public static long Counter;
    static Thread[] ts;
    public static void Start(int n) {
        if (Alive() != 0) throw new InvalidOperationException("load already running");
        Stop = false; Counter = 0; ts = new Thread[n];
        for (int i = 0; i < n; i++) {
            int seed = i;
            ts[i] = new Thread(() => {
                double x = 1.0 + seed * 0.001, y = 0.5;
                while (!Stop) {
                    for (int k = 0; k < 2000; k++) {
                        x = x * 1.0000001 + 1.234567;
                        y = y * 0.9999999 - 0.7654321;
                        if (x > 1e9) x -= 1e9;
                        if (y < -1e9) y += 1e9;
                    }
                    Interlocked.Increment(ref Counter);
                }
            });
            ts[i].IsBackground = true; ts[i].Priority = ThreadPriority.Highest; ts[i].Start();
        }
    }
    public static bool WaitStop(int ms) {
        Stop = true;
        DateTime until = DateTime.UtcNow.AddMilliseconds(ms);
        while (DateTime.UtcNow < until) { if (Alive() == 0) return true; Thread.Sleep(20); }
        return Alive() == 0;
    }
    public static int Alive() {
        int n = 0;
        if (ts != null) foreach (Thread t in ts) if (t != null && t.IsAlive) n++;
        return n;
    }
}
'@
if (-not ('FanLoad' -as [type])) { Add-Type -TypeDefinition $loadSrc -Language CSharp }
try { [System.Diagnostics.Process]::GetCurrentProcess().PriorityClass = 'High' } catch { }

$baselineRaw = Get-Dsts $DeviceId
$baselineMode = [int]($baselineRaw -band 0xFFFF)
Log ("baseline raw=0x{0:X8} mode={1} cores={2} tjmax={3}" -f $baselineRaw, $baselineMode, $cores, $tjMax)

$script:clock = [Diagnostics.Stopwatch]::StartNew()
$script:lastEnergy = $null
$script:lastT = $null

function Invoke-Phase {
  param([int]$Seconds, [int]$Mode, [string]$Label)
  $rows = @()
  $invalid = $null
  $stall = 0
  $prevIter = $null
  $prevIterT = $null
  $nullT = 0
  $modeDrift = 0
  $startT = $script:clock.Elapsed.TotalSeconds
  $end = $startT + $Seconds

  while ($script:clock.Elapsed.TotalSeconds -lt $end) {
    $t0 = $script:clock.Elapsed.TotalSeconds
    $temps = Get-CoreTemps
    $valid = @($temps | Where-Object { -not [double]::IsNaN($_) })
    $tmax = if ($valid.Count -gt 0) { [math]::Round(($valid | Measure-Object -Maximum).Maximum, 1) } else { $null }
    if ($null -eq $tmax) { $nullT++ }

    $e = Read-Msr32 0x611
    $pkg = $null
    if ($null -ne $e -and $null -ne $script:lastEnergy -and $null -ne $script:lastT -and $t0 -gt $script:lastT) {
      $delta = $e - $script:lastEnergy
      if ($delta -lt 0) { $delta += [math]::Pow(2, 32) }
      $pkg = [math]::Round(($delta * $energyUnit) / ($t0 - $script:lastT), 2)
    }
    $script:lastEnergy = $e
    $script:lastT = $t0

    $sys = Get-SystemW

    $iter = [FanLoad]::Counter
    if ($null -ne $prevIter -and $iter -le $prevIter) { $stall++ } else { $stall = 0 }
    $prevIter = $iter
    $prevIterT = $t0

    $modeNow = $null
    try { $modeNow = [int]((Get-Dsts $DeviceId) -band 0xFFFF) } catch { }
    if ($null -ne $modeNow -and $modeNow -ne $Mode) { $modeDrift++ } else { $modeDrift = 0 }

    $row = [ordered]@{
      t = [math]::Round($t0, 2); label = $Label; mode = $Mode; mode_now = $modeNow
      t_max = $tmax; pkg_w = $pkg; sys_w = $sys
      iter = $iter; alive_threads = [FanLoad]::Alive()
    }
    [System.IO.File]::AppendAllText($jsonlPath, ($row | ConvertTo-Json -Compress) + "`n", $utf8)
    $rows += $row

    if ($stall -ge 3) { $invalid = 'work counter stalled'; Log "INVALID: $Label $invalid"; break }
    if ($modeDrift -ge 2) { $invalid = "mode drifted to $modeNow"; Log "INVALID: $Label $invalid"; break }
    if ($null -ne $tmax -and $tmax -ge $AbortTempC) { $invalid = "hot: $tmax C"; Log "ABORT: $Label $invalid"; break }

    $spent = $script:clock.Elapsed.TotalSeconds - $t0
    $sleepMs = [int](($Interval * 1000) - ($spent * 1000))
    if ($sleepMs -lt 100) { $sleepMs = 100 }
    Start-Sleep -Milliseconds $sleepMs
  }

  $endT = $script:clock.Elapsed.TotalSeconds
  $cut = $startT + [math]::Max(0, $Seconds - $SteadySec)
  $steady = @($rows | Where-Object { $null -ne $_.t_max -and $_.t -ge $cut })
  $stw = @($steady | Where-Object { $null -ne $_.sys_w } | ForEach-Object { $_.sys_w })
  $stp = @($steady | Where-Object { $null -ne $_.pkg_w } | ForEach-Object { $_.pkg_w })
  $stt = @($steady | Where-Object { $null -ne $_.t_max } | ForEach-Object { $_.t_max })
  $workRate = $null
  if ($steady.Count -ge 2) {
    $f = $steady[0]; $l = $steady[-1]
    if ($l.t -gt $f.t) { $workRate = [math]::Round(($l.iter - $f.iter) / ($l.t - $f.t), 1) }
  }
  if (-not $invalid -and $nullT -gt 0) { $invalid = "null temperatures in $nullT samples" }
  if (-not $invalid -and $steady.Count -lt 3) { $invalid = "steady window has $($steady.Count) samples" }
  if (-not $invalid -and $stw.Count -lt 3) { $invalid = "no system-power samples" }

  $sysAvg = if ($stw.Count) { [math]::Round(($stw | Measure-Object -Average).Average, 2) } else { $null }
  $pkgAvg = if ($stp.Count) { [math]::Round(($stp | Measure-Object -Average).Average, 2) } else { $null }
  $other = if ($null -ne $sysAvg -and $null -ne $pkgAvg) { [math]::Round($sysAvg - $pkgAvg, 2) } else { $null }
  $tAvg = if ($stt.Count) { [math]::Round(($stt | Measure-Object -Average).Average, 2) } else { $null }

  Log ('{0}: mode={1} sys={2}W pkg={3}W other={4}W temp={5}C work/s={6} invalid={7}' -f `
      $Label, $Mode, $sysAvg, $pkgAvg, $other, $tAvg, $workRate, $invalid)

  return [ordered]@{
    label = $Label; mode = $Mode
    sys_w = $sysAvg; pkg_w = $pkgAvg; other_w = $other
    temp_c = $tAvg; work_per_s = $workRate
    steady_samples = $steady.Count; invalid = $invalid
  }
}

function Wait-Cooldown {
  # Each phase must start from the same die temperature, or the fan starts at
  # a different speed and the steady windows are not comparable.
  param([double]$TargetC, [int]$MaxSec)
  $started = Get-Date
  $tmax = $null
  while (((Get-Date) - $started).TotalSeconds -lt $MaxSec) {
    $temps = Get-CoreTemps
    $valid = @($temps | Where-Object { -not [double]::IsNaN($_) })
    if ($valid.Count -gt 0) {
      $tmax = [math]::Round(($valid | Measure-Object -Maximum).Maximum, 1)
      if ($tmax -le $TargetC) { break }
    }
    Start-Sleep -Seconds 3
  }
  return [ordered]@{ ok = ($null -ne $tmax -and $tmax -le $TargetC); t = $tmax; sec = [math]::Round(((Get-Date) - $started).TotalSeconds, 1) }
}

$summary = [ordered]@{
  baseline_mode = $baselineMode
  baseline_raw = $baselineRaw
  threads = $Threads
  load_sec = $LoadSec
  steady_sec = $SteadySec
  cooldown_target_c = $CooldownTargetC
  modes = $modeList
  phases = @()
  cooldowns = @()
  restored_ok = $false
  aborted = $null
}
$failed = $null
try {
  foreach ($m in $modeList) {
    Set-Mode $m | Out-Null
    $cd = Wait-Cooldown -TargetC $CooldownTargetC -MaxSec $CooldownMaxSec
    $summary.cooldowns += $cd
    Log ("cooldown: ok={0} t={1}C sec={2}" -f $cd.ok, $cd.t, $cd.sec)
    # A cooldown that times out is not fatal: the A/B/A/B design lets the
    # data show whether the phases started comparably. What IS fatal is a
    # phase that runs invalid.
    if (-not $cd.ok) { Log "WARN: cooldown target not reached, continuing" }
    [FanLoad]::Start($Threads)
    $res = Invoke-Phase -Seconds $LoadSec -Mode $m -Label ("m{0}" -f $m)
    if (-not [FanLoad]::WaitStop(5000)) { throw 'load threads did not exit' }
    $summary.phases += $res
    if ($res.invalid) { throw "phase $($res.label) invalid: $($res.invalid)" }
  }
} catch {
  $failed = $_.Exception.Message
  Log "ERROR: $failed"
} finally {
  try { if (-not [FanLoad]::WaitStop(5000)) { Log 'STOP: threads still alive' } } catch { }
  try {
    $null = Set-Devs $DeviceId ([uint32]$baselineRaw)
    $finalRaw = Get-Dsts $DeviceId
    $summary.restored_raw = $finalRaw
    $summary.restored_ok = ([int64]$finalRaw -eq [int64]$baselineRaw)
    Log ('restored raw=0x{0:X8} ok={1}' -f $finalRaw, $summary.restored_ok)
  } catch { Log "RESTORE FAILED: $($_.Exception.Message)" }
  if ($msr) { try { $msr.Close() } catch { } }
  $summary.aborted = $failed
  $summary.finished = (Get-Date).ToString('o')
  [System.IO.File]::WriteAllText($summaryPath, ($summary | ConvertTo-Json -Depth 6), $utf8)
  Log 'done'
}
if ($failed) { exit 1 }
exit 0
