#!/usr/bin/env python3
from __future__ import annotations

import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PATCH_DIR = Path(__file__).resolve().parent
SPOOF_PATCH = PATCH_DIR.parent / "spoof-slicer-firmware-version" / "patch.py"
SPOOF_CAVE_VA = 0x00451048
SPOOF_SITES = (0x0036859C, 0x0036A98C, 0x0037E80C)
SPOOF_ORIGINAL = bytes.fromhex("38 3a 09 e3 40 30 40 e3")
SPOOF_RELOCATED = bytes.fromhex("48 30 01 e3 45 30 40 e3")
sys.path.insert(0, str(PATCH_DIR))

import patch_app  # noqa: E402
import tag_codec  # noqa: E402
import live_verify  # noqa: E402


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
        self.assertLessEqual(
            patch_app.BRAND_CAVE_START_VA + len(resolver),
            SPOOF_CAVE_VA,
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
        size = max(
            patch_app.off(patch_app.BRAND_CAVE_LIMIT_VA) + 0x100,
            max(patch_app.off(site) for site in SPOOF_SITES) + len(SPOOF_ORIGINAL),
        )
        data = bytearray(size)
        for va, expected in patch_app.EXPECTED_HOOK_BYTES.items():
            start = patch_app.off(va)
            data[start:start + len(expected)] = expected
        for site in SPOOF_SITES:
            start = patch_app.off(site)
            data[start:start + len(SPOOF_ORIGINAL)] = SPOOF_ORIGINAL
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

    def test_slicer_spoof_can_follow_rfid_without_overlap(self) -> None:
        source = self.make_synthetic_app()
        self.addCleanup(source.unlink, missing_ok=True)
        patch_app.patch_app(source)

        with tempfile.TemporaryDirectory(prefix="rfid-spoof-test-") as root:
            app_dir = Path(root) / "app"
            app_dir.mkdir()
            target = app_dir / "app"
            shutil.copyfile(source, target)
            env = {
                **os.environ,
                "SQUASHFS_ROOT": root,
                "FW_VER": "1.4.46",
            }
            result = subprocess.run(
                [sys.executable, str(SPOOF_PATCH)],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            data = target.read_bytes()

        for site in SPOOF_SITES:
            self.assertEqual(
                data[patch_app.off(site):patch_app.off(site) + len(SPOOF_RELOCATED)],
                SPOOF_RELOCATED,
            )
        self.assertEqual(
            data[
                patch_app.off(SPOOF_CAVE_VA):
                patch_app.off(SPOOF_CAVE_VA) + len(b"1.4.46\0")
            ],
            b"1.4.46\0",
        )
        self.assertIn(
            b"Prusament\0",
            data[
                patch_app.off(patch_app.BRAND_CAVE_START_VA):
                patch_app.off(patch_app.BRAND_CAVE_LIMIT_VA)
            ],
        )

    def test_slicer_spoof_refuses_occupied_cave_without_partial_patch(self) -> None:
        source = self.make_synthetic_app()
        self.addCleanup(source.unlink, missing_ok=True)
        patch_app.patch_app(source)

        with tempfile.TemporaryDirectory(prefix="rfid-spoof-collision-") as root:
            app_dir = Path(root) / "app"
            app_dir.mkdir()
            target = app_dir / "app"
            shutil.copyfile(source, target)
            data = bytearray(target.read_bytes())
            data[patch_app.off(SPOOF_CAVE_VA)] = 1
            target.write_bytes(data)
            env = {
                **os.environ,
                "SQUASHFS_ROOT": root,
                "FW_VER": "1.4.46",
            }
            result = subprocess.run(
                [sys.executable, str(SPOOF_PATCH)],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            after = target.read_bytes()

        for site in SPOOF_SITES:
            self.assertEqual(
                after[patch_app.off(site):patch_app.off(site) + len(SPOOF_ORIGINAL)],
                SPOOF_ORIGINAL,
            )


class LiveVerifyTests(unittest.TestCase):
    def test_cmd_324_request_matches_sdcp_wire_format(self) -> None:
        request = live_verify.build_material_request(
            "printer-id",
            "mainboard-id",
            request_id="request-id",
            timestamp=123,
        )
        self.assertEqual(request["Id"], "printer-id")
        self.assertEqual(request["Topic"], "sdcp/request/mainboard-id")
        self.assertEqual(request["Data"]["Cmd"], 324)
        self.assertEqual(request["Data"]["RequestID"], "request-id")
        self.assertEqual(request["Data"]["MainboardID"], "mainboard-id")
        self.assertEqual(request["Data"]["TimeStamp"], 123)
        self.assertEqual(request["Data"]["From"], 0)

    def test_tray_flattening_and_brand_expectation(self) -> None:
        payload = {
            "canvas_list": [
                {
                    "canvas_id": 0,
                    "tray_list": [
                        {"tray_id": 0, "brand": "ELEGOO"},
                        {"tray_id": 1, "brand": "Prusament"},
                    ],
                }
            ]
        }
        trays = live_verify.trays_from_payload(payload)
        self.assertEqual(trays[1]["canvas_id"], 0)
        self.assertTrue(live_verify.brand_matches(trays, "prusament", 1))
        self.assertFalse(live_verify.brand_matches(trays, "Prusament", 0))

    def test_material_response_requires_success_ack(self) -> None:
        response = {"Data": {"Data": {"Ack": 7}}}
        with self.assertRaises(RuntimeError):
            live_verify.material_payload(response)


if __name__ == "__main__":
    unittest.main()
