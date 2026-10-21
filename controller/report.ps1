<#
  report.ps1 - one-page summary of what the governor actually did.

  Reads telemetry.csv, governor-log.csv and model.json and answers the only
  questions that matter without opening a spreadsheet:

    - how hot did it get, and for how long
    - how much of the time was spent in each profile
    - how often did it switch, and did it flap
    - is the learned model still where it was seeded

  Usage:
    powershell -ExecutionPolicy Bypass -File .\report.ps1
    powershell -ExecutionPolicy Bypass -File .\report.ps1 -Hours 2
    powershell -ExecutionPolicy Bypass -File .\report.ps1 -Since 2026-10-20T13:00
#>

param(
  [double]$Hours = 0,
  [datetime]$Since = [datetime]::MinValue,
  [string]$Root = $PSScriptRoot
)

$ErrorActionPreference = 'Stop'
$cfg      = Get-Content (Join-Path $Root 'config.json') -Raw | ConvertFrom-Json
$telPath  = Join-Path $Root $cfg.telemetryFile
$logPath  = Join-Path $Root $cfg.logFile
$modelPath= Join-Path $Root $cfg.modelFile

function Read-Text([string]$path) {
  for ($i = 0; $i -lt 12; $i++) {
    try { return [System.IO.File]::ReadAllText($path) } catch { Start-Sleep -Milliseconds 300 }
  }
  throw "cannot read $path (locked by another process)"
}

function Rule([string]$t) {
  ""
  $t
  ('-' * $t.Length)
}

function Pct($sorted, [double]$p) {
  if ($sorted.Count -eq 0) { return 0.0 }
  $i = [int][math]::Floor(($sorted.Count - 1) * $p)
  return [double]$sorted[$i]
}

function MinutesAbove($rows, [double]$thr) {
  $sum = 0.0
  for ($i = 0; $i -lt $rows.Count - 1; $i++) {
    if ($rows[$i].temp -gt $thr) {
      $dt = ($rows[$i + 1].time - $rows[$i].time).TotalSeconds
      if ($dt -gt 0 -and $dt -le 60) { $sum += $dt }
    }
  }
  return $sum / 60.0
}

# ---- load telemetry ---------------------------------------------------------
# Older rows used a 5-column schema (time,temp,watts,ema,profile); newer rows
# use 7 (time,temp,watts,ema,tss,profile,controller). Parse by width, not by
# trusting the header.

$raw = (Read-Text $telPath) -split "`r?`n" | Where-Object { $_ -and $_ -notmatch '^time,' }
$rows = New-Object System.Collections.Generic.List[object]
foreach ($ln in $raw) {
  $f = $ln -split ','
  if ($f.Count -lt 5) { continue }
  $t = [datetime]::MinValue
  if (-not [datetime]::TryParse($f[0], [ref]$t)) { continue }
  $profile = if ($f.Count -ge 6) { $f[5] } else { $f[4] }
  $rows.Add([pscustomobject]@{
    time    = $t
    temp    = [double]$f[1]
    watts   = [double]$f[2]
    ema     = [double]$f[3]
    profile = $profile
  })
}
if ($Hours -gt 0) {
  $cut = (Get-Date).AddHours(-$Hours)
  $rows = @($rows | Where-Object { $_.time -ge $cut })
}
if ($Since -gt [datetime]::MinValue) {
  $rows = @($rows | Where-Object { $_.time -ge $Since })
}
if ($rows.Count -lt 2) { throw "not enough telemetry to report on" }

$first = $rows[0].time
$last  = $rows[-1].time
$span  = ($last - $first).TotalMinutes
$cadence = if ($rows.Count -gt 1) { ($last - $first).TotalSeconds / ($rows.Count - 1) } else { 0 }

"QUIET-VIVOBOOK REPORT"
"=" * 78
"window   : {0:yyyy-MM-dd HH:mm} -> {1:HH:mm}  ({2:N0} min, {3} samples, {4:N1} s cadence)" -f $first, $last, $span, $rows.Count, $cadence

$lastStart = (Read-Text $logPath) -split "`r?`n" | Where-Object { $_ -match 'start scheme=' } | Select-Object -Last 1
if ($lastStart -and $lastStart -match 'power=(\w+)') { "power    : $($Matches[1])  (learning is AC-gated)" }

# ---- thermal ----------------------------------------------------------------
Rule "THERMAL"
$temps = @($rows | ForEach-Object { $_.temp } | Sort-Object)
$meanT = ($rows | Measure-Object temp -Average).Average
$meanW = ($rows | Measure-Object watts -Average).Average
$maxW  = ($rows | Measure-Object watts -Maximum).Maximum

"  min / mean / p50 / p95 / max : {0:N0} / {1:N1} / {2:N0} / {3:N0} / {4:N0} C" -f `
  $temps[0], $meanT, (Pct $temps 0.50), (Pct $temps 0.95), $temps[-1]
"  power  mean / max            : {0:N1} / {1:N1} W" -f $meanW, $maxW

"" 
"  time above   70 C : {0,6:N1} min  ({1,5:N1} %)" -f (MinutesAbove $rows 70), (100 * (MinutesAbove $rows 70) / $span)
"  time above   75 C : {0,6:N1} min  ({1,5:N1} %)" -f (MinutesAbove $rows 75), (100 * (MinutesAbove $rows 75) / $span)
"  time above   80 C : {0,6:N1} min  ({1,5:N1} %)" -f (MinutesAbove $rows 80), (100 * (MinutesAbove $rows 80) / $span)
"  time above   85 C : {0,6:N1} min  ({1,5:N1} %)" -f (MinutesAbove $rows 85), (100 * (MinutesAbove $rows 85) / $span)
"  time above   90 C : {0,6:N1} min  ({1,5:N1} %)" -f (MinutesAbove $rows 90), (100 * (MinutesAbove $rows 90) / $span)

# ---- under load -------------------------------------------------------------
# Averaging over idle time flatters any controller. These figures only include
# samples where package power is above the idle band, so they describe what
# happens when the machine is actually working.
Rule "UNDER LOAD  (> 12 W)"
$ln = 0; $lsec = 0.0; $over80 = 0.0; $lt = @(); $lw = @()
for ($i = 0; $i -lt $rows.Count - 1; $i++) {
  $dt = ($rows[$i + 1].time - $rows[$i].time).TotalSeconds
  if ($dt -le 0 -or $dt -gt 60) { continue }
  if ($rows[$i].watts -gt 12) {
    $ln++; $lsec += $dt
    $lt += $rows[$i].temp
    $lw += $rows[$i].watts
    if ($rows[$i].temp -gt 80) { $over80 += $dt }
  }
}
if ($ln -ge 20) {
  $ltS = @($lt | Sort-Object)
  $loadShare = 100 * $lsec / ($span * 60)
  "  share of window  : {0,5:N1} %  ({1:N0} min)" -f $loadShare, ($lsec / 60)
  "  temp mean / p95  : {0:N1} / {1:N0} C" -f (($lt | Measure-Object -Average).Average), (Pct $ltS 0.95)
  "  temp max         : {0:N0} C" -f $ltS[-1]
  "  power mean / max : {0:N1} / {1:N1} W" -f (($lw | Measure-Object -Average).Average), (($lw | Measure-Object -Maximum).Maximum)
  "  above 80 C while loaded : {0:N1} min ({1:N1} % of loaded time)" -f ($over80 / 60), (100 * $over80 / $lsec)
} else {
  "  not enough loaded samples in this window ({0}) - run it during real work" -f $ln
}

# ---- profiles ---------------------------------------------------------------
Rule "PROFILES"
"  {0,-12} {1,7} {2,9} {3,8} {4,8} {5,9}" -f 'profile', 'share', 'mean C', 'max C', 'mean W', 'max W'
foreach ($g in ($rows | Group-Object profile | Sort-Object Count -Descending)) {
  $share = 100 * $g.Count / $rows.Count
  "  {0,-12} {1,6:N1}% {2,9:N1} {3,8:N0} {4,8:N1} {5,9:N1}" -f `
    $g.Name, $share,
    (($g.Group | Measure-Object temp -Average).Average),
    (($g.Group | Measure-Object temp -Maximum).Maximum),
    (($g.Group | Measure-Object watts -Average).Average),
    (($g.Group | Measure-Object watts -Maximum).Maximum)
}

# ---- control ----------------------------------------------------------------
Rule "CONTROL"
$logLines = (Read-Text $logPath) -split "`r?`n"
$changes = @($logLines | Where-Object { $_ -match ',(mpc-down|mpc-up|emergency-down|hys-down|hys-up) ' })
$downs = @($changes | Where-Object { $_ -match '-down ' }).Count
$ups   = @($changes | Where-Object { $_ -match '-up ' }).Count
$rate  = if ($span -gt 0) { $changes.Count / ($span / 60.0) } else { 0 }

"  switches : {0}   ({1:N1}/hour)   down={2}  up={3}" -f $changes.Count, $rate, $downs, $ups

# flapping: most switches inside any rolling 5-minute window
$times = @($changes | ForEach-Object {
  $p = ($_ -split ',')[0]
  $d = [datetime]::MinValue
  if ([datetime]::TryParse($p, [ref]$d)) { $d }
} | Sort-Object)
$worst = 0
for ($i = 0; $i -lt $times.Count; $i++) {
  $n = 0
  for ($j = $i; $j -lt $times.Count; $j++) {
    if (($times[$j] - $times[$i]).TotalMinutes -le 5) { $n++ } else { break }
  }
  if ($n -gt $worst) { $worst = $n }
}
"  worst 5-min burst : {0} switches  ({1})" -f $worst, $(if ($worst -le 3) { 'ok' } else { 'check tuning' })

# ---- model ------------------------------------------------------------------
Rule "MODEL  (learned vs measured seed)"
if (Test-Path $modelPath) {
  $m = Get-Content $modelPath -Raw | ConvertFrom-Json
  "  {0,-12} {1,10} {2,10} {3,8} {4,10} {5,10}" -f 'profile', 'eq C', 'seed C', 'delta', 'W', 'seed W'
  foreach ($p in $cfg.profiles) {
    $eq = [double]$p.eq; $q = [double]$p.watts
    $mp = $m.eq.PSObject.Properties[$p.id]
    if ($mp) { $eq = [double]$mp.Value }
    $mq = $m.q.PSObject.Properties[$p.id]
    if ($mq) { $q = [double]$mq.Value }
    "  {0,-12} {1,10:N1} {2,10:N1} {3,8:N1} {4,10:N1} {5,10:N1}" -f `
      $p.id, $eq, [double]$p.eq, ($eq - [double]$p.eq), $q, [double]$p.watts
  }
  "  last saved     : $($m.updated)"
} else {
  "  model.json not present - running on config seeds"
}

# ---- verdict ----------------------------------------------------------------
Rule "VERDICT"
$above80 = MinutesAbove $rows 80
$share80 = 100 * $above80 / $span
$loadedShare80 = if ($lsec -gt 0) { 100 * $over80 / $lsec } else { 0 }
if ($ln -lt 20) {
  "  Window is mostly idle - the headline below is not a stress result."
  "  Re-run during real work, or with -Hours covering a loaded stretch."
}
if ($share80 -lt 5) {
  "  Held the 80 C target for {0:N1}% of the window." -f (100 - $share80)
} elseif ($share80 -lt 20) {
  "  Above 80 C for {0:N1}% of the window - within tolerance for bursty work." -f $share80
} else {
  "  Above 80 C for {0:N1}% of the window. Either the workload outruns the caps" -f $share80
  "  or targetHigh is set too high for this chassis."
}
if ($ln -ge 20) {
  "  While loaded (> 12 W): above 80 C for {0:N1}% of that time." -f $loadedShare80
}
if ($worst -gt 3) {
  "  Switch rate is high ({0} in 5 min). Raise dwellSeconds or wSwitch." -f $worst
}
""
"  Note: temperature is the acoustic proxy. Fan RPM is unreadable on this model."
