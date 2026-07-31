# Complete RFID solution for CANVAS and Elegoo Slicer

[Cesky](RFID-END-TO-END-CZ.md) | [English](RFID-END-TO-END-EN.md)

This document covers the complete verified path from writing a custom NFC tag
through CANVAS and the Centauri Carbon display to automatic profile selection
in Elegoo Slicer.

## Verified stack

| Component | Verified version |
| --- | --- |
| Printer | ELEGOO Centauri Carbon 1 |
| Material system | CANVAS |
| Base ELEGOO firmware | `1.4.46` |
| OpenCentauri | `0.4.0` |
| Elegoo Slicer | `1.5.2.2` |
| RFID tag | NTAG213 |
| Slicer transport | WebSocket, SDCP `Cmd 324` |

Firmware `1.4.49` is not supported by this binary patch. The patcher validates
the application hash and original instructions and refuses unknown firmware.

## Repository contents

### Firmware

- a resolver for 70 brand names;
- compatibility with every original ELEGOO RFID tag;
- safe Generic fallback for unknown codes;
- 15 main materials and 50 subtypes with temperatures from firmware `1.4.46`;
- a generator for all nine NTAG213 pages;
- read-only CANVAS verification over SDCP;
- compatible `V1.4.46` reporting to Elegoo Slicer.

### Elegoo Slicer

- system profile `Prusament PLA @ECC`;
- internal `filament_id` and `setting_id` `PRSPLA00`;
- mapping for `vendor=Prusament` plus `filamentType=PLA`;
- Centauri Carbon 0.4 mm compatibility fix for `Generic PETG @Elegoo`;
- installer, validation script, and backup restoration;
- Czech and English documentation.

## Brand count and limits

The firmware currently contains 70 entries:

- 2 original entries: ELEGOO and Generic;
- 68 additional manufacturers;
- IDs from `0x00` through `0x45`.

The additional brands are:

```text
Prusament, Bambu Lab, Plasty Mladec, eSUN, Polymaker, SUNLU, Overture,
Spectrum, Creality, Anycubic, Eryone, FormFutura, Hatchbox, Kingroon,
QIDI, Raise3D, Flashforge, Snapmaker, ColorFabb, Fillamentum, Fiberlogy,
Filament PM, BASF Ultrafuse, AzureFilm, Atomic Filament, COEX 3D,
FILL3D, FDplast, GreenGate3D, Numakers, Yumi, MatterHackers, Proto-pasta,
Rosa3D, SainSmart, Siraya Tech, The Filament, ZIRO, Zyltech, JAYO,
Geeetech, iSANMATE, AMOLEN, Duramic 3D, Voxelab, Sovol, Tiertime,
Volumic, Peopoly, Co Print, Afinia, Artillery, CoLiDo, Cubicon,
DeltaMaker, FusRock, Valment, Eolas Prints, Aliz, Extrudr, 3DJake,
Recreus, NinjaTek, taulman3D, Kimya, Verbatim, AddNorth, and Noctuo.
```

The current combined binary build is practically full at 70 brands: the
resolver ends at `0x00451043`, while the Slicer version string starts at
`0x00451048`. Adding another brand requires relocating the table or the
version spoof patch.

The format uses one ID byte. After redesigning the resolver placement, the
current contiguous scheme can theoretically hold 238 total entries, IDs
`0x00` through `0xED`. Value `0xEE` is reserved by the original ELEGOO code
`EEEEEEEE`.

The authoritative list is
[`brand_map.json`](../oc-patches/cc1-app/rfid-brand-sync/brand_map.json).

## RFID ID is not a Slicer profile ID

The RFID tag does not contain the text `PRSPLA00`.

Prusament uses:

```text
page 0x10: 36 EE EE EE
page 0x11: 02 00 00 00
```

Manufacturer ID byte `02` identifies Prusament. `PRSPLA00` exists only inside
Elegoo Slicer and identifies its system print profile.

Data flow:

```text
RFID EEEEEE02
  -> firmware: Prusament
  -> display: Prusament / PLA
  -> SDCP Cmd 324: vendor=Prusament, filamentType=PLA
  -> Slicer mapping: PRSPLA00
  -> profile: Prusament PLA @ECC
```

## Installing a new printer

The printer must trust the OpenCentauri signing key before installation.
Replacing that key is a security-sensitive service operation. Do not remove
power during flashing, and do not install this image on another model or
firmware version.

In WSL or Linux:

```bash
git clone -b codex/rfid-brand-sync \
  https://github.com/Dupl3xx/cc-fw-tools.git
cd cc-fw-tools
git lfs pull
python3 -m pip install -r requirements.txt
sudo ./build.sh 1.4.46
```

The output is:

```text
update/update.swu
```

Stage and verify it first:

```bash
./install.sh --stage PRINTER_IP
```

Then flash the inactive A/B partition:

```bash
./install.sh --flash PRINTER_IP
```

`install.sh` detects the active partition and selects the opposite partition
for the new system.

## Installing a new PC

1. Install Elegoo Slicer `1.5.2.2`.
2. Start it once and configure Centauri Carbon with a 0.4 mm nozzle.
3. Close every Slicer instance.
4. From the repository root, run:

```powershell
powershell -ExecutionPolicy Bypass -File `
  .\TOOLS\elegoo-slicer-rfid-sync\Install-ElegooSlicerRfidSync.ps1
```

Accept the UAC prompt. The installer creates a backup before changing files:

```text
%APPDATA%\ElegooSlicer\rfid-sync-backups\
```

Validate the installation:

```powershell
powershell -ExecutionPolicy Bypass -File `
  .\TOOLS\elegoo-slicer-rfid-sync\Test-ElegooSlicerRfidSync.ps1
```

Restore the latest backup:

```powershell
powershell -ExecutionPolicy Bypass -File `
  .\TOOLS\elegoo-slicer-rfid-sync\Uninstall-ElegooSlicerRfidSync.ps1
```

An Elegoo Slicer update may overwrite modified files under `Program Files`.
Run the installer and validator again after updating.

## Writing a custom RFID tag

Example for a black 1 kg Prusament PLA spool:

```bash
python3 oc-patches/cc1-app/rfid-brand-sync/generate_tag.py \
  --brand Prusament \
  --subtype PLA \
  --color 000000 \
  --weight 1000
```

The `A2` commands write raw NTAG213 pages `0x10` through `0x18`. In NFC Tools,
use **Other -> Advanced NFC commands**. Do not store the payload as NDEF text.

List every brand:

```bash
python3 oc-patches/cc1-app/rfid-brand-sync/generate_tag.py --list-brands
```

List all 50 subtypes and temperatures:

```bash
python3 oc-patches/cc1-app/rfid-brand-sync/generate_tag.py --list-subtypes
```

## Verification

Read-only printer verification:

```bash
python3 oc-patches/cc1-app/rfid-brand-sync/live_verify.py \
  PRINTER_IP \
  --tray 1 \
  --expect-brand Prusament
```

In Elegoo Slicer, open **Sync filaments with MMS** and confirm **Sync**. The
verified setup produces:

```text
A1 -> ELEGOO PLA
A2 -> Prusament PLA
A3 -> Generic PETG
```

The Slicer log must not contain:

```text
PresetBundle::sync_ams_list: filament_id ... not found
```

## Important Slicer profile limitation

The firmware can read and transmit all 70 brands. The companion Windows
installer currently adds one exact system profile: `Prusament PLA`. Other
brands appear on the printer and are transmitted over SDCP, but without
another system profile Elegoo Slicer may map them to Generic.

Each additional exact profile requires:

1. a compatible system JSON profile;
2. a unique Slicer `filament_id`;
3. an entry in `Elegoo.json`;
4. vendor and material mapping;
5. a Centauri Carbon 0.4 mm synchronization test.

This does not change the RFID layout or firmware manufacturer ID.

## Files

| Path | Purpose |
| --- | --- |
| `oc-patches/cc1-app/rfid-brand-sync/brand_map.json` | 70 brands and RFID codes |
| `oc-patches/cc1-app/rfid-brand-sync/material_map.json` | materials, subtypes, temperatures |
| `oc-patches/cc1-app/rfid-brand-sync/generate_tag.py` | NFC command generator |
| `oc-patches/cc1-app/rfid-brand-sync/live_verify.py` | SDCP `Cmd 324` validator |
| `TOOLS/elegoo-slicer-rfid-sync/profiles/Prusament PLA @ECC.json` | Slicer profile |
| `TOOLS/elegoo-slicer-rfid-sync/Install-ElegooSlicerRfidSync.ps1` | installation |
| `TOOLS/elegoo-slicer-rfid-sync/Test-ElegooSlicerRfidSync.ps1` | validation |
| `TOOLS/elegoo-slicer-rfid-sync/Uninstall-ElegooSlicerRfidSync.ps1` | restoration |

## Verification status

- 15 firmware regression tests: passed;
- JSON and PowerShell syntax: passed;
- repeated installation: idempotent;
- real Prusament RFID scan on the printer: passed;
- A2 imported into Elegoo Slicer as Prusament PLA: passed;
- original ELEGOO tags: preserved.
