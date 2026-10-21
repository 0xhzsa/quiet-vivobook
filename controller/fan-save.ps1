#requires -Version 5.1
<#
  fan-save.ps1 - Activate and maintain fan-saving mode on the ASUS Vivobook.

  This applies the efficient power profile (boost=3, epp=60, state=100) which
  reduces CPU power draw, heat generation, and fan speed. The governor is
  paused so it doesn't override the setting.

  Run this script to activate fan-saving mode. Run with -Mode resume to restore.

  No elevation required for power scheme changes.
#>
param(
  [ValidateSet('save', 'resume', 'status')]
  [string]$Mode = 'save'
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$pauseFlag = Join-Path $root 'paused.flag'

function Show-Status {
  $boost = (Get-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\Power\User\PowerSchemes\1c34d62b-115d-4e7b-abb7-f19a12b8159e\54533251-82be-4824-96c1-47b60b740d00\be337238-0d82-4146-a960-4f3749d470c7" -Name ACSettingIndex -ErrorAction SilentlyContinue).ACSettingIndex
  $epp = (Get-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\Power\User\PowerSchemes\1c34d62b-115d-4e7b-abb7-f19a12b8159e\54533251-82be-4824-96c1-47b60b740d00\36687f9e-e3a5-4dbf-b1dc-15eb381c6863" -Name ACSettingIndex -ErrorAction SilentlyContinue).ACSettingIndex
  $state = (Get-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\Power\User\PowerSchemes\1c34d62b-115d-4e7b-abb7-f19a12b8159e\54533251-82be-4824-96c1-47b60b740d00\bc5038f7-23e0-4960-96da-33abaf5935ec" -Name ACSettingIndex -ErrorAction SilentlyContinue).ACSettingIndex
  $paused = Test-Path $pauseFlag
  $scheme = (powercfg /getactivescheme)
  Write-Host "=== Fan-Save Status ==="
  Write-Host "Active scheme: $scheme"
  Write-Host "Boost mode: $boost (3=efficient, 0=disabled)"
  Write-Host "EPP: $epp (60=efficient, 100=max perf)"
  Write-Host "Max state: $state %"
  Write-Host "Governor: $(if ($paused) { 'PAUSED (fan-save active)' } else { 'ACTIVE' })"
  Write-Host "Fan-save: $(if ($boost -eq 3 -and $epp -eq 60 -and $paused) { 'ACTIVE' } else { 'INACTIVE' })"
}

switch ($Mode) {
  'save' {
    # Apply efficient settings
    $g = '1c34d62b-115d-4e7b-abb7-f19a12b8159e'
    $sub = '54533251-82be-4824-96c1-47b60b740d00'
    powercfg /setacvalueindex $g $sub 'be337238-0d82-4146-a960-4f3749d470c7' 3 | Out-Null
    powercfg /setacvalueindex $g $sub '36687f9e-e3a5-4dbf-b1dc-15eb381c6863' 60 | Out-Null
    powercfg /setacvalueindex $g $sub 'bc5038f7-23e0-4960-96da-33abaf5935ec' 100 | Out-Null
    powercfg /setactive $g | Out-Null
    # Pause governor
    New-Item $pauseFlag -ItemType File -Force | Out-Null
    Write-Host "Fan-save mode ACTIVATED"
    Write-Host "  boost=3, epp=60, state=100, governor paused"
    Write-Host "  CPU power reduced -> less heat -> less fan"
    Show-Status
  }
  'resume' {
    Remove-Item $pauseFlag -ErrorAction SilentlyContinue
    $g = '1c34d62b-115d-4e7b-abb7-f19a12b8159e'
    powercfg /setactive $g | Out-Null
    Write-Host "Fan-save mode DEACTIVATED - governor resumed"
    Show-Status
  }
  'status' {
    Show-Status
  }
}