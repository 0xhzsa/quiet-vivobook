#requires -Version 5.1
<#
  scheme-ab.ps1 - clean throughput A/B/A for Windows power schemes.

  This is the non-elevated half of the measurement. It changes only the active
  power scheme, pauses the quiet-vivobook governor with its own paused.flag,
  and measures completed work in an in-process load. It does not write the ASUS
  thermal-policy device and it does not claim a fan-power saving.

  Design:
    - Balanced and Quiet are alternated in four blocks; each order appears
      twice, so a monotonic thermal drift partially cancels.
    - Every phase runs the same in-process integer load for the same wall time.
    - Work rate is measured from the load's completed work counter over the
      final SteadySec seconds, not from a per-sample rate that can be skewed by
      a short first interval.
    - The active scheme is read back after every write.
    - The original scheme is restored and the governor pause flag is removed
      in finally.

  Output: samples.jsonl, summary.json, scheme.log
#>
[CmdletBinding(PositionalBinding = $false)]
param(
  [int]$LoadSec = 60,
  [int]$SteadySec = 40,
  [int]$BetweenSec = 45,
  [int]$WarmSec = 30,
  [int]$Interval = 2,
  [int]$Threads = 8,
  [string]$OutDir
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$pauseFlag = Join-Path $root 'paused.flag'

if (-not $OutDir) { $OutDir = Join-Path $PSScriptRoot ('scheme-' + (Get-Date).ToString('yyyyMMdd-HHmmss')) }
New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
$OutDir = (Resolve-Path -LiteralPath $OutDir).Path
$logPath = Join-Path $OutDir 'scheme.log'
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

$battery = Get-CimInstance Win32_Battery -ErrorAction SilentlyContinue | Select-Object -First 1
$acOnline = $false
$charge = $null
if ($battery) {
  $charge = $battery.EstimatedChargeRemaining
  $acOnline = ($battery.BatteryStatus -eq 2 -or $battery.BatteryStatus -eq 6 -or $battery.BatteryStatus -eq 7 -or $battery.BatteryStatus -eq 8)
}
if (-not $acOnline) { throw 'AC power is required; refusing to run on battery' }

function Get-ActiveGuid {
  $line = powercfg /getactivescheme
  if ($line -match '([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})') { return $Matches[1] }
  throw 'could not read active power scheme'
}
function Get-SchemeGuid([string]$Name) {
  $line = (powercfg /list) | Where-Object { $_ -match [regex]::Escape($Name) } | Select-Object -First 1
  if ($line -and $line -match '([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})') { return $Matches[1] }
  throw "power scheme not found: $Name"
}
function Set-Scheme([string]$Guid) {
  & powercfg /setactive $Guid
  if ($LASTEXITCODE -ne 0) { throw "powercfg /setactive $Guid exited $LASTEXITCODE" }
  Start-Sleep -Seconds 1
  $active = Get-ActiveGuid
  if ($active -ne $Guid) { throw "scheme did not stick: wanted $Guid, got $active" }
}

$loadSrc = @'
using System;
using System.Threading;

public static class SchemeLoad {
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
if (-not ('SchemeLoad' -as [type])) { Add-Type -TypeDefinition $loadSrc -Language CSharp }
try { [System.Diagnostics.Process]::GetCurrentProcess().PriorityClass = 'High' } catch { }

function Stop-Load {
  if (-not [SchemeLoad]::WaitStop(5000)) { throw 'load threads did not exit within 5 s' }
}

function Invoke-Phase {
  param([int]$Seconds, [string]$Scheme, [string]$Label)
  $rows = @()
  $invalid = $null
  $sw = [Diagnostics.Stopwatch]::StartNew()
  [SchemeLoad]::Start($Threads)
  try {
    while ($sw.Elapsed.TotalSeconds -lt $Seconds) {
      Start-Sleep -Milliseconds ($Interval * 1000)
      $t = [math]::Round($sw.Elapsed.TotalSeconds, 2)
      $iter = [SchemeLoad]::Counter
      $row = [ordered]@{
        t = $t; label = $Label; scheme = $Scheme
        iter = $iter; alive_threads = [SchemeLoad]::Alive()
      }
      [System.IO.File]::AppendAllText($jsonlPath, (Json $row) + "`n", $utf8)
      $rows += $row
    }
  } finally {
    Stop-Load
  }

  $cut = [math]::Max(0, $Seconds - $SteadySec)
  $steady = @($rows | Where-Object { $_.t -ge $cut })
  $rate = $null
  if ($steady.Count -ge 2) {
    $first = $steady[0]
    $last = $steady[-1]
    if ($last.t -gt $first.t) { $rate = [math]::Round(($last.iter - $first.iter) / ($last.t - $first.t), 1) }
  }
  if ($rows.Count -lt 3) { $invalid = "only $($rows.Count) samples" }
  elseif ($steady.Count -lt 3) { $invalid = "steady window has $($steady.Count) samples" }
  elseif ($null -eq $rate) { $invalid = 'work rate unavailable' }

  Log ('{0}: scheme={1} samples={2} steady={3} iter/s={4} invalid={5}' -f $Label, $Scheme, $rows.Count, $steady.Count, $rate, $invalid)
  return [ordered]@{
    label = $Label
    scheme = $Scheme
    seconds = [math]::Round($sw.Elapsed.TotalSeconds, 1)
    steady_samples = $steady.Count
    iter_per_s = $rate
    invalid = $invalid
  }
}

$balanced = Get-SchemeGuid 'Balanced'
$quiet = Get-SchemeGuid 'Quiet (quiet-vivobook)'
$original = Get-ActiveGuid
$createdPause = $false
$summary = [ordered]@{
  original_scheme = $original
  balanced_guid = $balanced
  quiet_guid = $quiet
  threads = $Threads
  load_sec = $LoadSec
  steady_sec = $SteadySec
  between_sec = $BetweenSec
  warmup_sec = $WarmSec
  ac_online = $acOnline
  battery_charge_pct = $charge
  warmup = $null
  phases = @()
  ratios = @()
  throughput_cost_pct = $null
  aborted = $null
}

$failed = $null
try {
  if (-not (Test-Path -LiteralPath $pauseFlag)) {
    New-Item -ItemType File -Path $pauseFlag -Force | Out-Null
    $createdPause = $true
  }
  Log "governor pause flag: $pauseFlag (created=$createdPause)"
  Start-Sleep -Seconds 6

  Set-Scheme $balanced
  $summary.warmup = Invoke-Phase -Seconds $WarmSec -Scheme 'balanced' -Label 'warmup'
  if ($summary.warmup.invalid) { throw "warmup invalid: $($summary.warmup.invalid)" }
  Set-Scheme $balanced
  Start-Sleep -Seconds $BetweenSec

  $orders = @(
    @('balanced', 'quiet'),
    @('quiet', 'balanced'),
    @('balanced', 'quiet'),
    @('quiet', 'balanced')
  )
  $block = 0
  foreach ($order in $orders) {
    $block++
    $blockRows = @()
    foreach ($name in $order) {
      $guid = if ($name -eq 'balanced') { $balanced } else { $quiet }
      Set-Scheme $guid
      $res = Invoke-Phase -Seconds $LoadSec -Scheme $name -Label ("b{0}-{1}" -f $block, $name)
      $summary.phases += $res
      if ($res.invalid) { throw "phase $($res.label) invalid: $($res.invalid)" }
      $blockRows += $res
      Set-Scheme $balanced
      Start-Sleep -Seconds $BetweenSec
    }
    $b = @($blockRows | Where-Object { $_.scheme -eq 'balanced' })[0]
    $q = @($blockRows | Where-Object { $_.scheme -eq 'quiet' })[0]
    if ($null -eq $b.iter_per_s -or $null -eq $q.iter_per_s -or $b.iter_per_s -le 0) {
      throw "block $block has no usable paired rates"
    }
    $ratio = [math]::Round($q.iter_per_s / $b.iter_per_s, 4)
    $summary.ratios += [ordered]@{ block = $block; order = ($order -join ','); quiet_over_balanced = $ratio }
    Log ("block {0}: quiet/balanced work = {1}" -f $block, $ratio)
  }

  $ratios = @($summary.ratios | ForEach-Object { $_.quiet_over_balanced })
  if ($ratios.Count -gt 0) {
    $mean = ($ratios | Measure-Object -Average).Average
    $summary.throughput_cost_pct = [math]::Round((1 - $mean) * 100, 2)
    $summary.ratio_mean = [math]::Round($mean, 4)
    $summary.ratio_min = ($ratios | Measure-Object -Minimum).Minimum
    $summary.ratio_max = ($ratios | Measure-Object -Maximum).Maximum
    Log ("summary: quiet keeps {0:P2} of balanced work; cost {1}%" -f $mean, $summary.throughput_cost_pct)
  }
} catch {
  $failed = $_.Exception.Message
  Log "ERROR: $failed"
} finally {
  try { Set-Scheme $original } catch { Log "RESTORE FAILED: $($_.Exception.Message)" }
  if ($createdPause) {
    Remove-Item -LiteralPath $pauseFlag -ErrorAction SilentlyContinue
    Log 'governor pause flag removed'
  }
  $summary.aborted = $failed
  $summary.finished = (Get-Date).ToString('o')
  New-Item -ItemType File -Path $doneFlag -Force | Out-Null
  [System.IO.File]::WriteAllText($summaryPath, ($summary | ConvertTo-Json -Depth 6), $utf8)
  Log 'done'
}

if ($failed) { exit 1 }
exit 0
