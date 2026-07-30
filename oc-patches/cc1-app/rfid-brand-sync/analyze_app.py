#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import struct
import sys
from pathlib import Path


VA_DELTA = 0x10000


def va(file_off: int) -> int:
    return file_off + VA_DELTA


def refs_to(data: bytes, target_va: int) -> list[int]:
    needle = struct.pack("<I", target_va)
    refs: list[int] = []
    start = 0
    while True:
        hit = data.find(needle, start)
        if hit < 0:
            return refs
        refs.append(hit)
        start = hit + 1


def find_string(data: bytes, text: bytes) -> list[int]:
    hits: list[int] = []
    start = 0
    while True:
        hit = data.find(text + b"\0", start)
        if hit < 0:
            return hits
        hits.append(hit)
        start = hit + 1


def read_c_string(data: bytes, file_off: int) -> str:
    end = data.find(b"\0", file_off)
    if end < 0:
        return "<unterminated>"
    return data[file_off:end].decode("ascii", errors="replace")


def parse_command_entry(data: bytes, desc: bytes) -> tuple[int, int, int, int, str] | None:
    hits = find_string(data, desc)
    for string_off in hits:
        for ref in refs_to(data, va(string_off)):
            entry_off = ref - 4
            if entry_off < 0 or entry_off + 16 > len(data):
                continue
            cmd, desc_ptr, handler, opaque = struct.unpack_from("<IIII", data, entry_off)
            if desc_ptr == va(string_off) and cmd < 1000:
                return entry_off, cmd, handler, opaque, read_c_string(data, string_off)
    return None


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"Usage: {Path(argv[0]).name} <path-to-app>", file=sys.stderr)
        return 2

    path = Path(argv[1])
    data = path.read_bytes()
    print(f"file: {path}")
    print(f"size: {len(data)}")
    print(f"sha256: {hashlib.sha256(data).hexdigest()}")

    for text in [
        b"ELEGOO",
        b"Generic",
        b"material info get",
        b"tray_id",
        b"brand",
        b"filament_name",
        b"filament_code",
        b"filament_color",
        b"min_nozzle_temp",
        b"max_nozzle_temp",
        b"/user-resource/filament_info",
        b"is_material_supported_by_brand",
        b"get_rfid_subclass_code_by_num",
    ]:
        hits = find_string(data, text)
        print(f"{text.decode(errors='replace')}: {[hex(x) for x in hits]}")
        for hit in hits[:3]:
            ref_hits = refs_to(data, va(hit))
            if ref_hits:
                print(f"  refs to {va(hit):#010x}: {[hex(x) for x in ref_hits[:10]]}")

    entry = parse_command_entry(data, b"material info get")
    if entry is None:
        print("SDCP material command: NOT FOUND")
    else:
        entry_off, cmd, handler, opaque, desc = entry
        print(
            "SDCP material command: "
            f"entry_off={entry_off:#x}, cmd={cmd}, desc='{desc}', "
            f"handler={handler:#010x}, data={opaque:#010x}"
        )

    brand_table = data.find(struct.pack("<II", 0xEEEEEEEE, 0x00442214))
    if brand_table >= 0:
        print(f"stock brand table: file_off={brand_table:#x}, va={va(brand_table):#010x}")
        for i in range(2):
            code, ptr = struct.unpack_from("<II", data, brand_table + i * 8)
            print(f"  {i}: code={code:#010x}, ptr={ptr:#010x}, text='{read_c_string(data, ptr - VA_DELTA)}'")

    try:
        import capstone
    except Exception:
        return 0

    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_ARM)
    for name, start_va in [
        ("brand resolver hook", 0x00291C90),
        ("manufacturer resolver hook", 0x00292014),
        ("tray JSON item builder", 0x0036E184),
    ]:
        print(f"\n{name} @ {start_va:#010x}")
        start = start_va - VA_DELTA
        for ins in md.disasm(data[start: start + 0x80], start_va):
            print(f"  {ins.address:08x}: {ins.mnemonic:<8} {ins.op_str}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
