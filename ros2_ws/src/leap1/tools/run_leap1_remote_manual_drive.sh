#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export LEAP1_MANUAL_DRIVE_START_LOCAL_RUNTIME="${LEAP1_MANUAL_DRIVE_START_LOCAL_RUNTIME:-false}"

exec "${SCRIPT_DIR}/run_leap1_manual_drive_runtime.sh" "$@"
