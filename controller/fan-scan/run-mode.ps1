param(
  [int]$LoadSec = 100,
  [int]$BetweenSec = 15,
  [int]$SteadySec = 50,
  [int]$Interval = 2
)
$ErrorActionPreference = 'Stop'
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$out = Join-Path $PSScriptRoot ("mode-" + $stamp)
$argList = @(
  '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"{0}"' -f (Join-Path $PSScriptRoot 'mode-effect.ps1')),
  '-LoadSec', $LoadSec, '-BetweenSec', $BetweenSec, '-SteadySec', $SteadySec,
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
