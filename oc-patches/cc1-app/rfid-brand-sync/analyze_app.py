#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import struct
import sys
from pathlib import Path


VA_DELTA = 0x10000
STOCK_SHA256 = "ae693f7dc096da1f734c2972694963286cba20dc8f6afac79f8468139b613129"

BRAND_HOOK_VA = 0x00291C90
MANUFACTURER_HOOK_VA = 0x00292014
BRAND_CAVE_VA = 0x00450C40
MANUFACTURER_CAVE_VA = 0x00450300
BRAND_THUNK_VA = 0x002ABBAC
MANUFACTURER_THUNK_VA = 0x002ABBB4

MATERIAL_TABLE_VA = 0x00441080
SUBTYPE_TEMP_TABLE_VA = 0x004411F8
SUBTYPE_NAME_TABLE_VA = 0x00441478

SLICER_VERSION_CAVE_VA = 0x00451048
SLICER_VERSION_SITES = [0x0036859C, 0x0036A98C, 0x0037E80C]
SLICER_VERSION_ORIGINAL = bytes.fromhex("38 3a 09 e3 40 30 40 e3")
SLICER_VERSION_RELOCATED = bytes.fromhex("48 30 01 e3 45 30 40 e3")


def off(va: int) -> int:
    return va - VA_DELTA


def va(file_off: int) -> int:
    return file_off + VA_DELTA


def read_u32(data: bytes, target_va: int) -> int:
    return struct.unpack_from("<I", data, off(target_va))[0]


def read_c_string(data: bytes, target_va: int) -> str:
    start = off(target_va)
    end = data.find(b"\0", start)
    if end < 0:
        raise ValueError(f"Unterminated string at {target_va:#x}")
    return data[start:end].decode("ascii", errors="strict")


def branch_target(instruction: int, instruction_va: int) -> int | None:
    if (instruction & 0x0E000000) != 0x0A000000:
        return None
    immediate = instruction & 0x00FFFFFF
    if immediate & 0x00800000:
        immediate -= 1 << 24
    return instruction_va + 8 + immediate * 4


def find_string(data: bytes, text: bytes) -> list[int]:
    hits: list[int] = []
    start = 0
    while True:
        hit = data.find(text + b"\0", start)
        if hit < 0:
            return hits
        hits.append(hit)
        start = hit + 1


def refs_to(data: bytes, target_va: int) -> list[int]:
    needle = struct.pack("<I", target_va)
    hits: list[int] = []
    start = 0
    while True:
        hit = data.find(needle, start)
        if hit < 0:
            return hits
        hits.append(hit)
        start = hit + 1


def parse_command_entry(data: bytes, description: bytes) -> tuple[int, int, int, int] | None:
    for string_off in find_string(data, description):
        for ref in refs_to(data, va(string_off)):
            entry_off = ref - 4
            if entry_off < 0 or entry_off + 16 > len(data):
                continue
            command, description_ptr, dispatcher, callback = struct.unpack_from(
                "<IIII", data, entry_off
            )
            if description_ptr == va(string_off) and command < 1000:
                return entry_off, command, dispatcher, callback
    return None


class Audit:
    def __init__(self) -> None:
        self.failures: list[str] = []

    def check(self, condition: bool, message: str) -> None:
        status = "PASS" if condition else "FAIL"
        print(f"[{status}] {message}")
        if not condition:
            self.failures.append(message)


def audit_material_tables(data: bytes, audit: Audit) -> None:
    map_path = Path(__file__).with_name("material_map.json")
    material_map = json.loads(map_path.read_text(encoding="utf-8"))

    actual_materials: dict[str, str] = {}
    for index in range(15):
        code, name_ptr = struct.unpack_from(
            "<II", data, off(MATERIAL_TABLE_VA) + index * 8
        )
        actual_materials[f"{code:08X}"] = read_c_string(data, name_ptr)
    expected_materials = {
        item["code"]: item["name"] for item in material_map["materials"]
    }
    audit.check(
        actual_materials == expected_materials,
        "15 material codes match the firmware 1.4.46 table",
    )

    names: dict[int, str] = {}
    for index in range(50):
        code, name_ptr = struct.unpack_from(
            "<II", data, off(SUBTYPE_NAME_TABLE_VA) + index * 8
        )
        names[code & 0xFFFF] = read_c_string(data, name_ptr)

    actual_subtypes: dict[str, tuple[str, int, int]] = {}
    for index in range(50):
        code, minimum, maximum, _flags = struct.unpack_from(
            "<HHHH", data, off(SUBTYPE_TEMP_TABLE_VA) + index * 8
        )
        actual_subtypes[f"{code:04X}"] = (names[code], minimum, maximum)
    expected_subtypes = {
        item["code"]: (item["name"], item["min_temp"], item["max_temp"])
        for item in material_map["subtypes"]
    }
    audit.check(
        actual_subtypes == expected_subtypes,
        "50 subtype names and nozzle temperature ranges match firmware 1.4.46",
    )


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"Usage: {Path(argv[0]).name} <path-to-app>", file=sys.stderr)
        return 2

    path = Path(argv[1])
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    print(f"file: {path}")
    print(f"size: {len(data)}")
    print(f"sha256: {digest}")

    audit = Audit()
    audit.check(len(data) == 4_787_332, "ELF file size matches firmware 1.4.46")
    print(f"[INFO] image type: {'stock' if digest == STOCK_SHA256 else 'modified'}")

    command = parse_command_entry(data, b"material info get")
    audit.check(command is not None, "SDCP command 324 registration is present")
    if command is not None:
        entry_off, command_id, dispatcher, callback = command
        audit.check(command_id == 324, f"material command ID is 324 (entry {entry_off:#x})")
        audit.check(
            dispatcher == 0x0036CD18,
            "SDCP command dispatcher remains at 0x0036cd18",
        )
        audit.check(
            callback == 0x00371598,
            "SDCP material callback remains at 0x00371598",
        )

    required_json_keys = [
        b"tray_id",
        b"brand",
        b"filament_name",
        b"filament_code",
        b"filament_color",
        b"min_nozzle_temp",
        b"max_nozzle_temp",
    ]
    for key in required_json_keys:
        audit.check(bool(find_string(data, key)), f"SDCP JSON key {key.decode()} is present")

    for call_site in [0x0031ED3C, 0x00321CA0, 0x0036E744]:
        target = branch_target(read_u32(data, call_site), call_site)
        audit.check(
            target == BRAND_THUNK_VA,
            f"brand resolver is used at {call_site:#010x}",
        )
    manufacturer_target = branch_target(read_u32(data, 0x00321B64), 0x00321B64)
    audit.check(
        manufacturer_target == MANUFACTURER_THUNK_VA,
        "RFID parser calls the manufacturer resolver",
    )

    brand_thunk_target = branch_target(read_u32(data, BRAND_THUNK_VA + 4), BRAND_THUNK_VA + 4)
    manufacturer_thunk_target = branch_target(
        read_u32(data, MANUFACTURER_THUNK_VA + 4),
        MANUFACTURER_THUNK_VA + 4,
    )
    audit.check(brand_thunk_target == BRAND_HOOK_VA, "brand thunk reaches hook 0x00291c90")
    audit.check(
        manufacturer_thunk_target == MANUFACTURER_HOOK_VA,
        "manufacturer thunk reaches hook 0x00292014",
    )

    brand_hook_target = branch_target(read_u32(data, BRAND_HOOK_VA), BRAND_HOOK_VA)
    manufacturer_hook_target = branch_target(
        read_u32(data, MANUFACTURER_HOOK_VA), MANUFACTURER_HOOK_VA
    )
    patched = brand_hook_target == BRAND_CAVE_VA
    if patched:
        audit.check(
            manufacturer_hook_target == MANUFACTURER_CAVE_VA,
            "both RFID hooks point to their allocated caves",
        )
        brand_map = json.loads(
            Path(__file__).with_name("brand_map.json").read_text(encoding="utf-8")
        )["brands"]
        cave = data[off(BRAND_CAVE_VA):off(0x004510D8)]
        for brand in brand_map:
            if brand["id"] > 1:
                audit.check(
                    brand["name"].encode("ascii") + b"\0" in cave,
                    f"patched brand string is present: {brand['name']}",
                )
    else:
        audit.check(
            data[off(BRAND_HOOK_VA):off(BRAND_HOOK_VA) + 4]
            == bytes.fromhex("01 00 51 e3"),
            "stock brand resolver prologue is intact",
        )
        audit.check(
            data[off(MANUFACTURER_HOOK_VA):off(MANUFACTURER_HOOK_VA) + 4]
            == bytes.fromhex("ee 0e 0e e3"),
            "stock manufacturer resolver prologue is intact",
        )

    slicer_site_bytes = [
        data[off(site):off(site) + len(SLICER_VERSION_RELOCATED)]
        for site in SLICER_VERSION_SITES
    ]
    slicer_spoofed = any(
        site == SLICER_VERSION_RELOCATED for site in slicer_site_bytes
    )
    if slicer_spoofed:
        for site, actual in zip(SLICER_VERSION_SITES, slicer_site_bytes):
            audit.check(
                actual == SLICER_VERSION_RELOCATED,
                f"slicer version pointer is relocated at {site:#010x}",
            )
        audit.check(
            data[
                off(SLICER_VERSION_CAVE_VA):
                off(SLICER_VERSION_CAVE_VA) + len(b"1.4.46\0")
            ] == b"1.4.46\0",
            "slicer-facing version cave contains 1.4.46",
        )
    else:
        for site, actual in zip(SLICER_VERSION_SITES, slicer_site_bytes):
            audit.check(
                actual == SLICER_VERSION_ORIGINAL,
                f"stock slicer version pointer is intact at {site:#010x}",
            )

    audit_material_tables(data, audit)

    if audit.failures:
        print(f"\nAudit failed: {len(audit.failures)} problem(s).", file=sys.stderr)
        return 1
    print("\nAudit completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
