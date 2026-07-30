#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import secrets
import socket
import time
from typing import Any

import websockets


DISCOVERY_PORT = 3000
SDCP_PORT = 3030
MATERIAL_INFO_COMMAND = 324


def discover_printer(host: str, timeout: float) -> dict[str, Any]:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
        client.settimeout(timeout)
        client.sendto(b"M99999", (host, DISCOVERY_PORT))
        payload, source = client.recvfrom(65_535)
    if source[0] != host:
        raise RuntimeError(f"Discovery response came from unexpected host {source[0]}")

    response = json.loads(payload.decode("utf-8"))
    details = response.get("Data")
    if not isinstance(details, dict):
        raise RuntimeError("Discovery response does not contain Data")
    if not details.get("MainboardID") or not response.get("Id"):
        raise RuntimeError("Discovery response is missing printer identifiers")
    return response


def build_material_request(
    printer_id: str,
    mainboard_id: str,
    request_id: str | None = None,
    timestamp: int | None = None,
) -> dict[str, Any]:
    return {
        "Id": printer_id,
        "Data": {
            "Cmd": MATERIAL_INFO_COMMAND,
            "Data": {},
            "RequestID": request_id or secrets.token_hex(16),
            "MainboardID": mainboard_id,
            "TimeStamp": timestamp if timestamp is not None else int(time.time()),
            "From": 0,
        },
        "Topic": f"sdcp/request/{mainboard_id}",
    }


async def query_materials(
    host: str,
    discovery: dict[str, Any],
    timeout: float,
) -> dict[str, Any]:
    details = discovery["Data"]
    request = build_material_request(discovery["Id"], details["MainboardID"])
    request_id = request["Data"]["RequestID"]
    uri = f"ws://{host}:{SDCP_PORT}/websocket"

    async with websockets.connect(uri, open_timeout=timeout) as websocket:
        await websocket.send(json.dumps(request, separators=(",", ":")))
        async with asyncio.timeout(timeout):
            while True:
                response = json.loads(await websocket.recv())
                if response.get("Data", {}).get("RequestID") == request_id:
                    return response


def material_payload(response: dict[str, Any]) -> dict[str, Any]:
    data = response.get("Data", {}).get("Data")
    if not isinstance(data, dict):
        raise RuntimeError("Cmd 324 response does not contain material data")
    if data.get("Ack") != 0:
        raise RuntimeError(f"Cmd 324 failed with Ack={data.get('Ack')!r}")
    return data


def trays_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    trays: list[dict[str, Any]] = []
    for canvas in payload.get("canvas_list", []):
        canvas_id = canvas.get("canvas_id")
        for tray in canvas.get("tray_list", []):
            trays.append({"canvas_id": canvas_id, **tray})
    return trays


def brand_matches(
    trays: list[dict[str, Any]],
    expected_brand: str,
    tray_id: int | None,
) -> bool:
    candidates = trays
    if tray_id is not None:
        candidates = [tray for tray in trays if tray.get("tray_id") == tray_id]
    return any(
        str(tray.get("brand", "")).casefold() == expected_brand.casefold()
        for tray in candidates
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read CANVAS filament data through the same SDCP Cmd 324 used by Elegoo Slicer."
    )
    parser.add_argument("host", help="Printer IPv4 address")
    parser.add_argument("--timeout", type=float, default=5.0, help="Network timeout in seconds")
    parser.add_argument("--json", action="store_true", help="Print the complete response as JSON")
    parser.add_argument("--expect-brand", help="Fail unless this brand is present")
    parser.add_argument("--tray", type=int, help="Limit --expect-brand to one tray ID")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        discovery = discover_printer(args.host, args.timeout)
        response = asyncio.run(query_materials(args.host, discovery, args.timeout))
        payload = material_payload(response)
        trays = trays_from_payload(payload)
    except (OSError, TimeoutError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}")
        return 1

    if args.json:
        print(json.dumps(response, indent=2, ensure_ascii=True))
    else:
        details = discovery["Data"]
        print(
            f"{details.get('Name', 'Printer')} {details.get('FirmwareVersion', '')} "
            f"({args.host})"
        )
        print("Canvas Tray Brand                 Type             Color     Temp      Status")
        for tray in trays:
            print(
                f"{tray.get('canvas_id', '?'):>6} "
                f"{tray.get('tray_id', '?'):>4} "
                f"{str(tray.get('brand', '')):<21} "
                f"{str(tray.get('filament_name', '')):<16} "
                f"{str(tray.get('filament_color', '')):<9} "
                f"{tray.get('min_nozzle_temp', '?')}-{tray.get('max_nozzle_temp', '?')} C "
                f"{tray.get('status', '?')}"
            )

    if args.expect_brand and not brand_matches(trays, args.expect_brand, args.tray):
        location = f" in tray {args.tray}" if args.tray is not None else ""
        print(f"FAIL: brand {args.expect_brand!r} was not found{location}")
        return 1
    if args.expect_brand:
        location = f" in tray {args.tray}" if args.tray is not None else ""
        print(f"PASS: brand {args.expect_brand!r} found{location}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
