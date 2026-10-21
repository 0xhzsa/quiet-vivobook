param([int]$Mode = 1, [int]$ObserveSec = 90)
$ErrorActionPreference = 'Stop'
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$out = Join-Path $PSScriptRoot ("setmode-" + $stamp)
$argList = @(
  '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"{0}"' -f (Join-Path $PSScriptRoot 'set-thermal-mode.ps1')),
  '-Mode', $Mode, '-ObserveSec', $ObserveSec, '-OutDir', ('"{0}"' -f $out)
)
try {
  $p = Start-Process powershell.exe -Verb RunAs -ArgumentList $argList -PassThru -ErrorAction Stop
  "OUT=$out"
  "PID=$($p.Id)"
} catch {
  "ELEVATION_DECLINED $($_.Exception.Message)"
  exit 1
}
