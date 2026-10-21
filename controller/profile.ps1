param(
  [ValidateSet('show', 'stock', 'efficient', 'noturbo', 'floor', 'resume')]
  [string]$Mode = 'show'
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$stateFile = Join-Path $root 'state.json'
$pauseFlag = Join-Path $root 'paused.flag'
$cfg = Get-Content (Join-Path $root 'config.json') -Raw | ConvertFrom-Json
. (Join-Path $root 'thermal-policy.ps1')

$SUB = '54533251-82be-4824-96c1-47b60b740d00'        # SUB_PROCESSOR
$BOOST = 'be337238-0d82-4146-a960-4f3749d470c7'      # PERFBOOSTMODE
$EPP = '36687f9e-e3a5-4dbf-b1dc-15eb381c6863'        # PERFEPP
$MAXSTATE = 'bc5038f7-23e0-4960-96da-33abaf5935ec'   # PROCTHROTTLEMAX
$COOLPOL = '94d3a615-a899-4ac5-ae2b-e4d8f634367f'    # SYSCOOLPOL
$STOCK = '381b4222-f694-41f0-9685-ff5bb260df2e'

function Get-ActiveScheme {
  ((powercfg /getactivescheme) -replace '.*GUID: ([a-f0-9-]+).*', '$1')
}

function Get-QuietScheme {
  $line = (powercfg /list) | Where-Object { $_ -match [regex]::Escape($cfg.schemeName) } | Select-Object -First 1
  if ($line -and $line -match '([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})') { return $Matches[1] }
  return $null
}

function Ensure-QuietScheme {
  $g = Get-QuietScheme
  if (-not $g) {
    $out = powercfg /duplicatescheme $STOCK
    $g = ($out | Select-String -Pattern '([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})').Matches[0].Groups[1].Value
    powercfg /changename $g $cfg.schemeName 'Power profile managed by quiet-vivobook' | Out-Null
  }
  return $g
}

function Set-Value($scheme, $sub, $setting, $ac, $dc) {
  powercfg /setacvalueindex $scheme $sub $setting $ac | Out-Null
  powercfg /setdcvalueindex $scheme $sub $setting $dc | Out-Null
}

function Show {
  $g = Get-QuietScheme
  $last = Get-Content (Join-Path $root $cfg.telemetryFile) | Select-Object -Last 1
  $current = if ($last -and $last -notmatch '^time,') { ($last -split ',')[5] } else { '?' }
  "governor  : $(if (Test-Path $pauseFlag) { 'PAUSED' } else { 'active' })"
  "profile   : $current"
  "scheme    : $(powercfg /getactivescheme)"
  if (-not $g) { return }
  $base = "HKLM:\SYSTEM\CurrentControlSet\Control\Power\User\PowerSchemes\$g\$SUB"
  foreach ($pair in @(@('boost mode', $BOOST), @('EPP', $EPP), @('max state', $MAXSTATE), @('cooling', $COOLPOL))) {
    $k = Join-Path $base $pair[1]
    $p = Get-ItemProperty -Path $k -ErrorAction SilentlyContinue
    "{0,-10} AC={1} DC={2}" -f $pair[0],
      $(if ($null -ne $p.ACSettingIndex) { $p.ACSettingIndex } else { '-' }),
      $(if ($null -ne $p.DCSettingIndex) { $p.DCSettingIndex } else { '-' })
  }
}

function Apply-Profile($p) {
  $g = Ensure-QuietScheme
  Set-Value $g $SUB $BOOST $p.boost $p.boost
  Set-Value $g $SUB $EPP $p.epp $p.epp
  Set-Value $g $SUB $MAXSTATE $p.state $p.state
  Set-Value $g $SUB $COOLPOL 1 1
  powercfg /setactive $g | Out-Null
  # manual override must not be undone by the governor five seconds later
  New-Item $pauseFlag -ItemType File -Force | Out-Null
  "applied: $($p.id)  (boost=$($p.boost) epp=$($p.epp) state=$($p.state))"
  "governor paused -- run 'profile.ps1 -Mode resume' to hand control back"
  Show
}

switch ($Mode) {
  'show' { Show }

  'resume' {
    Remove-Item $pauseFlag -ErrorAction SilentlyContinue
    # The pause path may have switched the active scheme away from ours.
    # Re-activate before handing control back or the governor will write
    # settings into a scheme nobody is using.
    $g = Get-QuietScheme
    if ($g) { powercfg /setactive $g | Out-Null }
    # Quiet means quiet fan curve, not just a quiet power scheme.
    $therm = if ($null -ne $cfg.thermalPolicyMode) { [int]$cfg.thermalPolicyMode } else { 1 }
    $null = Set-ThermalMode $therm
    "governor resumed"
    Show
  }

  'stock' {
    if (-not (Test-Path $stateFile)) {
      @{ original_scheme = (Get-ActiveScheme); created = (Get-Date).ToString('s') } | ConvertTo-Json | Set-Content $stateFile -Encoding UTF8
    }
    New-Item $pauseFlag -ItemType File -Force | Out-Null
    $orig = (Get-Content $stateFile -Raw | ConvertFrom-Json).original_scheme
    powercfg /setactive $orig | Out-Null
    $null = Set-ThermalMode (Get-ThermalBaseline)
    "switched to stock scheme $orig  (governor paused, fan policy restored)"
  }

  default {
    $p = $cfg.profiles | Where-Object { $_.id -eq $Mode } | Select-Object -First 1
    if (-not $p) { throw "profile '$Mode' not found in config.json" }
    Apply-Profile $p
  }
}
