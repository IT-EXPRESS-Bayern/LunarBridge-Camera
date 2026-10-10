# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 IT-EXPRESS Bayern
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$OutputPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# Device instance paths, location paths, serials, friendly names and usernames
# are never written. Reading PnP metadata does not open a camera stream.
function Select-PublicHardwareIds {
    param([object]$Values)
    $allowed = @()
    foreach ($candidate in @($Values) | Select-Object -First 32) {
        if ($candidate -isnot [string] -or $candidate.Length -gt 160) { continue }
        $upper = $candidate.ToUpperInvariant()
        if ($upper -match '^PCI\\VEN_[0-9A-F]{4}&DEV_[0-9A-F]{4}(&SUBSYS_[0-9A-F]{8})?(&REV_[0-9A-F]{2})?(&CC_[0-9A-F]{4,6})?$' -or
            $upper -match '^VIDEO\\VEN_[0-9A-F]{4}&DEV_[0-9A-F]{4}(&SUBSYS_[0-9A-F]{8})?(&REV_[0-9A-F]{2})?&INT3480$' -or
            $upper -match '^USB\\VID_[0-9A-F]{4}&PID_[0-9A-F]{4}(&REV_[0-9A-F]{4})?(&MI_[0-9A-F]{2})?$' -or
            $upper -match '^USB\\(COMPAT_VID_[0-9A-F]{4}&)?CLASS_[0-9A-F]{2}(&SUBCLASS_[0-9A-F]{2})?(&PROT_[0-9A-F]{2})?$' -or
            $upper -match '^(ACPI\\|\*)?(OVTI02E1|INT3472|INT3480|HIMX1092)$' -or
            $upper -match '^ACPI\\VEN_(OVTI|INT)&DEV_(02E1|3472|3480)$') {
            $allowed += $upper
        }
    }
    return @($allowed | Select-Object -Unique)
}

function Read-PropertyValue {
    param([object[]]$Properties, [string]$Key)
    $found = @($Properties | Where-Object KeyName -eq $Key)
    if ($found.Count -eq 1) { return $found[0].Data }
    return $null
}

$collectionErrors = @()
$records = @()
try {
    $candidates = @(Get-PnpDevice -PresentOnly | Where-Object {
        $_.Class -in @('Camera','Image') -or
        $_.InstanceId -match '^PCI\\VEN_8086&DEV_645D' -or
        $_.InstanceId -match '^ACPI\\(VEN_)?(OVTI|HIMX|INT3472|INT&DEV_3472)' -or
        $_.InstanceId -match '^VIDEO\\' -or
        $_.InstanceId -match '^USB\\VID_0BDA&PID_9201'
    })
} catch {
    $candidates = @()
    $collectionErrors += 'enumeration_failed'
}
if ($candidates.Count -gt 512) { $collectionErrors += 'record_limit_reached' }

foreach ($device in $candidates | Select-Object -First 512) {
    try {
        $properties = @(Get-PnpDeviceProperty -InstanceId $device.InstanceId -ErrorAction Stop)
    } catch {
        $collectionErrors += 'property_read_failed'
        continue
    }
    $hardware = Select-PublicHardwareIds (Read-PropertyValue $properties 'DEVPKEY_Device_HardwareIds')
    $compatible = Select-PublicHardwareIds (Read-PropertyValue $properties 'DEVPKEY_Device_CompatibleIds')
    $service = Read-PropertyValue $properties 'DEVPKEY_Device_Service'
    if ($service -notin @('camera','OV02E10','iaisp64_lnl','iactrllogic','usbvideo','USBSTOR')) { $service = $null }
    $version = Read-PropertyValue $properties 'DEVPKEY_Device_DriverVersion'
    if ($version -isnot [string] -or $version -notmatch '^\d{1,8}(\.\d{1,8}){1,4}$') { $version = $null }
    $inf = Read-PropertyValue $properties 'DEVPKEY_Device_DriverInfPath'
    if ($inf -isnot [string] -or $inf -notmatch '^(oem\d{1,6}|usbvideo|usbstor)\.inf$') { $inf = $null }
    $problem = Read-PropertyValue $properties 'DEVPKEY_Device_ProblemCode'
    $records += [pscustomobject]@{
        hardware_ids = @($hardware)
        compatible_ids = @($compatible)
        service = $service
        driver = @{version=$version;inf=$inf}
        problem_code = $problem
    }
}

$capture = [ordered]@{
    schema_version = 1
    platform = 'windows'
    devices = @($records)
    collection_errors = @($collectionErrors | Select-Object -Unique)
}
$resolvedOutput = [IO.Path]::GetFullPath($OutputPath)
$outputDirectory = [IO.Path]::GetDirectoryName($resolvedOutput)
if (-not [IO.Directory]::Exists($outputDirectory)) { [IO.Directory]::CreateDirectory($outputDirectory) | Out-Null }
[IO.File]::WriteAllText($resolvedOutput, ($capture | ConvertTo-Json -Depth 8) + [Environment]::NewLine, (New-Object System.Text.UTF8Encoding($false)))
Write-Output ('Kamerametadaten geschrieben: {0} Geräte; {1} Fehlercodes.' -f $records.Count, $capture.collection_errors.Count)
