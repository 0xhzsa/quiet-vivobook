#Requires -RunAsAdministrator

$ErrorActionPreference = 'Stop'

$QUIET_NAME = 'Quiet (quiet-vivobook)'

if (Get-ScheduledTask -TaskName 'quiet-vivobook' -ErrorAction SilentlyContinue) {
  Stop-ScheduledTask -TaskName 'quiet-vivobook' -ErrorAction SilentlyContinue
  Unregister-ScheduledTask -TaskName 'quiet-vivobook' -Confirm:$false
  "removed scheduled task"
}

powercfg /setactive 381b4222-f694-41f0-9685-ff5bb260df2e | Out-Null
"active scheme restored to Balanced"

$line = (powercfg /list) | Where-Object { $_ -match [regex]::Escape($QUIET_NAME) } | Select-Object -First 1
if ($line -and $line -match '([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})') {
  powercfg /delete $Matches[1] | Out-Null
  "deleted power scheme $($Matches[1])"
}

""
"PawnIO was left installed on purpose: it is a shared, signed driver also used"
"by LibreHardwareMonitor, FanControl and OpenRGB, and removing it would break"
"any of those. To remove it anyway:"
"  & 'C:\Program Files\PawnIO\uninstall.exe'"
"Memory Integrity was never changed."
