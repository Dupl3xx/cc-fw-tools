#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from tag_codec import (
    colon_commands,
    decode_tag,
    encode_tag,
    load_brands,
    load_materials,
    nfc_tools_commands,
    split_pages,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate CANVAS-compatible NTAG213 filament pages for CC1 firmware 1.4.46."
    )
    parser.add_argument("--brand", help="Brand name from brand_map.json")
    parser.add_argument("--subtype", help="Firmware filament subtype, for example PLA or PETG-CF")
    parser.add_argument("--color", default="000000", help="RGB color as RRGGBB (default: 000000)")
    parser.add_argument("--diameter", type=float, default=1.75, help="Filament diameter in mm")
    parser.add_argument("--weight", type=int, default=1000, help="Spool weight in grams")
    parser.add_argument("--decode", metavar="HEX", help="Decode a 36-byte filament payload")
    parser.add_argument("--list-brands", action="store_true", help="List supported brands")
    parser.add_argument("--list-subtypes", action="store_true", help="List stock firmware subtypes")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.list_brands:
        for brand in load_brands():
            print(f"{brand['id']:>2}  {brand['codes'][0]}  {brand['name']}")
        return 0

    if args.list_subtypes:
        for subtype in load_materials()["subtypes"]:
            print(
                f"{subtype['code']}  {subtype['name']:<18} "
                f"{subtype['min_temp']}-{subtype['max_temp']} C"
            )
        return 0

    if args.decode:
        normalized = "".join(args.decode.split()).replace(":", "")
        try:
            data = bytes.fromhex(normalized)
            profile = decode_tag(data)
        except ValueError as exc:
            parser.error(str(exc))
        print(json.dumps(asdict(profile), indent=2, ensure_ascii=True))
        return 0

    if not args.brand or not args.subtype:
        parser.error("--brand and --subtype are required when generating a tag")

    try:
        data, profile = encode_tag(
            args.brand,
            args.subtype,
            args.color,
            diameter=args.diameter,
            weight=args.weight,
        )
    except ValueError as exc:
        parser.error(str(exc))

    pages = split_pages(data)
    if args.json:
        result = {
            "profile": asdict(profile),
            "payload_hex": data.hex().upper(),
            "pages": {f"{page:02X}": block.hex().upper() for page, block in pages.items()},
            "nfc_tools_commands": nfc_tools_commands(data),
            "colon_commands": colon_commands(data),
        }
        print(json.dumps(result, indent=2, ensure_ascii=True))
        return 0

    print(f"Brand:       {profile.brand} ({profile.manufacturer_code})")
    print(f"Material:    {profile.subtype} / {profile.material}")
    print(f"Color:       {profile.color}")
    print(f"Temperature: {profile.min_temp}-{profile.max_temp} C")
    print(f"Spool:       {profile.diameter:.2f} mm / {profile.weight} g")
    print()
    print("NFC Tools - Other > Advanced NFC commands:")
    for command in nfc_tools_commands(data):
        print(command)
    print()
    print("Compact page notation:")
    for command in colon_commands(data):
        print(command)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
