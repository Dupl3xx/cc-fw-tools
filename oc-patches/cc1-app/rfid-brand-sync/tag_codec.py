#!/usr/bin/env python3
from __future__ import annotations

import json
import struct
from dataclasses import dataclass
from pathlib import Path


TAG_HEADER = 0x36
FILAMENT_START_PAGE = 0x10
FILAMENT_PAGE_COUNT = 9
FILAMENT_DATA_SIZE = FILAMENT_PAGE_COUNT * 4
CANVAS_IDENTIFY_PAGE = bytes.fromhex("36EEEEEE")
DEFAULT_COLOR_MODIFIER = 0xFF
DEFAULT_PRODUCTION_CODE = bytes.fromhex("0036C800")


def _load_json(name: str) -> dict:
    return json.loads(Path(__file__).with_name(name).read_text(encoding="utf-8"))


def load_brands() -> list[dict]:
    return _load_json("brand_map.json")["brands"]


def load_materials() -> dict:
    return _load_json("material_map.json")


def _find_named(items: list[dict], value: str, kind: str) -> dict:
    matches = [item for item in items if item["name"].casefold() == value.casefold()]
    if len(matches) != 1:
        available = ", ".join(item["name"] for item in items)
        raise ValueError(f"Unknown {kind} {value!r}. Available: {available}")
    return matches[0]


def find_brand(name: str) -> dict:
    return _find_named(load_brands(), name, "brand")


def find_subtype(name: str) -> dict:
    return _find_named(load_materials()["subtypes"], name, "subtype")


def find_material(name: str) -> dict:
    return _find_named(load_materials()["materials"], name, "material")


def parse_rgb(value: str) -> bytes:
    normalized = value.strip().removeprefix("#")
    if len(normalized) != 6:
        raise ValueError("Color must contain exactly six hexadecimal RGB digits")
    try:
        return bytes.fromhex(normalized)
    except ValueError as exc:
        raise ValueError("Color must contain only hexadecimal RGB digits") from exc


@dataclass(frozen=True)
class TagProfile:
    brand: str
    material: str
    subtype: str
    color: str
    min_temp: int
    max_temp: int
    diameter: float
    weight: int
    manufacturer_code: str


def encode_tag(
    brand_name: str,
    subtype_name: str,
    color: str,
    *,
    diameter: float = 1.75,
    weight: int = 1000,
) -> tuple[bytes, TagProfile]:
    brand = find_brand(brand_name)
    subtype = find_subtype(subtype_name)
    material = find_material(subtype["material"])
    rgb = parse_rgb(color)

    diameter_raw = round(diameter * 100)
    if not 1 <= diameter_raw <= 0xFFFF:
        raise ValueError("Diameter is outside the encodable range")
    if not 1 <= weight <= 0xFFFF:
        raise ValueError("Weight is outside the encodable range")

    data = bytearray(FILAMENT_DATA_SIZE)
    data[0] = TAG_HEADER
    data[1:5] = bytes.fromhex(brand["codes"][0])
    data[8:12] = bytes.fromhex(material["code"])
    data[12:14] = bytes.fromhex(subtype["code"])
    data[16:19] = rgb
    data[19] = DEFAULT_COLOR_MODIFIER
    struct.pack_into(">H", data, 20, int(subtype["min_temp"]))
    struct.pack_into(">H", data, 22, int(subtype["max_temp"]))
    struct.pack_into(">H", data, 28, diameter_raw)
    struct.pack_into(">H", data, 30, weight)
    data[32:36] = DEFAULT_PRODUCTION_CODE

    if data[:4] != CANVAS_IDENTIFY_PAGE:
        raise ValueError(
            "Generated tag would be rejected by the CANVAS RFID identify-page filter"
        )

    profile = TagProfile(
        brand=brand["name"],
        material=material["name"],
        subtype=subtype["name"],
        color=f"#{rgb.hex().upper()}",
        min_temp=int(subtype["min_temp"]),
        max_temp=int(subtype["max_temp"]),
        diameter=diameter_raw / 100,
        weight=weight,
        manufacturer_code=brand["codes"][0],
    )
    return bytes(data), profile


def split_pages(data: bytes) -> dict[int, bytes]:
    if len(data) != FILAMENT_DATA_SIZE:
        raise ValueError(f"Filament data must contain {FILAMENT_DATA_SIZE} bytes")
    return {
        FILAMENT_START_PAGE + index: data[index * 4:(index + 1) * 4]
        for index in range(FILAMENT_PAGE_COUNT)
    }


def nfc_tools_commands(data: bytes, separator: str = " ") -> list[str]:
    commands = []
    for page, block in split_pages(data).items():
        parts = [0xA2, page, *block]
        commands.append(separator.join(f"{value:02X}" for value in parts))
    return commands


def colon_commands(data: bytes) -> list[str]:
    return [
        f"A2:{page:02X}:{block.hex().upper()}"
        for page, block in split_pages(data).items()
    ]


def decode_tag(data: bytes) -> TagProfile:
    if len(data) != FILAMENT_DATA_SIZE:
        raise ValueError(f"Filament data must contain {FILAMENT_DATA_SIZE} bytes")
    if data[0] != TAG_HEADER:
        raise ValueError(f"Unexpected tag header: {data[0]:02X}")

    manufacturer_code = data[1:5].hex().upper()
    material_code = data[8:12].hex().upper()
    subtype_code = data[12:14].hex().upper()
    brands = load_brands()
    materials = load_materials()

    brand = next(
        (item for item in brands if manufacturer_code in item["codes"]),
        next(item for item in brands if item["id"] == 1),
    )
    material = next(
        (item for item in materials["materials"] if item["code"] == material_code),
        {"name": f"Unknown ({material_code})"},
    )
    subtype = next(
        (item for item in materials["subtypes"] if item["code"] == subtype_code),
        {
            "name": f"Unknown ({subtype_code})",
            "min_temp": struct.unpack_from(">H", data, 20)[0],
            "max_temp": struct.unpack_from(">H", data, 22)[0],
        },
    )

    return TagProfile(
        brand=brand["name"],
        material=material["name"],
        subtype=subtype["name"],
        color=f"#{data[16:19].hex().upper()}",
        min_temp=struct.unpack_from(">H", data, 20)[0],
        max_temp=struct.unpack_from(">H", data, 22)[0],
        diameter=struct.unpack_from(">H", data, 28)[0] / 100,
        weight=struct.unpack_from(">H", data, 30)[0],
        manufacturer_code=manufacturer_code,
    )
