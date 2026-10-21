<#
  quiet-vivobook governor  (learned-equilibrium MPC)

  quiet-lab's control stack, rebuilt for a plant whose actuator is CPU power
  rather than fan speed:

    quiet-lab                          here
    --------------------------------   --------------------------------------
    C dT/dt = Q - H(u)(T - Tinlet)  ->  T(t) -> T_eq(p), first-order, tau=60 s
    u = fan PWM (changes H)            p = power profile (changes Q)
    learned H matrix + EKF             learned T_eq per profile (non-parametric)
    MPC, N=3, 45 s, SLSQP              MPC, N=18, 90 s, exhaustive over actions
    acoustic cost L_ref + 50log10(w)   NOT PORTABLE -- fan RPM is unreadable
    power cost sum(u^3)                ignored: saving power is a side effect

  Why the model is a response surface and not the ODE from upstream:

    H is not constant on this machine. Measured from profiles.csv and live
    telemetry, the effective heat-transfer coefficient runs 0.26 W/K at idle
    and 0.58 W/K under load -- a factor of 2.2 -- because the firmware's fan
    curve raises airflow as the die heats. A constant-parameter model is
    therefore structurally misspecified, and an RLS fit of one walks into a
    degenerate corner no matter how it is regularised. That was observed, not
    assumed: H pinned at its lower clamp, inlet temperature at 0 C.

    So the model learns the steady-state temperature of each profile directly
    -- the same quantity the upstream project learns, without forcing it
    through a linear structure the hardware does not obey. Transients use a
    first-order approach with a fixed 60 s time constant, measured from load
    tests. This is honest about being empirical.

  Requires elevation (MSR access via PawnIO).
#>

param(
  [string]$ConfigPath = (Join-Path $PSScriptRoot 'config.json'),
  [switch]$Once,
  [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$cfg = Get-Content $ConfigPath -Raw | ConvertFrom-Json
$logPath = Join-Path $PSScriptRoot $cfg.logFile
$telemetryPath = Join-Path $PSScriptRoot $cfg.telemetryFile
$modelPath = Join-Path $PSScriptRoot $cfg.modelFile
$pauseFlag = Join-Path $PSScriptRoot 'paused.flag'
$lib = Join-Path $PSScriptRoot $cfg.libPath
. (Join-Path $PSScriptRoot 'thermal-policy.ps1')

$SUB = '54533251-82be-4824-96c1-47b60b740d00'
$MAXSTATE = 'bc5038f7-23e0-4960-96da-33abaf5935ec'
$BOOST = 'be337238-0d82-4146-a960-4f3749d470c7'
$EPP = '36687f9e-e3a5-4dbf-b1dc-15eb381c6863'
$STOCK = '381b4222-f694-41f0-9685-ff5bb260df2e'

function Write-Log($msg) {
  $line = "{0},{1}" -f (Get-Date).ToString('s'), $msg
  for ($i = 0; $i -lt 6; $i++) {
    try { Add-Content -Path $logPath -Value $line -Encoding UTF8; return } catch { Start-Sleep -Milliseconds 60 }
  }
}

function Write-Telemetry($line) {
  for ($i = 0; $i -lt 6; $i++) {
    try { Add-Content -Path $telemetryPath -Value $line -Encoding UTF8; return } catch { Start-Sleep -Milliseconds 60 }
  }
}

# ---- sensor: MSRs via PawnIO -------------------------------------------------

Add-Type -Path $lib
$msr = New-Object LibreHardwareMonitor.PawnIo.IntelMsr
$affType = [LibreHardwareMonitor.Hardware.GroupAffinity]

$tjRaw = [uint64]0
if (-not $msr.ReadMsr([uint32]0x1A2, [ref]$tjRaw)) { Write-Log "FATAL cannot read TjMax"; throw "no msr" }
$tjMax = [int](($tjRaw -shr 16) -band 0xFF)

$coreCount = [int](Get-CimInstance Win32_Processor | Measure-Object NumberOfLogicalProcessors -Sum).Sum
if ($coreCount -le 0 -or $coreCount -gt 64) { $coreCount = 20 }

$raplUnit = [uint64]0
if (-not $msr.ReadMsr([uint32]0x606, [ref]$raplUnit)) { Write-Log "FATAL cannot read RAPL unit"; throw "no rapl" }
$energyUnit = 1.0 / [math]::Pow(2, [int](($raplUnit -shr 8) -band 0x1F))

$script:lastEnergy = $null
$script:lastEnergyAt = $null

function Read-Cpu {
  $maxTemp = 0; $read = 0; $sum = 0.0
  for ($i = 0; $i -lt $coreCount; $i++) {
    $eax = [uint32]0; $edx = [uint32]0
    $ga = $affType::Single([uint16]0, $i)
    if ($msr.ReadMsr([uint32]0x19C, [ref]$eax, [ref]$edx, $ga)) {
      $t = $tjMax - [int](($eax -shr 16) -band 0x7F)
      if ($t -gt $maxTemp) { $maxTemp = $t }
      $sum += $t
      $read++
    }
  }
  if ($read -eq 0) { return [pscustomobject]@{ temp = $null; avg = $null; watts = 0.0 } }

  $energy = [uint64]0
  $watts = 0.0
  $now = [DateTime]::UtcNow
  if ($msr.ReadMsr([uint32]0x611, [ref]$energy)) {
    if ($null -ne $script:lastEnergy) {
      $delta = ($energy - $script:lastEnergy) -band 0xFFFFFFFF
      $dt = ($now - $script:lastEnergyAt).TotalSeconds
      if ($dt -gt 0.2) { $watts = ($delta * $energyUnit) / $dt }
    }
    $script:lastEnergy = $energy
    $script:lastEnergyAt = $now
  }
  [pscustomobject]@{ temp = [double]$maxTemp; avg = [double]($sum / $read); watts = [double]$watts }
}

# ---- learned equilibrium surface --------------------------------------------
#
#   eq[id]  steady-state die temperature observed in that profile under load
#   q[id]   steady-state package power observed in that profile under load
#
# Seeded from profiles.csv, which was measured on this machine, then corrected
# online whenever the plant is actually sitting still.

$script:eq = @{}
$script:q = @{}
foreach ($p in $cfg.profiles) {
  $script:eq[$p.id] = [double]$p.eq
  $script:q[$p.id] = [double]$p.watts
}

function Save-Model {
  $e = @{}; $q = @{}
  foreach ($k in $script:eq.Keys) { $e[$k] = [math]::Round($script:eq[$k], 2) }
  foreach ($k in $script:q.Keys) { $q[$k] = [math]::Round($script:q[$k], 2) }
  @{ eq = $e; q = $q; updated = (Get-Date).ToString('s') } |
    ConvertTo-Json -Depth 4 | Set-Content $modelPath -Encoding UTF8
}

if (Test-Path $modelPath) {
  try {
    $m = Get-Content $modelPath -Raw | ConvertFrom-Json
    if ($m.eq) { foreach ($k in $m.eq.PSObject.Properties) { $script:eq[$k.Name] = [double]$k.Value } }
    if ($m.q) { foreach ($k in $m.q.PSObject.Properties) { $script:q[$k.Name] = [double]$k.Value } }
    $parts = @()
    foreach ($k in $script:eq.Keys) { $parts += ("{0}={1:N1}C/{2:N1}W" -f $k, $script:eq[$k], $script:q[$k]) }
    Write-Log ("model loaded: " + ($parts -join '  '))
  } catch { Write-Log "model load failed: $($_.Exception.Message)" }
}

# ---- actuator ---------------------------------------------------------------

function Get-SchemeGuid([string]$name) {
  $line = (powercfg /list) | Where-Object { $_ -match [regex]::Escape($name) } | Select-Object -First 1
  if (-not $line) { return $null }
  if ($line -match '([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})') { return $Matches[1] }
}

$scheme = Get-SchemeGuid $cfg.schemeName
if (-not $scheme) { Write-Log "FATAL scheme not found"; throw "scheme not found" }

function Set-Profile($p) {
  if ($DryRun) { return }
  foreach ($scope in 'ac', 'dc') {
    powercfg "/set${scope}valueindex" $scheme $SUB $BOOST $p.boost | Out-Null
    powercfg "/set${scope}valueindex" $scheme $SUB $MAXSTATE $p.state | Out-Null
    powercfg "/set${scope}valueindex" $scheme $SUB $EPP $p.epp | Out-Null
  }
  powercfg /setactive $scheme | Out-Null
}

$profiles = @($cfg.profiles)

function Get-Eq($p) {
  if ($script:eq.ContainsKey($p.id)) { return [double]$script:eq[$p.id] }
  return [double]$p.eq
}

# ---- controllers -------------------------------------------------------------

function Invoke-Mpc([double]$temp, [int]$currentIdx) {
  $ctrl = $cfg.controller
  $dt = [double]$cfg.pollSeconds
  $N = [int]$ctrl.horizon
  $tau = [double]$cfg.tauSeconds
  $decay = [math]::Exp(-$dt / $tau)
  $best = $currentIdx
  $bestCost = [double]::MaxValue
  $costs = @()

  for ($a = 0; $a -lt $profiles.Count; $a++) {
    $p = $profiles[$a]
    $eq = Get-Eq $p
    $t = $temp
    $cost = 0.0
    $peak = $temp
    for ($k = 1; $k -le $N; $k++) {
      $t = $eq + ($t - $eq) * $decay
      if ($t -gt $peak) { $peak = $t }
      $over = $t - [double]$cfg.targetHigh
      if ($over -gt 0) {
        $sigma = ($t - [double]$ctrl.warnTemp) / ([double]$ctrl.critTemp - [double]$ctrl.warnTemp)
        if ($sigma -lt 0) { $sigma = 0 }
        if ($sigma -gt 1) { $sigma = 1 }
        $cost += [double]$ctrl.wOver * (1 + 9 * [math]::Pow($sigma, 3)) * $over * $over
      }
    }
    $cost += [double]$ctrl.wPerf * (1.0 - [double]$p.work) * $N
    if ($a -ne $currentIdx) { $cost += [double]$ctrl.wSwitch }
    if ($peak -ge [double]$cfg.emergencyTemp) { $cost += 10000 }

    $costs += [pscustomobject]@{ id = $p.id; cost = [math]::Round($cost, 3); eq = [math]::Round($eq, 1); peak = [math]::Round($peak, 1) }
    if ($cost -lt $bestCost) { $bestCost = $cost; $best = $a }
  }
  return [pscustomobject]@{ index = $best; costs = $costs }
}

function Invoke-Hysteresis([double]$ema, [double]$temp, [double]$projected, [int]$idx, [bool]$dwellOk, $now) {
  if ((($ema -gt $cfg.targetHigh) -or ($temp -gt ($cfg.targetHigh + 2)) -or ($projected -gt ($cfg.targetHigh + 3))) -and $idx -lt $profiles.Count - 1 -and $dwellOk) {
    return $idx + 1
  }
  if (($ema -lt $cfg.targetLow) -and ($temp -lt $cfg.targetLow) -and ($projected -lt $cfg.targetLow + 2) -and $idx -gt 0) {
    if (-not $script:coldSince) { $script:coldSince = $now }
    if ((($now - $script:coldSince).TotalSeconds -ge $cfg.idleRelaxSeconds) -and $dwellOk) { return $idx - 1 }
  } else { $script:coldSince = $null }
  return $idx
}

# ---- state ------------------------------------------------------------------

try { (Get-Process -Id $PID).PriorityClass = 'AboveNormal' } catch { }

$idx = 0
for ($i = 0; $i -lt $profiles.Count; $i++) { if ($profiles[$i].id -eq $cfg.startProfile) { $idx = $i; break } }

$lastChange = (Get-Date).AddSeconds(-3600)
$script:coldSince = $null
$ema = $null
$prevEma = $null
$emaTrend = 0.0
$avgTrend = 0.0
$onAc = $true
$powerTick = 0

$prevTemp = $null
$prevAvg = $null
$prevAt = $null
$failures = 0
$switches = 0
$ready = $false
$tick = 0

Set-Profile $profiles[$idx]

# Quiet means a quiet fan curve, not just a quiet power scheme. Record the
# machine's own policy, apply ours, and put the baseline back on exit --
# including the critical-temperature exit below.
$thermalWanted = if ($null -ne $cfg.thermalPolicyMode) { [int]$cfg.thermalPolicyMode } else { 1 }
$thermalBaseline = $null
$thermalApplied = $false
$thermalCurrent = Get-ThermalMode
if ($null -ne $thermalCurrent) {
  # The baseline is the machine's own policy, recorded once. Never overwrite it
  # on a restart: a restart that lands on our applied mode would otherwise
  # record that mode as "stock".
  if (Test-Path $script:ThermalStatePath) {
    $thermalBaseline = Get-ThermalBaseline
  } else {
    $thermalBaseline = $thermalCurrent
    Save-ThermalBaseline $thermalCurrent
  }
  if (-not $DryRun) { $thermalApplied = Set-ThermalMode $thermalWanted }
  Write-Log ("thermal current={0} baseline={1} wanted={2} applied={3}" -f $thermalCurrent, $thermalBaseline, $thermalWanted, $thermalApplied)
}
if (-not (Test-Path $telemetryPath)) { "time,temp_c,watts,ema,tss,profile,controller" | Set-Content $telemetryPath -Encoding UTF8 }
try {
  $bs = (Get-CimInstance Win32_Battery -ErrorAction SilentlyContinue | Select-Object -First 1).BatteryStatus
  $onAc = ($null -eq $bs) -or ($bs -ne 1)
} catch { }
Write-Log ("start scheme={0} profile={1} tjmax={2} cores={3} power={4}" -f $scheme, $profiles[$idx].id, $tjMax, $coreCount, $(if ($onAc) { 'AC' } else { 'battery' }))

while ($true) {
  try {
    if (Test-Path $pauseFlag) {
      if ($Once) { Write-Log "paused, nothing to do"; break }
      Start-Sleep -Seconds $cfg.pollSeconds
      continue
    }

    $r = Read-Cpu
    if ($null -eq $r.temp -or [double]$r.temp -le 0) {
      $failures++
      Write-Log "sensor=null failures=$failures"
      if ($failures -ge 3) {
        Write-Log "SENSOR LOST -> restoring stock"
        Set-Profile $profiles[0]
        powercfg /setactive $STOCK | Out-Null
        break
      }
      Start-Sleep -Seconds $cfg.pollSeconds
      continue
    }
    $failures = 0

    $temp = [double]$r.temp
    $avgTemp = [double]$r.avg
    $watts = [double]$r.watts
    $now = Get-Date
    $priorAvg = $prevAvg
    $priorTemp = $prevTemp
    $dtNow = if ($null -ne $prevAt) { ($now - $prevAt).TotalSeconds } else { 0 }
    $prevAvg = $avgTemp
    $prevTemp = $temp
    $prevAt = $now

    $ema = if ($null -eq $ema) { $temp } else { (1 - $cfg.emaAlpha) * $ema + $cfg.emaAlpha * $temp }
    if ($null -ne $prevEma -and $dtNow -gt 0.5) {
      $d = ($ema - $prevEma) / $dtNow
      $emaTrend = 0.6 * $emaTrend + 0.4 * $d
    }
    $prevEma = $ema

    if ($null -ne $priorAvg -and $dtNow -gt 0.5) {
      $d2 = ($avgTemp - $priorAvg) / $dtNow
      $avgTrend = 0.6 * $avgTrend + 0.4 * $d2
    }

    # Learn equilibrium only above the idle power band. Idle package power on
    # this chip measures 5-9 W, so a 12 W floor keeps idle samples out of the
    # steady-state estimate without depending on WMI load counters.
    $underLoad = ($watts -gt 12)

    # Refresh the power source every ~60 s. All profile measurements were taken on
    # AC; on battery this chassis caps itself hard, so DC data describes a different
    # plant. Learning is AC-gated so DC operation cannot corrupt the AC model.
    $powerTick++
    if ($powerTick % 12 -eq 0) {
      try {
        $battStatus = (Get-CimInstance Win32_Battery -ErrorAction SilentlyContinue | Select-Object -First 1).BatteryStatus
        $wasAc = $onAc
        $onAc = ($null -eq $battStatus) -or ($battStatus -ne 1)
        if ($wasAc -ne $onAc) {
          Write-Log ("power source changed: {0} (learning {1})" -f $(if ($onAc) { 'AC' } else { 'battery' }), $(if ($onAc) { 'enabled' } else { 'suspended' }))
        }
      } catch { }
    }

    # Learn this profile's equilibrium whenever the die temperature has stopped
    # moving under load. The trend is already smoothed, so this asks a physical
    # question ("is it settling?") rather than a statistical one ("did two
    # consecutive samples happen to match?"), which the bursty workload made
    # impossible to satisfy.
    $calm = ([math]::Abs($avgTrend) -le [double]$cfg.steadyTrendCPerS)
    if ($onAc -and $underLoad -and $calm) {
      $id = $profiles[$idx].id
      $script:eq[$id] = 0.9 * $script:eq[$id] + 0.1 * $avgTemp
      $script:q[$id] = 0.9 * $script:q[$id] + 0.1 * $watts
    }

    $dwellOk = (($now - $lastChange).TotalSeconds -ge $cfg.dwellSeconds)
    $action = "hold"
    $target = $idx
    $controller = "mpc"

    if ($ema -ge $cfg.criticalTemp) {
      Set-Profile $profiles[-1]
      Write-Log ("CRITICAL ema={0} temp={1} w={2} -> restoring stock and stopping" -f [math]::Round($ema,1), $temp, [math]::Round($watts,1))
      powercfg /setactive $STOCK | Out-Null
      break
    }
    elseif ($ema -ge $cfg.emergencyTemp -and $idx -lt $profiles.Count - 1) {
      $target = $profiles.Count - 1
      $action = "emergency-down"
    }
    else {
      $startTemp = $ema + [math]::Max(0.0, $emaTrend) * [double]$cfg.predictiveWindow
      $decision = Invoke-Mpc $startTemp $idx
      $target = if ($dwellOk) { $decision.index } else { $idx }
      if ($target -ne $idx) { $action = if ($target -gt $idx) { "mpc-down" } else { "mpc-up" } }
      Write-Log ("mpc: " + (($decision.costs | ForEach-Object { "$($_.id) eq=$($_.eq) cost=$($_.cost)" }) -join '  '))
    }

    if ($target -ne $idx) {
      $idx = $target
      Set-Profile $profiles[$idx]
      $lastChange = $now
      $script:coldSince = $null
      $switches++
      Write-Log ("{0} ema={1} temp={2} w={3} profile={4}" -f $action, [math]::Round($ema,1), [math]::Round($temp,1), [math]::Round($watts,1), $profiles[$idx].id)
    }

    $tss = Get-Eq $profiles[$idx]
    Write-Telemetry ("{0},{1},{2},{3},{4},{5},{6}" -f (Get-Date).ToString('s'),
      [math]::Round($temp,1), [math]::Round($watts,1), [math]::Round($ema,1),
      [math]::Round($tss,1), $profiles[$idx].id, $controller)

    $tick++
    if ($tick % 12 -eq 0) { Save-Model }

    if ($Once) { break }
    Start-Sleep -Seconds $cfg.pollSeconds
  }
  catch {
    $failures++
    $lineInfo = $_.InvocationInfo
    Write-Log ("ERROR {0} @line {1}: {2}" -f $_.Exception.Message, $lineInfo.ScriptLineNumber, ($lineInfo.Line -replace '\s+', ' ').Trim())
    if ($failures -ge 3 -or $Once) { Set-Profile $profiles[0]; break }
    Start-Sleep -Seconds $cfg.pollSeconds
  }
}

Save-Model
if ($thermalApplied) { $null = Set-ThermalMode $thermalBaseline }
$msr.Close()
Set-Profile $profiles[0]
Write-Log ("exit, profile restored to {0}, switches={1}" -f $profiles[0].id, $switches)
