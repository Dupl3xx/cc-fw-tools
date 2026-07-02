#!/usr/bin/env python3
"""Spoof the firmware version reported to ElegooSlicer in SDCP attribute responses.

Stock CC1 1.4.46 reads the version string from VA 0x00409a38 for:
- UDP discovery responses (sub_368528, VA 0x0036859c)
- WebSocket/MQTT attributes topic (sub_36a948, VA 0x0036a98c)
- Direct request-attribute responses (sub_37e730, VA 0x0037e80c)

This patch repoints the source pointer in all three functions to a new code cave at
VA 0x00451048 containing a fixed "1.4.46\0" string. The original version string at
VA 0x00409a38 (logs, UI, OTA) is left untouched.
"""

import os
SQUASHFS_ROOT = os.getenv("SQUASHFS_ROOT")
FW_VER = os.getenv("FW_VER", "1.4.46")

if not SQUASHFS_ROOT:
    raise RuntimeError("SQUASHFS_ROOT environment variable is required")
if FW_VER != "1.4.46":
    raise RuntimeError(f"Unsupported firmware version for spoof-slicer-firmware-version patch: {FW_VER}")

APP = os.path.join(SQUASHFS_ROOT, "app", "app")

# File offsets (VA - 0x00010000, single LOAD segment starts at VA 0x10000/file 0).
UDP_VERSION_PTR = 0x0035859c      # VA 0x0036859c
WS_VERSION_PTR = 0x0035a98c       # VA 0x0036a98c
REQ_VERSION_PTR = 0x0036e80c      # VA 0x0037e80c (file offset = VA - 0x10000)
CAVE_VA = 0x00451048              # free aligned gap after rfid-brand-sync
CAVE_FILE_OFFSET = CAVE_VA - 0x00010000

EXPECTED_OLD = bytes.fromhex("383a09e3403040e3")  # movw r3,#0x9a38; movt r3,#0x40
NEW_BYTES = bytes.fromhex("483001e3453040e3")     # movw r3,#0x1048; movt r3,#0x45
CAVE_STRING = b"1.4.46\x00"     # 7 bytes, matching the stock 7-byte version slot


def main() -> None:
    with open(APP, "rb") as fp:
        data = bytearray(fp.read())

    sites = (
        ("udp_discovery", UDP_VERSION_PTR),
        ("ws_request_attr", WS_VERSION_PTR),
        ("req_attribute", REQ_VERSION_PTR),
    )
    for label, offset in sites:
        old = bytes(data[offset:offset + len(EXPECTED_OLD)])
        if old != EXPECTED_OLD:
            raise RuntimeError(
                f"{label}: expected {EXPECTED_OLD.hex()} at offset 0x{offset:08x}, "
                f"found {old.hex()}; refusing to patch"
            )

    cave_before = bytes(
        data[CAVE_FILE_OFFSET:CAVE_FILE_OFFSET + len(CAVE_STRING)]
    )
    if any(cave_before):
        raise RuntimeError(
            f"version cave at file offset 0x{CAVE_FILE_OFFSET:08x} is not empty; "
            "refusing to overlap another patch"
        )

    for label, offset in sites:
        data[offset:offset + len(NEW_BYTES)] = NEW_BYTES
        print(
            f"{label}: patched 0x{offset:08x} "
            f"(VA 0x{offset + 0x10000:08x}) to point at 0x{CAVE_VA:08x}"
        )
    data[CAVE_FILE_OFFSET:CAVE_FILE_OFFSET + len(CAVE_STRING)] = CAVE_STRING

    with open(APP, "wb") as fp:
        fp.write(data)
    print(
        f"wrote cave string {CAVE_STRING!r} at file offset "
        f"0x{CAVE_FILE_OFFSET:08x} (VA 0x{CAVE_VA:08x})"
    )


if __name__ == "__main__":
    main()
