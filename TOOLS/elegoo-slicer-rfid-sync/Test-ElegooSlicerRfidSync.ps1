[CmdletBinding()]
param(
    [string]$SlicerRoot = 'C:\Program Files\ElegooSlicer',
    [string]$ElegooDataRoot = (Join-Path $env:APPDATA 'ElegooSlicer'),
    [switch]$AllowUnsupportedVersion
)

$ErrorActionPreference = 'Stop'
$checks = @()

function Add-Check {
    param(
        [string]$Name,
        [bool]$Passed,
        [string]$Detail
    )

    $script:checks += [pscustomobject]@{
        Check = $Name
        Passed = $Passed
        Detail = $Detail
    }
}

function Read-Json {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        return $null
    }
    return Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
}

$executable = Join-Path $SlicerRoot 'elegoo-slicer.exe'
$programIndexPath = Join-Path $SlicerRoot 'resources\profiles\Elegoo.json'
$programProfilePath = Join-Path $SlicerRoot 'resources\profiles\Elegoo\filament\ECC\Prusament PLA @ECC.json'
$programPetgPath = Join-Path $SlicerRoot 'resources\profiles\Elegoo\filament\Generic\Generic PETG @Elegoo.json'
$syncJsPath = Join-Path $SlicerRoot 'resources\web\printer\filament_sync\filament_sync.js'
$dataIndexPath = Join-Path $ElegooDataRoot 'system\Elegoo.json'
$dataProfilePath = Join-Path $ElegooDataRoot 'system\Elegoo\filament\ECC\Prusament PLA @ECC.json'
$dataPetgPath = Join-Path $ElegooDataRoot 'system\Elegoo\filament\Generic\Generic PETG @Elegoo.json'

$version = if (Test-Path -LiteralPath $executable) {
    (Get-Item -LiteralPath $executable).VersionInfo.ProductVersion
} else {
    ''
}
$versionPassed = $version -eq '1.5.2.2' -or $AllowUnsupportedVersion
$versionDetail = "Found: $version"
if ($AllowUnsupportedVersion -and $version -ne '1.5.2.2') {
    $versionDetail += ' (unsupported version explicitly allowed)'
}
Add-Check 'Elegoo Slicer 1.5.2.2' $versionPassed $versionDetail

$programIndex = Read-Json $programIndexPath
$programEntries = if ($programIndex) {
    @($programIndex.filament_list | Where-Object { $_.name -eq 'Prusament PLA @ECC' })
} else {
    @()
}
Add-Check 'Program profile index' ($programEntries.Count -eq 1) "Entries: $($programEntries.Count)"

$dataIndex = Read-Json $dataIndexPath
$dataEntries = if ($dataIndex) {
    @($dataIndex.filament_list | Where-Object { $_.name -eq 'Prusament PLA @ECC' })
} else {
    @()
}
Add-Check 'User-data profile index' ($dataEntries.Count -eq 1) "Entries: $($dataEntries.Count)"

foreach ($item in @(
    @{ Name = 'Program Prusament profile'; Path = $programProfilePath },
    @{ Name = 'User-data Prusament profile'; Path = $dataProfilePath }
)) {
    $profile = Read-Json $item.Path
    $passed = $null -ne $profile -and
        $profile.filament_id -eq 'PRSPLA00' -and
        $profile.setting_id -eq 'PRSPLA00' -and
        $profile.inherits -eq 'Elegoo PLA @ECC' -and
        $profile.compatible_printers -contains 'Elegoo Centauri Carbon 0.4 nozzle'
    $detail = if ($profile) {
        "ID=$($profile.filament_id), parent=$($profile.inherits)"
    } else {
        'Missing'
    }
    Add-Check $item.Name $passed $detail
}

foreach ($item in @(
    @{ Name = 'Program Generic PETG compatibility'; Path = $programPetgPath },
    @{ Name = 'User-data Generic PETG compatibility'; Path = $dataPetgPath }
)) {
    $profile = Read-Json $item.Path
    $passed = $null -ne $profile -and
        $profile.compatible_printers -contains 'Elegoo Centauri Carbon 0.4 nozzle'
    Add-Check $item.Name $passed $(if ($profile) { 'Centauri Carbon 0.4 present' } else { 'Missing' })
}

$syncJs = if (Test-Path -LiteralPath $syncJsPath) {
    [IO.File]::ReadAllText($syncJsPath)
} else {
    ''
}
$jsPassed = $syncJs.Contains('OpenCentauri RFID profile mapping') -and
    $syncJs.Contains("filamentId: 'PRSPLA00'") -and
    $syncJs.Contains('this.mmsInfo = this.normalizeMmsProfiles(response.mmsInfo);')
Add-Check 'MMS JavaScript mapping' $jsPassed $(if ($syncJs) { 'Mapping inspected' } else { 'Missing' })

$checks | Format-Table -AutoSize
$failed = @($checks | Where-Object { -not $_.Passed })
if ($failed.Count -gt 0) {
    Write-Error "$($failed.Count) RFID synchronization check(s) failed."
    exit 1
}

Write-Host 'All Elegoo Slicer RFID synchronization checks passed.'
