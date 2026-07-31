#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import sys
from pathlib import Path


FULL_PACK_SIZE = 225_736
APP_PACK_SIZE = 176_584
BOOTLOADER_SIZE = 0xC000

FULL_PACK_CHECKS = {
    0x1F1E8: bytes.fromhex("35 4B 10 22 1A 72"),
    0x1F1F4: bytes.fromhex("32 4B 36 22 5A 72"),
    0x1F200: bytes.fromhex("2F 4B EE 22 9A 72"),
    0x1F20C: bytes.fromhex("2C 4B EE 22 DA 72"),
    0x1F218: bytes.fromhex("29 4B EE 22 1A 73"),
}


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(
            f"Usage: {Path(argv[0]).name} <upgrade_ams_lite[_full_pack].bin>",
            file=sys.stderr,
        )
        return 2

    path = Path(argv[1])
    data = path.read_bytes()
    print(f"file: {path}")
    print(f"size: {len(data)}")
    print(f"sha256: {hashlib.sha256(data).hexdigest()}")

    if len(data) == FULL_PACK_SIZE:
        offset_adjustment = 0
    elif len(data) == APP_PACK_SIZE:
        offset_adjustment = -BOOTLOADER_SIZE
    else:
        print("FAIL: unexpected AMS Lite firmware size", file=sys.stderr)
        return 1

    failures = 0
    for full_offset, expected in FULL_PACK_CHECKS.items():
        target = full_offset + offset_adjustment
        actual = data[target:target + len(expected)]
        ok = actual == expected
        print(
            f"[{'PASS' if ok else 'FAIL'}] {target:#08x}: "
            f"{actual.hex(' ').upper()}"
        )
        failures += not ok

    identify_log = b"page 0x10, 0x36, 0xEE, 0xEE, 0xEE"
    log_ok = identify_log in data
    print(
        f"[{'PASS' if log_ok else 'FAIL'}] CANVAS identify-page log confirms "
        "page 16 = 36 EE EE EE"
    )
    failures += not log_ok

    if failures:
        print(f"Audit failed: {failures} problem(s).", file=sys.stderr)
        return 1
    print(
        "Audit completed: manufacturer byte 4 is outside the hardware identify page "
        "and can safely carry the custom brand ID."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
