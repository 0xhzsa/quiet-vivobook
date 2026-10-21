param()
$ErrorActionPreference = 'Stop'
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$out = Join-Path $PSScriptRoot ("devs-" + $stamp)
$argList = @(
  '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"{0}"' -f (Join-Path $PSScriptRoot 'devs-test.ps1')),
  '-OutDir', ('"{0}"' -f $out)
)
try {
  $p = Start-Process powershell.exe -Verb RunAs -ArgumentList $argList -PassThru -ErrorAction Stop
  "OUT=$out"
  "PID=$($p.Id)"
} catch {
  "ELEVATION_DECLINED $($_.Exception.Message)"
  exit 1
}
