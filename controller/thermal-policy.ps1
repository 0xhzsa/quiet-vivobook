# ASUS thermal policy, shared by the governor and profile.ps1.
#
# Device 0x00110019, VIVO encoding (NOT the generic ASUS one):
#   0 = balanced   1 = silent   2 = overboost
#
# The WMI call needs elevation. Every function degrades to a null/false
# result instead of throwing, so callers can keep running without fan control.

$script:ThermalDeviceId = [uint32]0x00110019
$script:ThermalWmiPath = 'root\wmi:AsusAtkWmi_WMNB.InstanceName="{0}"' -f 'ACPI\PNP0C14\ATK_0'.Replace('\', '\\')
$script:ThermalStatePath = Join-Path $PSScriptRoot 'thermal-state.json'

function Get-ThermalMode {
  try {
    $o = [wmi]$script:ThermalWmiPath
    $in = $o.PSBase.GetMethodParameters('DSTS')
    $in.Device_ID = $script:ThermalDeviceId
    $out = $o.PSBase.InvokeMethod('DSTS', $in, $null)
    $raw = [int64]$out['device_status']
    if ($raw -eq 4294967294) { return $null }
    return [int]($raw -band 0xFFFF)
  } catch { return $null }
}

function Set-ThermalMode([int]$Mode) {
  try {
    $o = [wmi]$script:ThermalWmiPath
    $in = $o.PSBase.GetMethodParameters('DEVS')
    $in.Control_status = [uint32]$Mode
    $in.Device_ID = $script:ThermalDeviceId
    $out = $o.PSBase.InvokeMethod('DEVS', $in, $null)
    return ([int64]$out['result'] -eq 1)
  } catch { return $false }
}

function Save-ThermalBaseline([int]$Mode) {
  try {
    @{ baseline = $Mode; saved = (Get-Date).ToString('s') } | ConvertTo-Json | Set-Content $script:ThermalStatePath -Encoding UTF8
  } catch { }
}

function Get-ThermalBaseline {
  try {
    if (Test-Path $script:ThermalStatePath) {
      return [int](Get-Content $script:ThermalStatePath -Raw | ConvertFrom-Json).baseline
    }
  } catch { }
  return 0
}
