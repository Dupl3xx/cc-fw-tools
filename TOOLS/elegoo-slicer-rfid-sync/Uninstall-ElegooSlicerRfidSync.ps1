[CmdletBinding()]
param(
    [string]$SlicerRoot = 'C:\Program Files\ElegooSlicer',
    [string]$ElegooDataRoot = (Join-Path $env:APPDATA 'ElegooSlicer'),
    [string]$BackupPath = '',
    [switch]$NoElevation
)

$ErrorActionPreference = 'Stop'

function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

$resolvedSlicerRoot = [IO.Path]::GetFullPath($SlicerRoot)
$programFilesRoot = [IO.Path]::GetFullPath('C:\Program Files')
$needsElevation = $resolvedSlicerRoot.StartsWith(
    $programFilesRoot,
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
    if ($BackupPath) {
        $arguments += @('-BackupPath', "`"$BackupPath`"")
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
    throw 'Close every Elegoo Slicer window before restoring the backup.'
}

if (-not $BackupPath) {
    $backupParent = Join-Path $ElegooDataRoot 'rfid-sync-backups'
    $latest = Get-ChildItem -LiteralPath $backupParent -Directory -ErrorAction SilentlyContinue |
        Sort-Object Name -Descending |
        Select-Object -First 1
    if (-not $latest) {
        throw "No RFID synchronization backup found under $backupParent"
    }
    $BackupPath = $latest.FullName
}

$manifestPath = Join-Path $BackupPath 'backup-manifest.json'
if (-not (Test-Path -LiteralPath $manifestPath)) {
    throw "Backup manifest does not exist: $manifestPath"
}
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
if ($manifest.schema -ne 1) {
    throw "Unsupported backup manifest schema: $($manifest.schema)"
}

$programProfile = Join-Path $resolvedSlicerRoot 'resources\profiles\Elegoo\filament\ECC\Prusament PLA @ECC.json'
$dataProfile = Join-Path $ElegooDataRoot 'system\Elegoo\filament\ECC\Prusament PLA @ECC.json'
$userProfile = Join-Path $ElegooDataRoot 'user\default\filament\base\Prusament PLA @ECC.json'
$userInfo = Join-Path $ElegooDataRoot 'user\default\filament\base\Prusament PLA @ECC.info'

$backedUpSources = @($manifest.files | ForEach-Object { $_.source })
foreach ($path in @($programProfile, $dataProfile, $userProfile, $userInfo)) {
    if ($backedUpSources -notcontains $path -and (Test-Path -LiteralPath $path)) {
        Remove-Item -LiteralPath $path -Force
    }
}

foreach ($entry in $manifest.files) {
    $backupFile = Join-Path $BackupPath $entry.backup
    if (-not (Test-Path -LiteralPath $backupFile)) {
        throw "Backup file listed in manifest is missing: $backupFile"
    }
    $parent = Split-Path -Parent $entry.source
    if (-not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    Copy-Item -LiteralPath $backupFile -Destination $entry.source -Force
}

Write-Host "Elegoo Slicer RFID synchronization restored from: $BackupPath"
