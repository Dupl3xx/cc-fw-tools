#!/usr/bin/env bash
set -euo pipefail

# spoof-slicer-firmware-version patch for CC1 app 1.4.46
#
# Repoints the firmware-version source pointer used by slicer-facing SDCP
# attribute responses (UDP discovery and WebSocket request attribute) to a code
# cave containing "1.4.46\0".  The original version string used by logs/UI/OTA
# remains at VA 0x00409a38.

if [[ ${UID} -ne 0 ]]; then
  echo "Error: Please run as root." >&2
  exit 1
fi

case "${FW_VER:?FW_VER is required}" in
  1.4.46) ;;
  *)
    echo "Unsupported firmware version for spoof-slicer-firmware-version patch: $FW_VER" >&2
    exit 1
    ;;
esac

python3 "${CURRENT_PATCH_PATH:?CURRENT_PATCH_PATH is required}/patch.py"
