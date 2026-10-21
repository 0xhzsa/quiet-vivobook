param(
  [switch]$Uninstall,
  [switch]$Status
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$script = Join-Path $root 'fan-save.ps1'

# A per-user Startup-folder launcher. It runs in the user's session at logon,
# so it needs no elevation: power scheme changes and the governor pause flag
# are both user-writable. It does not touch the ASUS thermal-policy device,
# so it cannot leave a machine in a bad thermal state.
$startup = [Environment]::GetFolderPath('Startup')
$launcher = Join-Path $startup 'quiet-vivobook-fan-save.cmd'

if ($Status) {
  Write-Host "Startup launcher: $(if (Test-Path $launcher) { 'present' } else { 'absent' })"
  Write-Host "  path: $launcher"
  Write-Host ""
  & $script -Mode status
  exit 0
}

if ($Uninstall) {
  Remove-Item -LiteralPath $launcher -ErrorAction SilentlyContinue
  Write-Host "Startup launcher removed."
  Write-Host "Fan-save mode is still active for this session:"
  & $script -Mode status
  exit 0
}

# --- install -------------------------------------------------------------
$body = @"
@echo off
rem quiet-vivobook: apply the efficient power profile at logon.
rem boost=3, EPP=60, max state 100%%, governor paused.
rem Less CPU heat -> less fan. Safe to delete this file.
powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "$script" -Mode save >> "$root\fan-save.log" 2>&1
"@
[System.IO.File]::WriteAllText($launcher, $body, (New-Object System.Text.UTF8Encoding($false)))

Write-Host "Startup launcher installed: $launcher"
Write-Host "It applies the efficient profile at every logon."
Write-Host ""
& $script -Mode status
Write-Host ""
Write-Host "Remove it with:"
Write-Host "  powershell -NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -Uninstall"
