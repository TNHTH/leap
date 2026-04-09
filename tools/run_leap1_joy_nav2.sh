#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export LEAP1_WITH_NAV2=true
export LEAP1_WITH_RVIZ="${LEAP1_WITH_RVIZ:-true}"

exec "${SCRIPT_DIR}/run_leap1_joy_mapping.sh"
