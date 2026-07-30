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
CAVE_START_VA = 0x00450C40
CAVE_LIMIT_VA = 0x00451000

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
COND_AL = 0xE


def off(va: int) -> int:
    return va - VA_DELTA


def read_u32(data: bytes | bytearray, file_off: int) -> int:
    return struct.unpack_from("<I", data, file_off)[0]


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


def enc_mov_imm(rd: int, imm8: int, cond: int = COND_AL) -> int:
    if not 0 <= imm8 <= 0xFF:
        raise ValueError("This patcher only encodes unrotated MOV immediates")
    return (cond << 28) | 0x03A00000 | (rd << 12) | imm8


def enc_bx_lr(cond: int = COND_AL) -> int:
    return (cond << 28) | 0x012FFF1E


def enc_ldr_pc(rd: int, instr_va: int, literal_va: int, cond: int = COND_AL) -> int:
    imm = literal_va - (instr_va + 8)
    if not 0 <= imm <= 0xFFF:
        raise ValueError(f"Literal at {literal_va:#x} is out of range for LDR at {instr_va:#x}")
    return (cond << 28) | 0x059F0000 | (rd << 12) | imm


class ArmBlob:
    def __init__(self, base_va: int) -> None:
        self.base_va = base_va
        self.words: list[int] = []
        self.bytes_tail = bytearray()
        self.labels: dict[str, int] = {}
        self.literal_refs: list[tuple[int, str, int, int]] = []
        self.pending_string_labels: dict[str, bytes] = {}

    @property
    def cursor_va(self) -> int:
        return self.base_va + len(self.words) * 4 + len(self.bytes_tail)

    def label(self, name: str) -> None:
        self.align4()
        self.labels[name] = self.cursor_va

    def word(self, value: int) -> None:
        if self.bytes_tail:
            raise RuntimeError("Cannot emit instructions after raw data")
        self.words.append(value & 0xFFFFFFFF)

    def ldr_literal(self, rd: int, label: str, cond: int = COND_AL) -> None:
        instr_va = self.base_va + len(self.words) * 4
        self.literal_refs.append((len(self.words), label, rd, cond))
        self.words.append(0)

    def align4(self) -> None:
        while len(self.bytes_tail) % 4:
            self.bytes_tail.append(0)

    def data_u32(self, value: int) -> None:
        self.align4()
        self.bytes_tail.extend(struct.pack("<I", value & 0xFFFFFFFF))

    def string_label(self, label: str, value: str) -> None:
        self.pending_string_labels[label] = value.encode("ascii") + b"\0"

    def finish(self) -> bytes:
        code_len = len(self.words) * 4
        data = bytearray(struct.pack("<" + "I" * len(self.words), *self.words))
        data.extend(self.bytes_tail)

        for label, value in self.pending_string_labels.items():
            while len(data) % 4:
                data.append(0)
            self.labels[label] = self.base_va + len(data)
            data.extend(value)

        while len(data) % 4:
            data.append(0)

        for index, label, rd, cond in self.literal_refs:
            instr_va = self.base_va + index * 4
            literal_va = self.labels[label]
            struct.pack_into("<I", data, index * 4, enc_ldr_pc(rd, instr_va, literal_va, cond))

        return bytes(data)


def load_brand_map() -> list[dict]:
    map_path = Path(__file__).with_name("brand_map.json")
    brand_map = json.loads(map_path.read_text(encoding="utf-8"))
    return brand_map["brands"]


def reversed_hex32(hex_code: str) -> str:
    raw = bytes.fromhex(hex_code)
    return raw[::-1].hex().upper()


def manufacturer_entries(brands: list[dict]) -> list[tuple[int, int]]:
    entries: list[tuple[int, int]] = []
    seen: set[int] = set()
    for brand in brands:
        for code in brand.get("codes", []):
            for candidate in {code.upper(), reversed_hex32(code)}:
                value = int(candidate, 16)
                if value not in seen:
                    entries.append((value, int(brand["id"])))
                    seen.add(value)
    entries.sort(key=lambda item: (item[1] != 0, item[1], item[0]))
    return entries


def build_cave(brands: list[dict]) -> tuple[bytes, int, int]:
    blob = ArmBlob(CAVE_START_VA)

    manufacturer_func_va = blob.cursor_va
    blob.label("manufacturer_resolver")
    for code, brand_id in manufacturer_entries(brands):
        blob.word(enc_movw(0, code & 0xFFFF))
        blob.word(enc_movt(0, (code >> 16) & 0xFFFF))
        blob.word(enc_cmp_reg(1, 0))
        blob.word(enc_mov_imm(0, brand_id, COND_EQ))
        blob.word(enc_bx_lr(COND_EQ))
    blob.word(enc_mov_imm(0, 1))
    blob.word(enc_bx_lr())

    brand_func_va = blob.cursor_va
    blob.label("brand_resolver")
    for brand in sorted(brands, key=lambda item: int(item["id"])):
        brand_id = int(brand["id"])
        label = f"brand_ptr_{brand_id}"
        blob.word(enc_cmp_imm(1, brand_id))
        blob.ldr_literal(0, label, COND_EQ)
        blob.word(enc_bx_lr(COND_EQ))
    blob.ldr_literal(0, "brand_ptr_1")
    blob.word(enc_bx_lr())

    for brand in sorted(brands, key=lambda item: int(item["id"])):
        brand_id = int(brand["id"])
        label = f"brand_ptr_{brand_id}"
        if brand_id == 0:
            blob.label(label)
            blob.data_u32(ORIGINAL_ELEGOO_STR_VA)
        elif brand_id == 1:
            blob.label(label)
            blob.data_u32(ORIGINAL_GENERIC_STR_VA)
        else:
            blob.string_label(f"brand_name_{brand_id}", brand["name"])
            blob.label(label)
            blob.data_u32(0)

    payload = bytearray(blob.finish())

    # Fill new-brand pointer literals after string labels are known.
    for brand in brands:
        brand_id = int(brand["id"])
        if brand_id <= 1:
            continue
        ptr_label = f"brand_ptr_{brand_id}"
        name_label = f"brand_name_{brand_id}"
        pointer_off = blob.labels[ptr_label] - CAVE_START_VA
        struct.pack_into("<I", payload, pointer_off, blob.labels[name_label])

    return bytes(payload), manufacturer_func_va, brand_func_va


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
    cave_payload, manufacturer_func_va, brand_func_va = build_cave(brands)
    cave_start = off(CAVE_START_VA)
    cave_end_va = CAVE_START_VA + len(cave_payload)
    if cave_end_va > CAVE_LIMIT_VA:
        raise SystemExit(f"RFID brand cave is too large: ends at {cave_end_va:#x}, limit is {CAVE_LIMIT_VA:#x}")
    if any(data[cave_start: cave_start + len(cave_payload)]):
        raise SystemExit("RFID brand cave is not empty; refusing to overwrite another patch.")

    data[cave_start: cave_start + len(cave_payload)] = cave_payload
    write_u32(data, off(MANUFACTURER_RESOLVER_HOOK_VA), enc_b(MANUFACTURER_RESOLVER_HOOK_VA, manufacturer_func_va))
    write_u32(data, off(BRAND_RESOLVER_HOOK_VA), enc_b(BRAND_RESOLVER_HOOK_VA, brand_func_va))

    path.write_bytes(data)
    patched_sha = hashlib.sha256(data).hexdigest()
    print(f"RFID_BRAND_SYNC patched {path}")
    print(f"  before sha256: {original_sha}")
    print(f"  after  sha256: {patched_sha}")
    print(f"  cave: {CAVE_START_VA:#010x}-{cave_end_va - 1:#010x}")
    print(f"  manufacturer resolver hook: {MANUFACTURER_RESOLVER_HOOK_VA:#010x} -> {manufacturer_func_va:#010x}")
    print(f"  brand resolver hook:        {BRAND_RESOLVER_HOOK_VA:#010x} -> {brand_func_va:#010x}")


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"Usage: {Path(argv[0]).name} <path-to-app>", file=sys.stderr)
        return 2
    patch_app(Path(argv[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
