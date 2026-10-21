#requires -Version 5.1
<#
  devs-watchdog.ps1 - last-resort restore.

  Started by devs-test.ps1 as an elevated child. It holds the value the
  machine had before the test and writes it back if the parent dies without
  creating the done flag. It is deliberately independent: its own WMI
  connection, its own process, no shared state beyond a flag file.
#>
param(
  [uint32]$DeviceId = 0x00110019,
  [uint32]$RestoreValue = 0,
  [string]$DoneFlag,
  [int]$TimeoutSec = 30,
  [string]$Log
)

$ErrorActionPreference = 'Stop'

function Log($m) {
  $line = '{0} {1}' -f (Get-Date).ToString('HH:mm:ss.fff'), $m
  if ($Log) {
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::AppendAllText($Log, $line + "`r`n", $utf8)
  }
}

$deadline = (Get-Date).AddSeconds($TimeoutSec)
while ((Get-Date) -lt $deadline) {
  if ($DoneFlag -and (Test-Path $DoneFlag)) {
    Log 'watchdog: done flag present, standing down'
    exit 0
  }
  Start-Sleep -Milliseconds 500
}

Log ('watchdog: timeout reached, restoring id=0x{0:X8} value={1}' -f $DeviceId, $RestoreValue)
try {
  $path = 'root\wmi:AsusAtkWmi_WMNB.InstanceName="{0}"' -f 'ACPI\PNP0C14\ATK_0'.Replace('\', '\\')
  $o = [wmi]$path
  $in = $o.PSBase.GetMethodParameters('DEVS')
  $in.Control_status = [uint32]$RestoreValue
  $in.Device_ID = [uint32]$DeviceId
  $out = $o.PSBase.InvokeMethod('DEVS', $in, $null)
  Log ('watchdog: RESTORED result={0}' -f $out['result'])
} catch {
  Log ('watchdog: RESTORE FAILED {0}' -f $_.Exception.Message)
  exit 2
}
exit 0
