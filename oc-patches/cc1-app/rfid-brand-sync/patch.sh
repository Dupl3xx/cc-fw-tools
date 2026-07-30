#!/usr/bin/env bash
set -euo pipefail

if [[ ${UID} -ne 0 ]]; then
  echo "Error: Please run as root." >&2
  exit 1
fi

project_root="${REPOSITORY_ROOT:?REPOSITORY_ROOT is required}"
# shellcheck source=/dev/null
source "$project_root/TOOLS/helpers/utils.sh" "$project_root"
check_tools "python3"

case "${FW_VER:?FW_VER is required}" in
  1.4.46)
    ;;
  *)
    echo "Unsupported firmware version for RFID_BRAND_SYNC patch: $FW_VER" >&2
    exit 1
    ;;
esac

cd "${SQUASHFS_ROOT:?SQUASHFS_ROOT is required}/app"
python3 "${CURRENT_PATCH_PATH:?CURRENT_PATCH_PATH is required}/patch_app.py" ./app
