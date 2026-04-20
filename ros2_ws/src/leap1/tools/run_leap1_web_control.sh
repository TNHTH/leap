#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export LEAP1_PANEL_MODE="${LEAP1_PANEL_MODE:-full_stack}"
export LEAP1_EXPECTED_VEHICLE_CAMERA="${LEAP1_EXPECTED_VEHICLE_CAMERA:-true}"
export LEAP1_WITH_GROUND_CAMERA="${LEAP1_WITH_GROUND_CAMERA:-true}"

exec "${SCRIPT_DIR}/run_leap1_center_console.sh" "$@"
