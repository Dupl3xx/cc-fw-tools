# RFID brands for CANVAS, the display, and Elegoo Slicer

[Cesky](README-CZ.md) | [English](README-EN.md)

The complete new-printer, new-PC, tag-writing, and restoration procedure is in
the [end-to-end guide](../../../docs/RFID-END-TO-END-EN.md).

This patch targets the ELEGOO Centauri Carbon 1 running stock firmware
`1.4.46` as the base for OpenCentauri `0.4.0`. It adds 68 custom brand names
while retaining the original ELEGOO and Generic entries. It does not replace
the printer's material types or temperature tables.

## Compatibility

| Component | Supported state |
| --- | --- |
| Printer | ELEGOO Centauri Carbon 1 |
| Base firmware | `1.4.46` |
| OpenCentauri | `0.4.0` |
| RFID tag | NTAG213, raw pages `0x10` through `0x18` |
| ELEGOO firmware `1.4.49` | Not supported by this patch |

The patcher validates the original instructions and every allocated code cave.
It refuses to modify an unknown binary instead of writing to unverified
addresses.

## What changed

- Added a manufacturer ID to internal brand ID resolver.
- Added an indexed brand ID to text resolver shared by the display and SDCP.
- Added 68 custom brands, for 70 total entries including ELEGOO and Generic.
- Preserved the original ELEGOO manufacturer ID `EEEEEEEE`.
- Unknown manufacturer and brand IDs safely fall back to Generic.
- Extracted the exact 15 materials, 50 subtypes, and temperature ranges from
  the `1.4.46` application binary.
- Added a generator for the complete nine-page NTAG213 filament payload.
- Added static audits for the main application and the CANVAS MCU firmware.
- Added a read-only live verifier that uses SDCP `Cmd 324`.
- Integrated the upstream `spoof-slicer-firmware-version` patch so Elegoo
  Slicer receives the supported version `V1.4.46`.
- Added 17 regression tests, including code-cave collision and final-edition
  Slicer identity checks.
- Fixed `pack.sh` signing order so `cpio_item_md5` hashes the final
  `sw-description.sig`.

## Why ordinary custom brand codes do not work

CANVAS does not accept every NTAG213 unconditionally. The AMS Lite MCU
configures this hardware identify-page filter:

```text
page 0x10 = 36 EE EE EE
```

This explains why the following tag is detected and produces a beep:

```text
A2:10:36EEEEEE
A2:11:EE000000
```

Changing any of the first three manufacturer bytes on page `0x10` causes the
RFID controller to discard the tag before the main application receives it.
Patching only the application brand resolver would therefore be insufficient.

This patch uses a CANVAS-safe brand protocol:

- page `0x10` remains exactly `36EEEEEE` for every brand;
- the brand ID is stored in manufacturer byte 4, which is byte 0 of page
  `0x11`;
- ELEGOO remains `EEEEEEEE`;
- an unknown code resolves to Generic.

Examples:

| Brand | Manufacturer ID | Page `0x10` | Page `0x11` |
| --- | --- | --- | --- |
| ELEGOO | `EEEEEEEE` | `36EEEEEE` | `EE000000` |
| Generic | `EEEEEE01` | `36EEEEEE` | `01000000` |
| Prusament | `EEEEEE02` | `36EEEEEE` | `02000000` |
| Bambu Lab | `EEEEEE03` | `36EEEEEE` | `03000000` |
| Plasty Mladec | `EEEEEE04` | `36EEEEEE` | `04000000` |
| eSUN | `EEEEEE05` | `36EEEEEE` | `05000000` |
| Polymaker | `EEEEEE06` | `36EEEEEE` | `06000000` |
| SUNLU | `EEEEEE07` | `36EEEEEE` | `07000000` |
| Overture | `EEEEEE08` | `36EEEEEE` | `08000000` |
| Spectrum | `EEEEEE09` | `36EEEEEE` | `09000000` |
| Creality | `EEEEEE0A` | `36EEEEEE` | `0A000000` |

The authoritative full list is stored in `brand_map.json`. It can also be
printed with:

```bash
python3 generate_tag.py --list-brands
```

## Tag layout

The printer reads nine NTAG213 pages, from `0x10` through `0x18`:

| Page | Contents |
| --- | --- |
| `0x10` | header `36` plus manufacturer ID bytes 1 through 3 |
| `0x11` | manufacturer ID byte 4 plus three reserved bytes |
| `0x12` | 32-bit main material code |
| `0x13` | 16-bit subtype code plus two reserved bytes |
| `0x14` | RGB plus color modifier |
| `0x15` | minimum and maximum nozzle temperatures |
| `0x16` | reserved |
| `0x17` | diameter in hundredths of a millimeter plus weight in grams |
| `0x18` | production code |

The material map is taken directly from firmware `1.4.46`. The generator does
not use the contradictory ASCII examples found in older public tag
documentation.

## Generating a tag

Run the generator from the patch directory. Example for a black, 1 kg
Prusament PLA spool:

```bash
python3 generate_tag.py \
  --brand Prusament \
  --subtype PLA \
  --color 000000 \
  --weight 1000
```

The output starts with:

```text
A2 10 36 EE EE EE
A2 11 02 00 00 00
A2 12 00 80 76 65
```

In NFC Tools, open `Other` -> `Advanced NFC commands`. Do not write the
payload as NDEF text. Each `A2` command writes one raw four-byte page.

List all firmware material subtypes and temperatures:

```bash
python3 generate_tag.py --list-subtypes
```

Generate machine-readable JSON:

```bash
python3 generate_tag.py \
  --brand "Bambu Lab" \
  --subtype PETG-CF \
  --color 123ABC \
  --weight 750 \
  --json
```

## Building the firmware

Install repository dependencies:

```bash
python3 -m pip install -r requirements.txt
```

Build the supported edition:

```bash
sudo ./build.sh 1.4.46
```

The resulting installer is:

```text
update/update.swu
```

`oc-patches/patch_config` is a Git symbolic link to
`firmware-editions/patched`. On Windows, cloning and building inside WSL is the
most reliable way to preserve that link.

## Installation

The printer must already trust the OpenCentauri signing key. It must be idle,
and power must remain connected throughout the update.

The safer two-step workflow first uploads the file and verifies its MD5:

```bash
./install.sh --stage PRINTER_IP
```

Only after that check should the inactive A/B partition be written:

```bash
./install.sh --flash PRINTER_IP
```

Both steps can be combined:

```bash
./install.sh --sendit PRINTER_IP
```

The image can be checked on the printer without installing it:

```bash
swupdate -c \
  -i /user-resource/update.swu \
  -k /etc/swupdate_public.pem \
  -e stable,now_A_next_B
```

`now_A_next_B` is valid only when the printer is currently booted from
`bootA`. `install.sh` detects the active partition and selects the reverse
mode when the printer is running from B.

## Display and Elegoo Slicer data flow

1. CANVAS accepts the tag because page `0x10` remains `36EEEEEE`.
2. The main application assembles the 32-bit manufacturer ID.
3. Hook `0x00292014` maps the manufacturer ID to an internal brand ID.
4. Hook `0x00291c90` maps the brand ID to text.
5. The display, RFID workflow, and SDCP response use the same resolver.

Before requesting filament data, the Slicer validates the printer identity and
firmware version. Elegoo Slicer did not accept the original OpenCentauri value
`V0.4.0-d` as a compatible firmware, so CANVAS import was unavailable. The
combined build reports `V1.4.46` through all three Slicer-facing paths:

- UDP discovery;
- WebSocket attributes;
- the direct SDCP `Cmd 1` (`request attribute`) response.

The real OpenCentauri version used by the local UI, logs, and OTA remains
unchanged. Only the value sent to the Slicer is replaced.

Elegoo Slicer does not read filament data from the HTTP path
`/user-resource/filament_info`. It connects to:

```text
ws://PRINTER_IP:3030/websocket
```

The Slicer requests material data through SDCP `Cmd 324`, described as
`material info get`. The printer returns fields such as:

```json
{
  "tray_id": 0,
  "brand": "Prusament",
  "filament_name": "PLA",
  "filament_code": "PLA",
  "filament_color": "#000000",
  "min_nozzle_temp": 190,
  "max_nozzle_temp": 230
}
```

Elegoo Slicer receives `brand` as the tray vendor. Automatic profile matching
primarily uses the standardized filament name and type; the vendor is a
secondary criterion. This patch does not add or modify Slicer print profiles.

Elegoo Slicer `1.5.2.2` also accepts only system base profiles with an exact
internal ID during MMS synchronization. The repository therefore includes a
separate [Windows profile installer](../../../TOOLS/elegoo-slicer-rfid-sync/README-EN.md).
It adds `Prusament PLA @ECC` with ID `PRSPLA00` and fixes Generic PETG
compatibility for Centauri Carbon.

After an RFID scan, the display can show custom names such as Prusament, Bambu
Lab, or Plasty Mladec as the current brand value. The stock dropdown still
contains only the two physically constructed options, ELEGOO and Generic.
Opening that dropdown and selecting an item overwrites the RFID-loaded brand.
The 70 brands are therefore RFID-readable values, not 70 manually selectable
dropdown entries. The firmware patch itself does not modify print profiles;
the companion Windows installer currently adds the verified Prusament PLA
profile.

## Patch files

| File | Purpose |
| --- | --- |
| `patch_app.py` | guarded binary patch for both resolvers |
| `brand_map.json` | authoritative map of all 70 brands |
| `material_map.json` | 15 materials and 50 subtypes with temperatures |
| `tag_codec.py` | encoder and decoder for the nine RFID pages |
| `generate_tag.py` | NFC Tools command generator |
| `analyze_app.py` | application, SDCP, and material table audit |
| `analyze_canvas_filter.py` | AMS Lite hardware filter audit |
| `live_verify.py` | read-only live view of the same JSON used by the Slicer |
| `test_rfid_brand_sync.py` | protocol and patcher regression tests |
| `../spoof-slicer-firmware-version/` | compatible `V1.4.46` Slicer handshake |

## Binary map

- stock `/app/app` SHA-256:
  `ae693f7dc096da1f734c2972694963286cba20dc8f6afac79f8468139b613129`
- manufacturer resolver: `0x00292014` -> cave `0x00450300`
- brand resolver: `0x00291c90` -> cave `0x00450c40`
- Slicer version `1.4.46`: cave `0x00451048`
- Slicer pointer sites: `0x0036859c`, `0x0036a98c`, `0x0037e80c`
- display resolver call: `0x0031ed3c`
- RFID workflow resolver call: `0x00321ca0`
- SDCP JSON resolver call: `0x0036e744`
- SDCP registration: `Cmd 324`, dispatcher `0x0036cd18`, callback `0x00371598`

## Verification

Run all regression tests:

```bash
python3 -m unittest discover \
  -s oc-patches/cc1-app/rfid-brand-sync \
  -p "test_*.py" \
  -v
```

Audit the final application:

```bash
python3 oc-patches/cc1-app/rfid-brand-sync/analyze_app.py \
  unpacked/squashfs-root/app/app
```

Audit the CANVAS identify-page filter:

```bash
python3 oc-patches/cc1-app/rfid-brand-sync/analyze_canvas_filter.py \
  unpacked/squashfs-root/app/resources/firmware/upgrade_ams_lite_full_pack.bin
```

Read the current CANVAS material data without changing the printer:

```bash
python3 oc-patches/cc1-app/rfid-brand-sync/live_verify.py PRINTER_IP
```

Verify one expected brand in one tray:

```bash
python3 oc-patches/cc1-app/rfid-brand-sync/live_verify.py \
  PRINTER_IP \
  --tray 0 \
  --expect-brand Prusament \
  --expect-firmware-version V1.4.46
```

The verified test build has these values:

| Artifact | Value |
| --- | --- |
| `update.swu` size | `116045824` bytes |
| `update.swu` SHA-256 | `f8d3e126134eedf9fe3201c44c2deea581dbe4547faacfd0165fc1d4fa87b7d2` |
| final `/app/app` SHA-256 | `50714d6cab202bbbb5a1ea7468dc4f8188091272c2ec737e444c7147b938be6f` |
| AMS Lite firmware SHA-256 | `998ba6955f1279b2360069a5e6599c01a03151f837022c79a186f4048d98a5d3` |

This image passed all 17 tests, the final application audit, the AMS Lite
audit, every `cpio_item_md5` entry, signature verification, and an independent
SWU extraction. A real printer also accepted the same file in read-only
`swupdate -c` mode with exit status 0.

The final hardware test must confirm:

1. An original ELEGOO tag still beeps and displays ELEGOO.
2. `EEEEEE02` beeps and displays Prusament.
3. `EEEEEE03` beeps and displays Bambu Lab.
4. `EEEEEE04` beeps and displays Plasty Mladec.
5. Material type, color, and temperatures match the tag.
6. Refreshing CANVAS in Elegoo Slicer shows the same brand and material.

Static analysis, tests, and the firmware build prove binary consistency. RFID
range, the audible detection beep, and end-to-end behavior on a specific
printer can only be conclusively verified with this hardware test.
