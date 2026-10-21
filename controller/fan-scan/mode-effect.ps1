#requires -Version 5.1
<#
  mode-effect.ps1 (v2) - measure what the ASUS thermal policy actually does.

  v1 was invalid: it started the load as a hidden child, Windows applied EcoQoS
  and pinned it to the E-cores, and in two phases the child died early. The
  sampler had no way to tell a dead load from a hot one, so it reported idle
  temperatures as "silent mode".

  v2 fixes the measurement, not the story:
    - the load runs IN THIS PROCESS, on real threads, so nothing can throttle
      it away or kill it silently;
    - every sample reads a work counter; if the counter stops advancing the
      phase is marked invalid instead of being reported as data;
    - thread count is auto-tuned first so the phases sit in a band where the
      fan policy can actually make a difference (74-86 C in balanced mode);
    - the run is A-B-A (mode 0, 1, 2, 0) so the last phase is a drift control.

  Encoding on VIVO is NOT the generic ASUS one:
      0 = default/balanced   1 = SILENT   2 = OVERBOOST

  Output: samples.jsonl, summary.json, mode.log
#>
param(
  [int]$LoadSec = 100,
  [int]$WarmSec = 40,
  [int]$BetweenSec = 15,
  [int]$SteadySec = 50,
  [int]$Interval = 2,
  [int]$StartThreads = 6,
  [int]$MaxThreads = 16,
  [int[]]$Modes = @(0, 1, 2, 0),
  [uint32]$DeviceId = 0x00110019,
  [double]$AbortTempC = 95.0,
  [double]$TargetLow = 74.0,
  [double]$TargetHigh = 86.0,
  [string]$OutDir
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
if (-not $OutDir) { $OutDir = Join-Path $PSScriptRoot ('mode-' + (Get-Date).ToString('yyyyMMdd-HHmmss')) }
New-Item -ItemType Directory -Path $OutDir -Force | Out-Null

$logPath = Join-Path $OutDir 'mode.log'
$jsonlPath = Join-Path $OutDir 'samples.jsonl'
$summaryPath = Join-Path $OutDir 'summary.json'
$doneFlag = Join-Path $OutDir 'done.flag'
$utf8 = New-Object System.Text.UTF8Encoding($false)

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
$ambient = Get-AmbientC
Log ('baseline raw=0x{0:X8} mode={1} ambient={2}C threads={3} tjmax={4}' -f $baselineRaw, $baselineMode, $ambient, $cores, $tjMax)

$watchdogSec = ($WarmSec * 3) + (($LoadSec + $BetweenSec) * $Modes.Count) + 300
$watchdog = Start-Process -FilePath 'powershell.exe' -PassThru -WindowStyle Hidden -ArgumentList @(
  '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', (Join-Path $PSScriptRoot 'devs-watchdog.ps1'),
  '-DeviceId', $DeviceId, '-RestoreValue', $baselineMode,
  '-DoneFlag', ('"{0}"' -f $doneFlag), '-TimeoutSec', "$watchdogSec",
  '-Log', ('"{0}"' -f $logPath)
)
Log "watchdog started pid=$($watchdog.Id) timeout=${watchdogSec}s"

$paused = $false
try {
  & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root 'profile.ps1') -Mode stock | Out-Null
  $paused = $true
  Log 'governor paused, stock scheme active'
} catch { Log "could not pause governor: $($_.Exception.Message)" }

$script:clock = [Diagnostics.Stopwatch]::StartNew()
$script:lastEnergy = $null
$script:lastT = $null

function Invoke-Phase {
  param([int]$Seconds, [int]$Mode, [string]$Label)
  $rows = @()
  $peak = 0.0
  $invalid = $null
  $stall = 0
  $prevIter = $null
  $prevIterT = $null
  $end = $script:clock.Elapsed.TotalSeconds + $Seconds

  while ($script:clock.Elapsed.TotalSeconds -lt $end) {
    $t0 = $script:clock.Elapsed.TotalSeconds

    $temps = Get-CoreTemps
    $valid = @($temps | Where-Object { -not [double]::IsNaN($_) })
    $tmax = if ($valid.Count -gt 0) { [math]::Round(($valid | Measure-Object -Maximum).Maximum, 1) } else { $null }

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

    $row = [ordered]@{
      t = [math]::Round($t0, 2); label = $Label; mode = $Mode
      t_max = $tmax; pkg_w = $watts
      iter = $iter; iter_per_s = $rate
      alive_threads = [LoadGen2]::Alive()
    }
    [System.IO.File]::AppendAllText($jsonlPath, (Json $row) + "`n", $utf8)
    $rows += $row
    if ($null -ne $tmax -and $tmax -gt $peak) { $peak = $tmax }

    if ($stall -ge 3) { $invalid = 'work counter stalled - load not running'; Log "INVALID: $Label $invalid"; break }
    if ($null -ne $tmax -and $tmax -ge $AbortTempC) { $invalid = "hot: $tmax C"; Log "ABORT: $Label $invalid"; break }

    $spent = $script:clock.Elapsed.TotalSeconds - $t0
    $sleepMs = [int](($Interval * 1000) - ($spent * 1000))
    if ($sleepMs -lt 100) { $sleepMs = 100 }
    Start-Sleep -Milliseconds $sleepMs
  }

  $endT = $script:clock.Elapsed.TotalSeconds
  $cut = $endT - [math]::Min($Seconds, $SteadySec)
  $steady = @($rows | Where-Object { $null -ne $_.t_max -and $_.t -ge $cut })
  $stw = @($steady | Where-Object { $null -ne $_.pkg_w } | ForEach-Object { $_.pkg_w })
  $stt = @($steady | Where-Object { $null -ne $_.t_max } | ForEach-Object { $_.t_max })
  $stir = @($steady | Where-Object { $null -ne $_.iter_per_s } | ForEach-Object { $_.iter_per_s })

  return [ordered]@{
    label = $Label
    mode = $Mode
    seconds = [math]::Round($endT - ($end - $Seconds), 1)
    peak_t = $peak
    steady_t = if ($stt.Count) { [math]::Round(($stt | Measure-Object -Average).Average, 2) } else { $null }
    steady_w = if ($stw.Count) { [math]::Round(($stw | Measure-Object -Average).Average, 2) } else { $null }
    steady_iter = if ($stir.Count) { [math]::Round(($stir | Measure-Object -Average).Average, 1) } else { $null }
    samples = $rows.Count
    invalid = $invalid
  }
}

function Set-Mode([int]$m) {
  $r = Set-Devs $DeviceId ([uint32]$m)
  $raw = Get-Dsts $DeviceId
  $applied = [int]($raw -band 0xFFFF)
  Log ('mode {0}: write result={1} readback=0x{2:X8} applied={3}' -f $m, $r, $raw, $applied)
  if ($applied -ne $m) { throw "mode $m did not stick (readback $applied)" }
  return $applied
}

$summary = [ordered]@{
  baseline_mode = $baselineMode
  ambient_c = $ambient
  logical_processors = $cores
  thread_count = $null
  warmup = @()
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
    $null = [LoadGen2]::WaitStop(3000)
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

  # ---- measurement: A-B-A ------------------------------------------------
  for ($i = 0; $i -lt $Modes.Count; $i++) {
    $m = [int]$Modes[$i]
    $label = "p$i-m$m"
    Set-Mode $m | Out-Null
    [LoadGen2]::Start($threads)
    $res = Invoke-Phase -Seconds $LoadSec -Mode $m -Label $label
    $null = [LoadGen2]::WaitStop(3000)
    $summary.phases += $res
    Log ('{0}: steady t={1}C w={2}W iter/s={3} peak={4}C n={5} invalid={6}' -f $label, $res.steady_t, $res.steady_w, $res.steady_iter, $res.peak_t, $res.samples, $res.invalid)

    if ($res.invalid -and $res.invalid -like 'hot:*') {
      Log 'restoring balanced after hot abort'
      Set-Mode 0 | Out-Null
      Start-Sleep -Seconds 25
    } elseif ($i -lt $Modes.Count - 1) {
      Start-Sleep -Seconds $BetweenSec
    }
  }
} catch {
  $failed = $_.Exception.Message
  Log "ERROR: $failed"
} finally {
  $null = [LoadGen2]::WaitStop(3000)
  try {
    $null = Set-Devs $DeviceId ([uint32]$baselineMode)
    $finalRaw = Get-Dsts $DeviceId
    $summary.restored_raw = $finalRaw
    $summary.restored_ok = ([int]($finalRaw -band 0xFFFF) -eq $baselineMode)
    Log ('restored mode={0} raw=0x{1:X8} ok={2}' -f $baselineMode, $finalRaw, $summary.restored_ok)
  } catch { Log "RESTORE FAILED: $($_.Exception.Message)" }

  if ($paused) {
    try {
      & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root 'profile.ps1') -Mode resume | Out-Null
      Log 'governor resumed'
    } catch { Log "resume failed: $($_.Exception.Message)" }
  }
  if ($msr) { try { $msr.Close() } catch { } }

  $summary.aborted = $failed
  $summary.finished = (Get-Date).ToString('o')
  New-Item -ItemType File -Path $doneFlag -Force | Out-Null
  if ($watchdog) { try { $null = $watchdog.WaitForExit(5000) } catch { } }
  [System.IO.File]::WriteAllText($summaryPath, ($summary | ConvertTo-Json -Depth 6), $utf8)
  Log 'done'
}
