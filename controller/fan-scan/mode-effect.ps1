#requires -Version 5.1
<#
  mode-effect.ps1 (v3) - measure what the ASUS thermal policy actually does.

  v1 was invalid: it started the load as a hidden child, Windows applied EcoQoS
  and pinned it to the E-cores, and in two phases the child died early. The
  sampler had no way to tell a dead load from a hot one, so it reported idle
  temperatures as "silent mode".

  v2 fixed the measurement, not the story:
    - the load runs IN THIS PROCESS, on real threads, so nothing can throttle
      it away or kill it silently;
    - every sample reads a work counter; if the counter stops advancing the
      phase is marked invalid instead of being reported as data;
    - thread count is auto-tuned first so the phases sit in a band where the
      fan policy can actually make a difference (74-86 C in balanced mode).

  v3 adds the controls a repeated/randomized run needs:
    - a single string -Modes argument, parsed and validated before any write,
      so a comma list cannot bind positionally to DeviceId/AbortTempC;
    - the governor pause is verified, not assumed;
    - a failed mode read-back, mode drift, null temperature, or short steady
      window invalidates the phase instead of silently becoming data;
    - a cooldown gate holds each phase at the same starting temperature;
    - the watchdog restores the full raw baseline, and the parent restores it
      again after resuming the governor.

  Encoding on VIVO is NOT the generic ASUS one:
      0 = default/balanced   1 = SILENT   2 = OVERBOOST

  Output: samples.jsonl, summary.json, mode.log
#>
[CmdletBinding(PositionalBinding = $false)]
param(
  [int]$LoadSec = 100,
  [int]$WarmSec = 40,
  [int]$BetweenSec = 15,
  [int]$SteadySec = 50,
  [int]$Interval = 2,
  [int]$StartThreads = 6,
  [int]$MaxThreads = 16,
  [string]$Modes = '0,1,2,0',
  [uint32]$DeviceId = 0x00110019,
  [double]$AbortTempC = 95.0,
  [double]$TargetLow = 74.0,
  [double]$TargetHigh = 86.0,
  [double]$CooldownTargetC = 65.0,
  [int]$CooldownMaxSec = 240,
  [string]$OutDir
)

$modeList = @(
  $Modes -split '[,\s]+' |
    Where-Object { $_ -ne '' } |
    ForEach-Object {
      $parsed = 0
      if (-not [int]::TryParse($_, [ref]$parsed)) { throw "invalid mode token: $_" }
      if ($parsed -lt 0 -or $parsed -gt 2) { throw "mode out of range: $parsed" }
      $parsed
    }
)
if ($modeList.Count -lt 1) { throw 'Modes must contain at least one mode' }

$ErrorActionPreference = 'Stop'

$elevated = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $elevated) { Write-Host 'REFUSING: needs elevation'; exit 2 }

$root = Split-Path -Parent $PSScriptRoot
if (-not $OutDir) { $OutDir = Join-Path $PSScriptRoot ('mode-' + (Get-Date).ToString('yyyyMMdd-HHmmss')) }
New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
$OutDir = (Resolve-Path -LiteralPath $OutDir).Path

$logPath = Join-Path $OutDir 'mode.log'
$jsonlPath = Join-Path $OutDir 'samples.jsonl'
$summaryPath = Join-Path $OutDir 'summary.json'
$doneFlag = Join-Path $OutDir 'done.flag'
$utf8 = New-Object System.Text.UTF8Encoding($false)

Remove-Item -LiteralPath $doneFlag -ErrorAction SilentlyContinue
[System.IO.File]::WriteAllText($logPath, '', $utf8)
[System.IO.File]::WriteAllText($jsonlPath, '', $utf8)


function Log($m) {
  $line = '{0} {1}' -f (Get-Date).ToString('HH:mm:ss.fff'), $m
  Write-Host $line
  [System.IO.File]::AppendAllText($logPath, $line + "`r`n", $utf8)
}
function Json($o) { $o | ConvertTo-Json -Depth 6 -Compress }

$elevated = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $elevated) { Log 'REFUSING: needs elevation'; exit 2 }

# ---- in-process load -------------------------------------------------------
$loadSrc = @'
using System;
using System.Threading;

public static class LoadGen2 {
    public static volatile bool Stop;
    public static long Counter;
    static Thread[] ts;

    public static void Start(int n) {
        if (Alive() != 0) throw new InvalidOperationException("load threads already running");
        Stop = false;
        Counter = 0;
        ts = new Thread[n];
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
            ts[i].IsBackground = true;
            ts[i].Priority = ThreadPriority.Highest;
            ts[i].Start();
        }
    }
    public static void Halt() { Stop = true; }
    public static bool WaitStop(int ms) {
        Stop = true;
        DateTime until = DateTime.UtcNow.AddMilliseconds(ms);
        while (DateTime.UtcNow < until) {
            if (Alive() == 0) return true;
            Thread.Sleep(20);
        }
        return Alive() == 0;
    }
    public static int Alive() {
        int n = 0;
        if (ts != null) foreach (Thread t in ts) if (t != null && t.IsAlive) n++;
        return n;
    }
}
'@
if (-not ('LoadGen2' -as [type])) { Add-Type -TypeDefinition $loadSrc -Language CSharp }
try { [System.Diagnostics.Process]::GetCurrentProcess().PriorityClass = 'High' } catch { }

# ---- WMI ------------------------------------------------------------------
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

# ---- MSR ------------------------------------------------------------------
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
function Get-AmbientC {
  try {
    $z = Get-CimInstance -Namespace root\wmi -ClassName MSAcpi_ThermalZoneTemperature -ErrorAction Stop | Select-Object -First 1
    if ($z) { return [math]::Round(($z.CurrentTemperature / 10.0) - 273.15, 1) }
  } catch { }
  return $null
}

# ---- state ----------------------------------------------------------------
$baselineRaw = Get-Dsts $DeviceId
$baselineMode = [int]($baselineRaw -band 0xFFFF)
if ($baselineRaw -eq 0xFFFFFFFE -or $baselineMode -gt 2) {
  throw ('unsupported baseline id=0x{0:X8} value=0x{1:X8}; refusing to write' -f $DeviceId, $baselineRaw)
}
$ambient = Get-AmbientC
Log ('baseline raw=0x{0:X8} mode={1} ambient={2}C threads={3} tjmax={4}' -f $baselineRaw, $baselineMode, $ambient, $cores, $tjMax)

$watchdogSec = ($WarmSec * 3) + 60 + (($LoadSec + $Interval + 5) * $modeList.Count) + ($BetweenSec * [math]::Max(0, $modeList.Count - 1)) + (25 * $modeList.Count) + 300
$watchdog = Start-Process -FilePath 'powershell.exe' -PassThru -WindowStyle Hidden -ArgumentList @(
  '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', (Join-Path $PSScriptRoot 'devs-watchdog.ps1'),
  '-DeviceId', $DeviceId, '-RestoreValue', $baselineRaw,
  '-DoneFlag', ('"{0}"' -f $doneFlag), '-TimeoutSec', "$watchdogSec",
  '-Log', ('"{0}"' -f $logPath)
)
Log "watchdog started pid=$($watchdog.Id) timeout=${watchdogSec}s"

$paused = $false
try {
  & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root 'profile.ps1') -Mode stock | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "profile.ps1 -Mode stock exited $LASTEXITCODE" }
  if (-not (Test-Path (Join-Path $root 'paused.flag'))) { throw 'paused.flag was not created' }
  $paused = $true
  Log 'governor paused, stock scheme active'
} catch { throw "could not pause governor: $($_.Exception.Message)" }

$script:clock = [Diagnostics.Stopwatch]::StartNew()
$script:lastEnergy = $null
$script:lastT = $null

function Invoke-Phase {
  param([int]$Seconds, [int]$Mode, [string]$Label)
  $rows = @()
  $peak = 0.0
  $invalid = $null
  $stall = 0
  $modeDrift = 0
  $nullT = 0
  $prevIter = $null
  $prevIterT = $null
  $startT = $script:clock.Elapsed.TotalSeconds
  $end = $startT + $Seconds

  while ($script:clock.Elapsed.TotalSeconds -lt $end) {
    $t0 = $script:clock.Elapsed.TotalSeconds

    $temps = Get-CoreTemps
    $valid = @($temps | Where-Object { -not [double]::IsNaN($_) })
    $tmax = if ($valid.Count -gt 0) { [math]::Round(($valid | Measure-Object -Maximum).Maximum, 1) } else { $null }
    if ($null -eq $tmax) { $nullT++ }

    $e = Read-Msr32 0x611
    $watts = $null
    if ($null -ne $e -and $null -ne $script:lastEnergy -and $null -ne $script:lastT -and $t0 -gt $script:lastT) {
      $delta = $e - $script:lastEnergy
      if ($delta -lt 0) { $delta += [math]::Pow(2, 32) }
      $watts = [math]::Round(($delta * $energyUnit) / ($t0 - $script:lastT), 2)
    }
    $script:lastEnergy = $e
    $script:lastT = $t0

    $iter = [LoadGen2]::Counter
    $rate = $null
    if ($null -ne $prevIter -and $t0 -gt $prevIterT) { $rate = [math]::Round(($iter - $prevIter) / ($t0 - $prevIterT), 1) }
    if ($null -ne $prevIter -and $iter -le $prevIter) { $stall++ } else { $stall = 0 }
    $prevIter = $iter
    $prevIterT = $t0

    $modeNow = $null
    try { $modeNow = [int]((Get-Dsts $DeviceId) -band 0xFFFF) } catch { }
    if ($null -ne $modeNow -and $modeNow -ne $Mode) { $modeDrift++ } else { $modeDrift = 0 }

    $row = [ordered]@{
      t = [math]::Round($t0, 2); label = $Label; mode = $Mode; mode_now = $modeNow
      t_max = $tmax; pkg_w = $watts
      iter = $iter; iter_per_s = $rate
      alive_threads = [LoadGen2]::Alive()
    }
    [System.IO.File]::AppendAllText($jsonlPath, (Json $row) + "`n", $utf8)
    $rows += $row
    if ($null -ne $tmax -and $tmax -gt $peak) { $peak = $tmax }

    if ($stall -ge 3) { $invalid = 'work counter stalled - load not running'; Log "INVALID: $Label $invalid"; break }
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
  $stw = @($steady | Where-Object { $null -ne $_.pkg_w } | ForEach-Object { $_.pkg_w })
  $stt = @($steady | Where-Object { $null -ne $_.t_max } | ForEach-Object { $_.t_max })
  $workRate = $null
  if ($steady.Count -ge 2) {
    $first = $steady[0]
    $last = $steady[-1]
    if ($last.t -gt $first.t) { $workRate = [math]::Round(($last.iter - $first.iter) / ($last.t - $first.t), 1) }
  }
  if (-not $invalid -and $nullT -gt 0) { $invalid = "null temperatures in $nullT samples" }
  if (-not $invalid -and $steady.Count -lt 3) { $invalid = "steady window has $($steady.Count) samples" }

  return [ordered]@{
    label = $Label
    mode = $Mode
    seconds = [math]::Round($endT - $startT, 1)
    start_t = if ($rows.Count) { $rows[0].t_max } else { $null }
    peak_t = $peak
    steady_t = if ($stt.Count) { [math]::Round(($stt | Measure-Object -Average).Average, 2) } else { $null }
    steady_w = if ($stw.Count) { [math]::Round(($stw | Measure-Object -Average).Average, 2) } else { $null }
    steady_iter = $workRate
    samples = $rows.Count
    null_t = $nullT
    invalid = $invalid
  }
}

function Set-Mode([int]$m) {
  for ($attempt = 1; $attempt -le 3; $attempt++) {
    $r = Set-Devs $DeviceId ([uint32]$m)
    Start-Sleep -Milliseconds 150
    $raw = Get-Dsts $DeviceId
    $applied = [int]($raw -band 0xFFFF)
    Log ('mode {0}: attempt {1} write result={2} readback=0x{3:X8} applied={4}' -f $m, $attempt, $r, $raw, $applied)
    if ($applied -eq $m) { return $applied }
    Start-Sleep -Milliseconds 250
  }
  throw "mode $m did not stick after 3 attempts"
}

function Stop-Load {
  if (-not [LoadGen2]::WaitStop(5000)) { throw 'load threads did not exit within 5 s' }
}

function Wait-Cooldown {
  param([double]$TargetC, [int]$MaxSec)
  $started = Get-Date
  $tmax = $null
  while (((Get-Date) - $started).TotalSeconds -lt $MaxSec) {
    $temps = Get-CoreTemps
    $valid = @($temps | Where-Object { -not [double]::IsNaN($_) })
    if ($valid.Count -gt 0) {
      $tmax = [math]::Round(($valid | Measure-Object -Maximum).Maximum, 1)
      if ($tmax -le $TargetC) {
        return [ordered]@{ ok = $true; t = $tmax; sec = [math]::Round(((Get-Date) - $started).TotalSeconds, 1) }
      }
    }
    Start-Sleep -Seconds 3
  }
  return [ordered]@{ ok = $false; t = $tmax; sec = [math]::Round(((Get-Date) - $started).TotalSeconds, 1) }
}

$battery = Get-CimInstance Win32_Battery -ErrorAction SilentlyContinue | Select-Object -First 1
$acOnline = $false
$charge = $null
if ($battery) {
  $charge = $battery.EstimatedChargeRemaining
  $acOnline = ($battery.BatteryStatus -eq 2 -or $battery.BatteryStatus -eq 6 -or $battery.BatteryStatus -eq 7 -or $battery.BatteryStatus -eq 8)
}
if (-not $acOnline) { throw 'AC power is required; refusing to run on battery' }

$summary = [ordered]@{
  baseline_mode = $baselineMode
  baseline_raw = $baselineRaw
  ambient_c = $ambient
  logical_processors = $cores
  thread_count = $null
  modes = $modeList
  load_sec = $LoadSec
  steady_sec = $SteadySec
  interval_sec = $Interval
  cooldown_target_c = $CooldownTargetC
  cooldown_max_sec = $CooldownMaxSec
  ac_online = $acOnline
  battery_charge_pct = $charge
  warmup = @()
  cooldowns = @()
  phases = @()
  restored_ok = $false
  aborted = $null
}

$threads = $StartThreads
$failed = $null

try {
  Set-Mode 0 | Out-Null

  # ---- warmup: pick a load that leaves the fan policy room to matter -------
  for ($attempt = 1; $attempt -le 3; $attempt++) {
    Log "warmup $attempt with $threads threads for ${WarmSec}s"
    [LoadGen2]::Start($threads)
    $w = Invoke-Phase -Seconds $WarmSec -Mode 0 -Label "warm$attempt"
    Stop-Load
    $steadyT = if ($null -ne $w.steady_t) { [math]::Round($w.steady_t, 1) } else { 0 }
    $summary.warmup += $w
    Log ('warmup {0}: threads={1} steady_t={2}C steady_w={3}W iter/s={4} invalid={5}' -f $attempt, $threads, $steadyT, $w.steady_w, $w.steady_iter, $w.invalid)
    if ($w.invalid) { throw "warmup invalid: $($w.invalid)" }

    if ($steadyT -lt $TargetLow -and $threads -lt $MaxThreads) {
      $threads += 2
      Start-Sleep -Seconds 8
      continue
    }
    if ($steadyT -gt $TargetHigh -and $threads -gt 4) {
      $threads -= 2
      Start-Sleep -Seconds 8
      continue
    }
    break
  }
  $summary.thread_count = $threads
  Log "chosen thread count: $threads"

  # ---- measurement: randomized/repeated modes ------------------------------
  for ($i = 0; $i -lt $modeList.Count; $i++) {
    $m = [int]$modeList[$i]
    $label = "p$i-m$m"

    Set-Mode 0 | Out-Null
    $cd = Wait-Cooldown -TargetC $CooldownTargetC -MaxSec $CooldownMaxSec
    $summary.cooldowns += $cd
    Log ('cooldown before {0}: ok={1} t={2}C sec={3}' -f $label, $cd.ok, $cd.t, $cd.sec)
    if (-not $cd.ok) { throw "cooldown to $CooldownTargetC C failed before $label (last $($cd.t) C)" }

    Set-Mode $m | Out-Null
    [LoadGen2]::Start($threads)
    $res = Invoke-Phase -Seconds $LoadSec -Mode $m -Label $label
    Stop-Load
    $summary.phases += $res
    Log ('{0}: steady t={1}C w={2}W iter/s={3} start={4}C peak={5}C n={6} invalid={7}' -f $label, $res.steady_t, $res.steady_w, $res.steady_iter, $res.start_t, $res.peak_t, $res.samples, $res.invalid)

    if ($res.invalid -and $res.invalid -like 'hot:*') {
      Log 'restoring balanced after hot abort'
      Set-Mode 0 | Out-Null
      Start-Sleep -Seconds 25
      throw "hot abort at $label"
    }
    if ($res.invalid) { throw "phase $label invalid: $($res.invalid)" }
  }
} catch {
  $failed = $_.Exception.Message
  Log "ERROR: $failed"
} finally {
  try { Stop-Load } catch { Log "STOP FAILED: $($_.Exception.Message)" }

  if ($paused) {
    try {
      & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root 'profile.ps1') -Mode resume | Out-Null
      Log 'governor resumed'
    } catch { Log "resume failed: $($_.Exception.Message)" }
  }

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
  New-Item -ItemType File -Path $doneFlag -Force | Out-Null
  if ($watchdog) { try { $null = $watchdog.WaitForExit(5000) } catch { } }
  [System.IO.File]::WriteAllText($summaryPath, ($summary | ConvertTo-Json -Depth 6), $utf8)
  Log 'done'
}

if ($failed) { exit 1 }
if (-not $summary.restored_ok) { exit 3 }
exit 0
