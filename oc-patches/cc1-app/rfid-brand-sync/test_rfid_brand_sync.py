#!/usr/bin/env python3
from __future__ import annotations

import struct
import sys
import tempfile
import unittest
from pathlib import Path


PATCH_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PATCH_DIR))

import patch_app  # noqa: E402
import tag_codec  # noqa: E402


class BrandMapTests(unittest.TestCase):
    def test_map_is_valid_and_contiguous(self) -> None:
        brands = patch_app.load_brand_map()
        self.assertEqual([item["id"] for item in brands], list(range(len(brands))))
        self.assertEqual(brands[0]["codes"], ["EEEEEEEE"])
        self.assertEqual(brands[2]["name"], "Prusament")
        self.assertEqual(brands[3]["name"], "Bambu Lab")
        self.assertEqual(brands[4]["name"], "Plasty Mladec")

    def test_every_custom_brand_passes_canvas_identify_page(self) -> None:
        for brand in patch_app.load_brand_map():
            with self.subTest(brand=brand["name"]):
                manufacturer = bytes.fromhex(brand["codes"][0])
                self.assertEqual(
                    bytes([tag_codec.TAG_HEADER]) + manufacturer[:3],
                    tag_codec.CANVAS_IDENTIFY_PAGE,
                )
                if brand["id"] > 0:
                    self.assertEqual(manufacturer[3], brand["id"])

    def test_compact_caves_fit_allocations(self) -> None:
        brands = patch_app.load_brand_map()
        manufacturer = patch_app.build_manufacturer_cave(brands)
        resolver = patch_app.build_brand_cave(brands)
        self.assertLessEqual(
            patch_app.MANUFACTURER_CAVE_START_VA + len(manufacturer),
            patch_app.MANUFACTURER_CAVE_LIMIT_VA,
        )
        self.assertLessEqual(
            patch_app.BRAND_CAVE_START_VA + len(resolver),
            patch_app.BRAND_CAVE_LIMIT_VA,
        )


class TagCodecTests(unittest.TestCase):
    def test_prusament_pla_matches_known_working_layout(self) -> None:
        data, profile = tag_codec.encode_tag("Prusament", "PLA", "FF3700")
        pages = tag_codec.split_pages(data)
        expected = {
            0x10: "36EEEEEE",
            0x11: "02000000",
            0x12: "00807665",
            0x13: "00000000",
            0x14: "FF3700FF",
            0x15: "00BE00E6",
            0x16: "00000000",
            0x17: "00AF03E8",
            0x18: "0036C800",
        }
        self.assertEqual(
            {page: block.hex().upper() for page, block in pages.items()},
            expected,
        )
        self.assertEqual(profile.brand, "Prusament")

    def test_original_elegoo_tag_remains_unchanged(self) -> None:
        data, _ = tag_codec.encode_tag("ELEGOO", "PLA-CF", "FF3700")
        pages = tag_codec.split_pages(data)
        self.assertEqual(pages[0x10].hex().upper(), "36EEEEEE")
        self.assertEqual(pages[0x11].hex().upper(), "EE000000")
        self.assertEqual(pages[0x13].hex().upper(), "00040000")
        self.assertEqual(pages[0x15].hex().upper(), "00D200F0")

    def test_round_trip(self) -> None:
        data, expected = tag_codec.encode_tag(
            "Bambu Lab",
            "PETG-CF",
            "123ABC",
            diameter=1.75,
            weight=750,
        )
        actual = tag_codec.decode_tag(data)
        self.assertEqual(actual, expected)

    def test_material_tables_match_firmware_counts(self) -> None:
        material_map = tag_codec.load_materials()
        self.assertEqual(len(material_map["materials"]), 15)
        self.assertEqual(len(material_map["subtypes"]), 50)
        self.assertEqual(tag_codec.find_subtype("PPS-CF")["code"], "0E01")
        self.assertEqual(tag_codec.find_subtype("PAHT-CF")["code"], "0402")

    def test_unknown_manufacturer_decodes_as_generic(self) -> None:
        data, _ = tag_codec.encode_tag("Prusament", "PLA", "000000")
        changed = bytearray(data)
        changed[4] = 0x7F
        profile = tag_codec.decode_tag(bytes(changed))
        self.assertEqual(profile.brand, "Generic")


class BinaryPatchTests(unittest.TestCase):
    def make_synthetic_app(self) -> Path:
        size = patch_app.off(patch_app.BRAND_CAVE_LIMIT_VA) + 0x100
        data = bytearray(size)
        for va, expected in patch_app.EXPECTED_HOOK_BYTES.items():
            start = patch_app.off(va)
            data[start:start + len(expected)] = expected
        handle = tempfile.NamedTemporaryFile(prefix="rfid-brand-test-", delete=False)
        handle.write(data)
        handle.close()
        return Path(handle.name)

    def test_patch_writes_both_hooks_and_tables(self) -> None:
        path = self.make_synthetic_app()
        self.addCleanup(path.unlink, missing_ok=True)
        patch_app.patch_app(path)
        data = path.read_bytes()

        manufacturer_hook = struct.unpack_from(
            "<I", data, patch_app.off(patch_app.MANUFACTURER_RESOLVER_HOOK_VA)
        )[0]
        brand_hook = struct.unpack_from(
            "<I", data, patch_app.off(patch_app.BRAND_RESOLVER_HOOK_VA)
        )[0]
        self.assertEqual(
            manufacturer_hook,
            patch_app.enc_b(
                patch_app.MANUFACTURER_RESOLVER_HOOK_VA,
                patch_app.MANUFACTURER_CAVE_START_VA,
            ),
        )
        self.assertEqual(
            brand_hook,
            patch_app.enc_b(
                patch_app.BRAND_RESOLVER_HOOK_VA,
                patch_app.BRAND_CAVE_START_VA,
            ),
        )
        self.assertIn(
            b"Prusament\0",
            data[
                patch_app.off(patch_app.BRAND_CAVE_START_VA):
                patch_app.off(patch_app.BRAND_CAVE_LIMIT_VA)
            ],
        )

    def test_patch_refuses_unknown_firmware(self) -> None:
        path = self.make_synthetic_app()
        self.addCleanup(path.unlink, missing_ok=True)
        data = bytearray(path.read_bytes())
        data[patch_app.off(patch_app.BRAND_RESOLVER_HOOK_VA)] ^= 0xFF
        path.write_bytes(data)
        with self.assertRaises(SystemExit):
            patch_app.patch_app(path)


if __name__ == "__main__":
    unittest.main()
