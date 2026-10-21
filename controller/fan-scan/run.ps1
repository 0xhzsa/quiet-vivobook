param(
  [int]$Cycles = 1,
  [int]$Idle = 25,
  [int]$Load = 100,
  [int]$LoadMax = 200,
  [int]$HotTarget = 80,
  [int]$Cooldown = 70,
  [int]$Interval = 5
)

$ErrorActionPreference = 'Stop'
$scan = Join-Path $PSScriptRoot 'scan.ps1'
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$out = Join-Path $PSScriptRoot ("run-" + $stamp)

$argList = @(
  '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"{0}"' -f $scan),
  '-Cycles', $Cycles, '-Idle', $Idle, '-Load', $Load, '-LoadMax', $LoadMax,
  '-HotTarget', $HotTarget, '-Cooldown', $Cooldown,
  '-Interval', $Interval, '-OutDir', ('"{0}"' -f $out)
)

try {
  $p = Start-Process powershell.exe -Verb RunAs -ArgumentList $argList -PassThru -ErrorAction Stop
  "OUT=$out"
  "PID=$($p.Id)"
} catch {
  "ELEVATION_DECLINED $($_.Exception.Message)"
  exit 1
}
