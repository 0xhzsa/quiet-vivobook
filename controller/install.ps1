#Requires -RunAsAdministrator

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot

$QUIET_NAME = 'Quiet (quiet-vivobook)'
$SUB = '54533251-82be-4824-96c1-47b60b740d00'
$BOOST = 'be337238-0d82-4146-a960-4f3749d470c7'
$EPP = '36687f9e-e3a5-4dbf-b1dc-15eb381c6863'
$MAXSTATE = 'bc5038f7-23e0-4960-96da-33abaf5935ec'
$COOLPOL = '94d3a615-a899-4ac5-ae2b-e4d8f634367f'

function Get-SchemeGuidByName([string]$name) {
  $line = (powercfg /list) | Where-Object { $_ -match [regex]::Escape($name) } | Select-Object -First 1
  if (-not $line) { return $null }
  if ($line -match '([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})') { return $Matches[1] }
}

"quiet-vivobook install"
"----------------------"

# --- prerequisite: PawnIO (signed, HVCI-compatible MSR access) ---------------
# The LibreHardwareMonitor build we ship carries the vendor installer as an
# embedded resource. Extracting and running that exact copy means we install
# what the upstream project would install, signature intact, no download.

$libPath = Join-Path $root 'tools\lhm\LibreHardwareMonitorLib.dll'
if (-not (Test-Path $libPath)) {
  throw @"
LibreHardwareMonitorLib.dll not found at:
  $libPath

Download LibreHardwareMonitor from
  https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/releases
copy LibreHardwareMonitorLib.dll into that folder, then re-run this script.
"@
}
Add-Type -Path $libPath

if ([LibreHardwareMonitor.PawnIo.PawnIo]::IsInstalled) {
  "PawnIO already installed (version $([LibreHardwareMonitor.PawnIo.PawnIo]::Version))"
} else {
  $exePath = Join-Path $root 'tools\lhm\LibreHardwareMonitor.exe'
  $appAsm = [Reflection.Assembly]::LoadFrom($exePath)
  $resName = $appAsm.GetManifestResourceNames() | Where-Object { $_ -match 'PawnIO_setup\.exe$' } | Select-Object -First 1
  if (-not $resName) { throw "embedded PawnIO installer not found in LibreHardwareMonitor.exe" }

  $setup = Join-Path $env:TEMP 'PawnIO_setup.exe'
  $stream = $appAsm.GetManifestResourceStream($resName)
  $file = [IO.File]::Create($setup)
  $stream.CopyTo($file)
  $file.Close(); $stream.Close()

  $sig = Get-AuthenticodeSignature $setup
  if ($sig.Status -ne 'Valid') { throw "PawnIO installer signature invalid: $($sig.Status)" }
  "PawnIO installer signature valid: $($sig.SignerCertificate.Subject)"

  $p = Start-Process -FilePath $setup -ArgumentList '-install' -Wait -PassThru
  Remove-Item $setup -Force -ErrorAction SilentlyContinue
  if ($p.ExitCode -ne 0) { throw "PawnIO install failed, exit $($p.ExitCode)" }
  if (-not [LibreHardwareMonitor.PawnIo.PawnIo]::IsInstalled) { throw "PawnIO install reported success but driver is not installed" }
  "PawnIO installed (version $([LibreHardwareMonitor.PawnIo.PawnIo]::Version))"
}

# --- power scheme ------------------------------------------------------------

$quiet = Get-SchemeGuidByName $QUIET_NAME
if (-not $quiet) {
  $out = powercfg /duplicatescheme 381b4222-f694-41f0-9685-ff5bb260df2e
  if ($out -match '([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})') { $quiet = $Matches[1] }
  powercfg /changename $quiet $QUIET_NAME 'Managed by quiet-vivobook: caps sustained CPU boost to cut heat and fan noise' | Out-Null
  "created power scheme $quiet"
} else {
  "reusing power scheme $quiet"
}

$cfg = Get-Content (Join-Path $root 'config.json') -Raw | ConvertFrom-Json
$first = $cfg.profiles[0]

powercfg /setacvalueindex $quiet $SUB $BOOST $first.boost | Out-Null
powercfg /setacvalueindex $quiet $SUB $EPP $first.epp | Out-Null
powercfg /setacvalueindex $quiet $SUB $MAXSTATE $first.state | Out-Null
powercfg /setdcvalueindex $quiet $SUB $BOOST $first.boost | Out-Null
powercfg /setdcvalueindex $quiet $SUB $EPP $first.epp | Out-Null
powercfg /setdcvalueindex $quiet $SUB $MAXSTATE $first.state | Out-Null
powercfg /setacvalueindex $quiet $SUB $COOLPOL 1 | Out-Null       # active: fan before throttle
powercfg /setdcvalueindex $quiet $SUB $COOLPOL 1 | Out-Null
"configured start profile '$($first.id)': boost=$($first.boost) epp=$($first.epp) state=$($first.state)"

# --- scheduled task ----------------------------------------------------------

$action = New-ScheduledTaskAction -Execute 'powershell.exe' `
  -Argument ('-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "{0}"' -f (Join-Path $root 'quiet-vivobook.ps1'))
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
  -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
  -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName 'quiet-vivobook' -Action $action -Trigger $trigger `
  -Principal $principal -Settings $settings -Description 'Adaptive CPU power cap for quiet operation' -Force | Out-Null
"registered scheduled task 'quiet-vivobook' (at logon, highest privileges)"

Start-ScheduledTask -TaskName 'quiet-vivobook'
Start-Sleep -Seconds 3
"governor running: $((Get-ScheduledTask -TaskName 'quiet-vivobook').State)"
"active scheme: $(powercfg /getactivescheme)"
