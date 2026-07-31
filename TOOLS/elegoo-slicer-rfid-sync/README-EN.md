# Elegoo Slicer RFID brand synchronization

[Cesky](README-CZ.md) | [English](README-EN.md)

This add-on fixes custom CANVAS RFID brand imports in Elegoo Slicer. It is
verified with Elegoo Slicer `1.5.2.2`, Centauri Carbon firmware `1.4.46`, and
OpenCentauri `0.4.0`.

The firmware and NFC writing procedure is covered by the
[complete English guide](../../docs/RFID-END-TO-END-EN.md).

## Why the printer was originally invisible

The blocking value was not the user-visible printer name. It was the SDCP
`FirmwareVersion` field. Elegoo Slicer rejected the OpenCentauri value
`V0.4.0-d` and therefore did not offer filament import. The firmware patch now
reports `V1.4.46` only to the Slicer through UDP discovery, WebSocket
attributes, and SDCP `Cmd 1`. The real OpenCentauri version remains available
to the display, logs, and OTA code.

The `patched` edition enables this fix with
`SPOOF_SLICER_FIRMWARE_VERSION=true`. Its
[technical documentation](../../oc-patches/cc1-app/spoof-slicer-firmware-version/README.md)
is stored next to the implementation.

## Why a user profile is not enough

MMS synchronization only accepts a compatible system base profile with the
same internal `filament_id` and exact preset name. A normal user profile named
`Prusament PLA @ECC` inherits its parent's ID, so the synchronization code
cannot select it automatically.

The installer:

- adds a system `Prusament PLA @ECC` profile with ID `PRSPLA00`;
- maps CANVAS vendor `Prusament` plus type `PLA` to that profile;
- maps `Generic` plus `PETG` to compatible `Generic PETG @Elegoo`;
- adds Centauri Carbon 0.4 mm compatibility to Generic PETG;
- removes only the conflicting user copy of the Prusament profile;
- creates a complete backup of every affected file before changing it.

Original ELEGOO RFID tags and profiles remain unchanged.

## Installation

1. Close every Elegoo Slicer instance.
2. Open PowerShell.
3. From the repository root, run:

```powershell
powershell -ExecutionPolicy Bypass -File `
  .\TOOLS\elegoo-slicer-rfid-sync\Install-ElegooSlicerRfidSync.ps1
```

Accept the Windows UAC prompt because the system profile and web mapping logic
are installed under `C:\Program Files\ElegooSlicer`.

Open Elegoo Slicer, choose **Sync filaments with MMS**, and confirm **Sync**.
The current test setup should produce:

| Tray | Profile |
| --- | --- |
| A1 | ELEGOO PLA |
| A2 | Prusament PLA |
| A3 | Generic PETG |

Backups are stored under:

```text
%APPDATA%\ElegooSlicer\rfid-sync-backups\
```

An Elegoo Slicer update may replace files under `Program Files`. Run the
installer again after updating. The installer safely refuses versions other
than `1.5.2.2`.

## Validation

Run the read-only validator after installation:

```powershell
powershell -ExecutionPolicy Bypass -File `
  .\TOOLS\elegoo-slicer-rfid-sync\Test-ElegooSlicerRfidSync.ps1
```

It checks both indexes, both profiles, internal IDs, Generic PETG
compatibility, and the MMS JavaScript mapping.

## Restore the pre-install state

Close the Slicer and restore the state from before the latest installer run:

```powershell
powershell -ExecutionPolicy Bypass -File `
  .\TOOLS\elegoo-slicer-rfid-sync\Uninstall-ElegooSlicerRfidSync.ps1
```

Use `-BackupPath` to select a specific older backup.

## Verified data flow

Printer input from SDCP `Cmd 324`:

```text
A2: vendor=Prusament, filamentType=PLA, 190-230 C
```

Data sent by the synchronization dialog:

```text
filamentId=PRSPLA00
settingId=PRSPLA00
filamentPresetName=Prusament PLA @ECC
```

After synchronization, the log must not contain:

```text
PresetBundle::sync_ams_list: filament_id ... not found
```
