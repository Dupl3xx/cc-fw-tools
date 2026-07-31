#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import struct
import sys
from pathlib import Path


VA_DELTA = 0x10000

BRAND_RESOLVER_HOOK_VA = 0x00291C90
MANUFACTURER_RESOLVER_HOOK_VA = 0x00292014
MANUFACTURER_CAVE_START_VA = 0x00450300
MANUFACTURER_CAVE_LIMIT_VA = 0x004508D8
BRAND_CAVE_START_VA = 0x00450C40
BRAND_CAVE_LIMIT_VA = 0x004510D8

ORIGINAL_ELEGOO_STR_VA = 0x00442214
ORIGINAL_GENERIC_STR_VA = 0x0044221C

EXPECTED_HOOK_BYTES = {
    BRAND_RESOLVER_HOOK_VA: bytes.fromhex(
        "01 00 51 e3 80 30 01 d3 44 30 40 d3 81 11 83 d0"
    ),
    MANUFACTURER_RESOLVER_HOOK_VA: bytes.fromhex(
        "ee 0e 0e e3 ee 0e 4e e3 00 00 51 e0 01 00 a0 13 1e ff 2f e1"
    ),
}


COND_EQ = 0x0
COND_NE = 0x1
COND_HI = 0x8
COND_AL = 0xE


def off(va: int) -> int:
    return va - VA_DELTA


def write_u32(data: bytearray, file_off: int, value: int) -> None:
    struct.pack_into("<I", data, file_off, value & 0xFFFFFFFF)


def enc_b(src_va: int, dst_va: int, cond: int = COND_AL) -> int:
    delta = dst_va - (src_va + 8)
    if delta % 4:
        raise ValueError(f"Unaligned branch from {src_va:#x} to {dst_va:#x}")
    imm = delta // 4
    if not -(1 << 23) <= imm < (1 << 23):
        raise ValueError(f"Branch from {src_va:#x} to {dst_va:#x} is out of range")
    return (cond << 28) | 0x0A000000 | (imm & 0x00FFFFFF)


def enc_movw(rd: int, imm16: int, cond: int = COND_AL) -> int:
    return (cond << 28) | 0x03000000 | ((imm16 >> 12) << 16) | (rd << 12) | (imm16 & 0xFFF)


def enc_movt(rd: int, imm16: int, cond: int = COND_AL) -> int:
    return (cond << 28) | 0x03400000 | ((imm16 >> 12) << 16) | (rd << 12) | (imm16 & 0xFFF)


def enc_cmp_reg(rn: int, rm: int, cond: int = COND_AL) -> int:
    return (cond << 28) | 0x01500000 | (rn << 16) | rm


def enc_cmp_imm(rn: int, imm8: int, cond: int = COND_AL) -> int:
    if not 0 <= imm8 <= 0xFF:
        raise ValueError("This patcher only encodes unrotated CMP immediates")
    return (cond << 28) | 0x03500000 | (rn << 16) | imm8


def enc_ldr_imm(rd: int, rn: int, imm12: int = 0, cond: int = COND_AL) -> int:
    if not 0 <= imm12 <= 0xFFF:
        raise ValueError("LDR immediate is out of range")
    return (cond << 28) | 0x05900000 | (rn << 16) | (rd << 12) | imm12


def enc_ldr_scaled_reg(rd: int, rn: int, rm: int, shift: int, cond: int = COND_AL) -> int:
    if not 0 <= shift <= 31:
        raise ValueError("LDR register shift is out of range")
    return (
        (cond << 28)
        | 0x07900000
        | (rn << 16)
        | (rd << 12)
        | (shift << 7)
        | rm
    )


def enc_add_imm(rd: int, rn: int, imm8: int, cond: int = COND_AL) -> int:
    if not 0 <= imm8 <= 0xFF:
        raise ValueError("This patcher only encodes unrotated ADD immediates")
    return (cond << 28) | 0x02800000 | (rn << 16) | (rd << 12) | imm8


def enc_subs_imm(rd: int, rn: int, imm8: int, cond: int = COND_AL) -> int:
    if not 0 <= imm8 <= 0xFF:
        raise ValueError("This patcher only encodes unrotated SUBS immediates")
    return (cond << 28) | 0x02500000 | (rn << 16) | (rd << 12) | imm8


def enc_mov_imm(rd: int, imm8: int, cond: int = COND_AL) -> int:
    if not 0 <= imm8 <= 0xFF:
        raise ValueError("This patcher only encodes unrotated MOV immediates")
    return (cond << 28) | 0x03A00000 | (rd << 12) | imm8


def enc_bx_lr(cond: int = COND_AL) -> int:
    return (cond << 28) | 0x012FFF1E


def load_brand_map() -> list[dict]:
    map_path = Path(__file__).with_name("brand_map.json")
    brand_map = json.loads(map_path.read_text(encoding="utf-8"))
    brands = brand_map["brands"]
    validate_brand_map(brands)
    return brands


def validate_brand_map(brands: list[dict]) -> None:
    if not brands:
        raise ValueError("Brand map is empty")

    ordered = sorted(brands, key=lambda item: int(item["id"]))
    ids = [int(item["id"]) for item in ordered]
    if ids != list(range(len(ordered))):
        raise ValueError("Brand IDs must be contiguous and start at zero")
    if ordered[0]["name"] != "ELEGOO" or ordered[0]["codes"] != ["EEEEEEEE"]:
        raise ValueError("Brand ID 0 must remain ELEGOO with code EEEEEEEE")
    if ordered[1]["name"] != "Generic":
        raise ValueError("Brand ID 1 must remain Generic")
    if len(ordered) > 0xEE:
        raise ValueError("Brand IDs would collide with the EEEEEEEE stock code")

    seen_codes: set[str] = set()
    seen_names: set[str] = set()
    for brand in ordered:
        brand_id = int(brand["id"])
        name = str(brand["name"])
        try:
            encoded_name = name.encode("ascii")
        except UnicodeEncodeError as exc:
            raise ValueError(f"Brand name must be ASCII: {name!r}") from exc
        if not encoded_name or len(encoded_name) > 31:
            raise ValueError(f"Brand name must contain 1-31 ASCII bytes: {name!r}")
        if name.casefold() in seen_names:
            raise ValueError(f"Duplicate brand name: {name}")
        seen_names.add(name.casefold())

        codes = brand.get("codes", [])
        if len(codes) != 1:
            raise ValueError(f"Brand {name} must have exactly one CANVAS-safe code")
        code = str(codes[0]).upper()
        if len(code) != 8:
            raise ValueError(f"Manufacturer code must contain exactly four bytes: {code}")
        bytes.fromhex(code)
        if brand_id > 0 and not code.startswith("EEEEEE"):
            raise ValueError(
                f"Brand {name} code {code} would be rejected by the CANVAS page-16 filter"
            )
        if brand_id > 0 and int(code[-2:], 16) != brand_id:
            raise ValueError(
                f"Brand {name} code suffix must equal its brand ID ({brand_id:02X})"
            )
        if code in seen_codes:
            raise ValueError(f"Duplicate manufacturer code: {code}")
        seen_codes.add(code)


def manufacturer_entries(brands: list[dict]) -> list[tuple[int, int]]:
    entries: list[tuple[int, int]] = []
    for brand in brands:
        entries.append((int(brand["codes"][0], 16), int(brand["id"])))
    return entries


def build_manufacturer_cave(brands: list[dict]) -> bytes:
    entries = manufacturer_entries(brands)
    code_words = 12
    table_va = MANUFACTURER_CAVE_START_VA + code_words * 4
    loop_va = MANUFACTURER_CAVE_START_VA + 3 * 4

    words = [
        enc_movw(2, table_va & 0xFFFF),
        enc_movt(2, (table_va >> 16) & 0xFFFF),
        enc_mov_imm(3, len(entries)),
        enc_ldr_imm(0, 2),
        enc_cmp_reg(1, 0),
        enc_ldr_imm(0, 2, 4, COND_EQ),
        enc_bx_lr(COND_EQ),
        enc_add_imm(2, 2, 8),
        enc_subs_imm(3, 3, 1),
        enc_b(MANUFACTURER_CAVE_START_VA + 9 * 4, loop_va, COND_NE),
        enc_mov_imm(0, 1),
        enc_bx_lr(),
    ]
    payload = bytearray(struct.pack("<" + "I" * len(words), *words))
    for code, brand_id in entries:
        payload.extend(struct.pack("<II", code, brand_id))
    return bytes(payload)


def build_brand_cave(brands: list[dict]) -> bytes:
    ordered = sorted(brands, key=lambda item: int(item["id"]))
    max_id = int(ordered[-1]["id"])
    table_va = BRAND_CAVE_START_VA + 6 * 4

    words = [
        enc_cmp_imm(1, max_id),
        enc_mov_imm(1, 1, COND_HI),
        enc_movw(2, table_va & 0xFFFF),
        enc_movt(2, (table_va >> 16) & 0xFFFF),
        enc_ldr_scaled_reg(0, 2, 1, 2),
        enc_bx_lr(),
    ]
    payload = bytearray(struct.pack("<" + "I" * len(words), *words))
    pointer_table_off = len(payload)
    payload.extend(b"\0" * (len(ordered) * 4))

    pointers: list[int] = []
    for brand in ordered:
        brand_id = int(brand["id"])
        if brand_id == 0:
            pointers.append(ORIGINAL_ELEGOO_STR_VA)
        elif brand_id == 1:
            pointers.append(ORIGINAL_GENERIC_STR_VA)
        else:
            while len(payload) % 4:
                payload.append(0)
            pointers.append(BRAND_CAVE_START_VA + len(payload))
            payload.extend(brand["name"].encode("ascii") + b"\0")

    for index, pointer in enumerate(pointers):
        struct.pack_into("<I", payload, pointer_table_off + index * 4, pointer)

    while len(payload) % 4:
        payload.append(0)
    return bytes(payload)


def write_cave(
    data: bytearray,
    payload: bytes,
    start_va: int,
    limit_va: int,
    name: str,
) -> int:
    end_va = start_va + len(payload)
    if end_va > limit_va:
        raise SystemExit(
            f"{name} cave is too large: ends at {end_va:#x}, limit is {limit_va:#x}"
        )
    start = off(start_va)
    if any(data[start:start + len(payload)]):
        raise SystemExit(f"{name} cave is not empty; refusing to overwrite another patch.")
    data[start:start + len(payload)] = payload
    return end_va


def patch_app(path: Path) -> None:
    data = bytearray(path.read_bytes())
    original_sha = hashlib.sha256(data).hexdigest()

    for va, expected in EXPECTED_HOOK_BYTES.items():
        actual = bytes(data[off(va): off(va) + len(expected)])
        if actual != expected:
            raise SystemExit(
                f"Unexpected bytes at {va:#x}; refusing to patch. "
                f"Expected {expected.hex()}, got {actual.hex()}."
            )

    brands = load_brand_map()
    manufacturer_payload = build_manufacturer_cave(brands)
    brand_payload = build_brand_cave(brands)
    manufacturer_end_va = write_cave(
        data,
        manufacturer_payload,
        MANUFACTURER_CAVE_START_VA,
        MANUFACTURER_CAVE_LIMIT_VA,
        "RFID manufacturer resolver",
    )
    brand_end_va = write_cave(
        data,
        brand_payload,
        BRAND_CAVE_START_VA,
        BRAND_CAVE_LIMIT_VA,
        "RFID brand resolver",
    )

    write_u32(
        data,
        off(MANUFACTURER_RESOLVER_HOOK_VA),
        enc_b(MANUFACTURER_RESOLVER_HOOK_VA, MANUFACTURER_CAVE_START_VA),
    )
    write_u32(
        data,
        off(BRAND_RESOLVER_HOOK_VA),
        enc_b(BRAND_RESOLVER_HOOK_VA, BRAND_CAVE_START_VA),
    )

    path.write_bytes(data)
    patched_sha = hashlib.sha256(data).hexdigest()
    print(f"RFID_BRAND_SYNC patched {path}")
    print(f"  before sha256: {original_sha}")
    print(f"  after  sha256: {patched_sha}")
    print(
        f"  manufacturer cave: {MANUFACTURER_CAVE_START_VA:#010x}-"
        f"{manufacturer_end_va - 1:#010x}"
    )
    print(f"  brand cave:        {BRAND_CAVE_START_VA:#010x}-{brand_end_va - 1:#010x}")
    print(
        f"  manufacturer resolver hook: {MANUFACTURER_RESOLVER_HOOK_VA:#010x} "
        f"-> {MANUFACTURER_CAVE_START_VA:#010x}"
    )
    print(
        f"  brand resolver hook:        {BRAND_RESOLVER_HOOK_VA:#010x} "
        f"-> {BRAND_CAVE_START_VA:#010x}"
    )


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"Usage: {Path(argv[0]).name} <path-to-app>", file=sys.stderr)
        return 2
    patch_app(Path(argv[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
