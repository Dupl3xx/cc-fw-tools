# `spoof-slicer-firmware-version` for CC1 1.4.46

## Stock behavior

The SDCP attribute builders for UDP discovery, WebSocket attributes, and direct `request attribute` load the firmware version from the literal address `0x00409a38` (file offset `0x003f9a38`). The same address is also used elsewhere for logs, UI, and OTA checks, so replacing it directly would have side effects.

## Patch mechanism

1. Claim a code cave at VA `0x00451048`, directly after the
   `rfid-brand-sync` payload.
2. Write the fixed string `1.4.46\0` into the cave.
3. Repoint the `movw/movt` pair in all three slicer-facing functions so `r3`
   is loaded with `0x00451048` instead of `0x00409a38`.

The original version string is left untouched.

## Affected instructions

### UDP discovery (`sub_368528`)
- VA: `0x0036859c`
- File offset: `0x0035859c`
- Original: `movw r3, #0x9a38; movt r3, #0x40` (`38 3a 09 e3 40 30 40 e3`)
- Patched: `movw r3, #0x1048; movt r3, #0x45` (`48 30 01 e3 45 30 40 e3`)

The loaded pointer is stored on the stack and later copied to the response buffer at `0x003687bc`.

### WebSocket attributes (`sub_36a948`)
- VA: `0x0036a98c`
- File offset: `0x0035a98c`
- Same instruction change as above.

The loaded pointer is read directly into `r0/r1` and copied to the `FirmwareVersion` field.

### Direct request-attribute (`sub_37e730`)
- VA: `0x0037e80c`
- File offset: `0x0036e80c`
- Same instruction change as above.

This handles the `request attribute` SDCP command envelope.

## Code cave details

| Item | Value |
|---|---|
| Cave VA | `0x00451048` |
| Cave file offset | `0x00441048` |
| String | `1.4.46\0` |
| Raw bytes | `31 2e 34 2e 34 36 00` |
| Size used | 7 bytes |
| Reserved | 8 bytes (`0x00451048` – `0x0045104f`) |

## Compatibility

- Only CC1 firmware `1.4.46` is supported.
- The patch is compatible with `rfid-brand-sync`; the upstream
  `0x00450e00` location was deliberately relocated because it overlaps that
  patch.

## Build enable

Set `SPOOF_SLICER_FIRMWARE_VERSION=true` in `oc-patches/patch_config` (or `firmware-editions/patched`).
