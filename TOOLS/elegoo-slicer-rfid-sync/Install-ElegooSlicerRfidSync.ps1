[CmdletBinding()]
param(
    [string]$SlicerRoot = 'C:\Program Files\ElegooSlicer',
    [string]$ElegooDataRoot = (Join-Path $env:APPDATA 'ElegooSlicer'),
    [switch]$NoElevation,
    [switch]$ForceUnsupportedVersion
)

$ErrorActionPreference = 'Stop'

function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Save-JsonFile {
    param(
        [Parameter(Mandatory)]
        [string]$Path,
        [Parameter(Mandatory)]
        [object]$Value
    )

    $json = $Value | ConvertTo-Json -Depth 100
    [IO.File]::WriteAllText($Path, $json + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))
}

function Add-FilamentIndexEntry {
    param(
        [Parameter(Mandatory)]
        [string]$Path
    )

    $index = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
    $exists = @($index.filament_list | Where-Object { $_.name -eq 'Prusament PLA @ECC' }).Count -gt 0
    if (-not $exists) {
        $index.filament_list += [pscustomobject]@{
            name = 'Prusament PLA @ECC'
            sub_path = 'filament/ECC/Prusament PLA @ECC.json'
        }
        Save-JsonFile -Path $Path -Value $index
    }
}

function Add-CompatiblePrinter {
    param(
        [Parameter(Mandatory)]
        [string]$Path
    )

    $profile = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
    $printer = 'Elegoo Centauri Carbon 0.4 nozzle'
    if ($profile.compatible_printers -notcontains $printer) {
        $profile.compatible_printers = @($printer) + @($profile.compatible_printers)
        Save-JsonFile -Path $Path -Value $profile
    }
}

function Patch-FilamentSyncJavaScript {
    param(
        [Parameter(Mandatory)]
        [string]$Path
    )

    $source = [IO.File]::ReadAllText($Path)
    $marker = 'OpenCentauri RFID profile mapping'
    if ($source.Contains($marker)) {
        return
    }

    $anchor = '        // Request printer filament info when printer is selected'
    if (-not $source.Contains($anchor)) {
        throw "Unsupported filament_sync.js: insertion anchor was not found."
    }

    $method = @'
        // OpenCentauri RFID profile mapping
        normalizeMmsProfiles(mmsInfo) {
            for (const mms of mmsInfo?.mmsList || []) {
                for (const tray of mms.trayList || []) {
                    const vendor = String(tray.vendor || '').trim().toLowerCase();
                    const filamentType = String(tray.filamentType || '').trim().toUpperCase();

                    if ((vendor === 'prusament' || vendor === 'prusa polymers') && filamentType === 'PLA') {
                        Object.assign(tray, {
                            filamentId: 'PRSPLA00',
                            settingId: 'PRSPLA00',
                            filamentPresetName: 'Prusament PLA @ECC',
                            filamentPresetAlias: 'Prusament PLA'
                        });
                    } else if (vendor === 'generic' && filamentType === 'PETG') {
                        Object.assign(tray, {
                            filamentId: 'GPETGB00',
                            settingId: 'GFSG99',
                            filamentPresetName: 'Generic PETG @Elegoo',
                            filamentPresetAlias: 'Generic PETG'
                        });
                    }
                }
            }
            return mmsInfo;
        },

'@
    $source = $source.Replace($anchor, $method + $anchor)

    $assignment = '                this.mmsInfo = response.mmsInfo;'
    if (-not $source.Contains($assignment)) {
        throw "Unsupported filament_sync.js: MMS assignment was not found."
    }
    $source = $source.Replace(
        $assignment,
        '                this.mmsInfo = this.normalizeMmsProfiles(response.mmsInfo);'
    )
    [IO.File]::WriteAllText($Path, $source, [Text.UTF8Encoding]::new($false))
}

$defaultProgramFilesRoot = [IO.Path]::GetFullPath('C:\Program Files')
$resolvedSlicerRoot = [IO.Path]::GetFullPath($SlicerRoot)
$needsElevation = $resolvedSlicerRoot.StartsWith(
    $defaultProgramFilesRoot,
    [StringComparison]::OrdinalIgnoreCase
) -and -not (Test-IsAdministrator)

if ($needsElevation -and -not $NoElevation) {
    $arguments = @(
        '-NoProfile',
        '-ExecutionPolicy', 'Bypass',
        '-File', "`"$PSCommandPath`"",
        '-SlicerRoot', "`"$SlicerRoot`"",
        '-ElegooDataRoot', "`"$ElegooDataRoot`""
    )
    if ($ForceUnsupportedVersion) {
        $arguments += '-ForceUnsupportedVersion'
    }

    $process = Start-Process -FilePath 'powershell.exe' -Verb RunAs `
        -ArgumentList $arguments -Wait -PassThru
    exit $process.ExitCode
}

$running = Get-Process -Name 'elegoo-slicer' -ErrorAction SilentlyContinue |
    Where-Object {
        $_.Path -and ([IO.Path]::GetDirectoryName($_.Path) -eq $resolvedSlicerRoot)
    }
if ($running) {
    throw 'Close every Elegoo Slicer window before installing the RFID profiles.'
}

$executable = Join-Path $resolvedSlicerRoot 'elegoo-slicer.exe'
$programIndex = Join-Path $resolvedSlicerRoot 'resources\profiles\Elegoo.json'
$programProfile = Join-Path $resolvedSlicerRoot 'resources\profiles\Elegoo\filament\ECC\Prusament PLA @ECC.json'
$programGenericPetg = Join-Path $resolvedSlicerRoot 'resources\profiles\Elegoo\filament\Generic\Generic PETG @Elegoo.json'
$filamentSyncJs = Join-Path $resolvedSlicerRoot 'resources\web\printer\filament_sync\filament_sync.js'
$dataIndex = Join-Path $ElegooDataRoot 'system\Elegoo.json'
$dataProfile = Join-Path $ElegooDataRoot 'system\Elegoo\filament\ECC\Prusament PLA @ECC.json'
$dataGenericPetg = Join-Path $ElegooDataRoot 'system\Elegoo\filament\Generic\Generic PETG @Elegoo.json'
$bundledProfile = Join-Path $PSScriptRoot 'profiles\Prusament PLA @ECC.json'

$required = @(
    $executable,
    $programIndex,
    $programGenericPetg,
    $filamentSyncJs,
    $dataIndex,
    $dataGenericPetg,
    $bundledProfile
)
foreach ($path in $required) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Required file does not exist: $path"
    }
}

$version = (Get-Item -LiteralPath $executable).VersionInfo.ProductVersion
if ($version -ne '1.5.2.2' -and -not $ForceUnsupportedVersion) {
    throw "This installer is verified for Elegoo Slicer 1.5.2.2; found $version. Use -ForceUnsupportedVersion only after reviewing the file layout."
}

$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backupRoot = Join-Path $ElegooDataRoot "rfid-sync-backups\$timestamp"
New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null

$backupFiles = @(
    $programIndex,
    $programGenericPetg,
    $filamentSyncJs,
    $dataIndex,
    $dataGenericPetg
)
foreach ($path in $backupFiles) {
    $safeName = ($path -replace ':', '' -replace '[\\/]', '__')
    Copy-Item -LiteralPath $path -Destination (Join-Path $backupRoot $safeName) -Force
}

$userProfile = Join-Path $ElegooDataRoot 'user\default\filament\base\Prusament PLA @ECC.json'
$userInfo = Join-Path $ElegooDataRoot 'user\default\filament\base\Prusament PLA @ECC.info'
foreach ($path in @($userProfile, $userInfo)) {
    if (Test-Path -LiteralPath $path) {
        Copy-Item -LiteralPath $path -Destination $backupRoot -Force
        Remove-Item -LiteralPath $path -Force
    }
}

Copy-Item -LiteralPath $bundledProfile -Destination $programProfile -Force
Copy-Item -LiteralPath $bundledProfile -Destination $dataProfile -Force
Add-FilamentIndexEntry -Path $programIndex
Add-FilamentIndexEntry -Path $dataIndex
Add-CompatiblePrinter -Path $programGenericPetg
Add-CompatiblePrinter -Path $dataGenericPetg
Patch-FilamentSyncJavaScript -Path $filamentSyncJs

foreach ($path in @($programIndex, $programProfile, $programGenericPetg, $dataIndex, $dataProfile, $dataGenericPetg)) {
    $null = Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
}

Write-Host "RFID profile synchronization installed for Elegoo Slicer $version."
Write-Host "Backup: $backupRoot"
Write-Host 'Start Elegoo Slicer and run Sync filaments with MMS.'
