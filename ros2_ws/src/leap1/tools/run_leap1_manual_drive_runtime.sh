#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

JOY_DEVICE_ID="${LEAP1_JOY_DEVICE_ID:-0}"
JOY_DEVICE_PATH="/dev/input/js${JOY_DEVICE_ID}"
VEHICLE_WAIT_SEC="${LEAP1_VEHICLE_RUNTIME_WAIT_SEC:-4}"
START_LOCAL_RUNTIME="${LEAP1_MANUAL_DRIVE_START_LOCAL_RUNTIME:-false}"
REMOTE_VEHICLE_HOST="${LEAP1_REMOTE_VEHICLE_HOST:-10.127.143.229}"

fail() {
  echo "[Leap1 Manual Drive] FAIL: $1" >&2
  exit 1
}

cleanup() {
  local exit_code=$?
  trap - EXIT INT TERM
  if [[ -n "${VEHICLE_PID:-}" ]] && kill -0 "${VEHICLE_PID}" 2>/dev/null; then
    kill "${VEHICLE_PID}" 2>/dev/null || true
    wait "${VEHICLE_PID}" 2>/dev/null || true
  fi
  exit "${exit_code}"
}

trap cleanup EXIT INT TERM

[[ -e "${JOY_DEVICE_PATH}" ]] || fail "找不到手柄设备: ${JOY_DEVICE_PATH}"

export LEAP1_AGENT_TRANSPORT="${LEAP1_AGENT_TRANSPORT:-external_serial}"
export LEAP1_MAPPING_BACKEND="${LEAP1_MAPPING_BACKEND:-slam_toolbox}"
export LEAP1_NAV_PROFILE="${LEAP1_NAV_PROFILE:-stable}"
export LEAP1_WITH_A20_STACK="${LEAP1_WITH_A20_STACK:-true}"
export LEAP1_WITH_WEB_TELEOP="${LEAP1_WITH_WEB_TELEOP:-false}"
export LEAP1_WITH_KEEPOUT_FILTER="${LEAP1_WITH_KEEPOUT_FILTER:-false}"
export LEAP1_WITH_VEHICLE_CAMERA="${LEAP1_WITH_VEHICLE_CAMERA:-true}"
export LEAP1_WITH_GROUND_CAMERA="${LEAP1_WITH_GROUND_CAMERA:-false}"

echo "[Leap1 Manual Drive] 手柄设备: ${JOY_DEVICE_PATH}"
if [[ "${START_LOCAL_RUNTIME}" == "true" ]]; then
  echo "[Leap1 Manual Drive] 模式: 本机先启动车端运行态，再接入 joy teleop"
  "${SCRIPT_DIR}/run_leap1_vehicle_runtime.sh" "$@" &
  VEHICLE_PID=$!
  sleep "${VEHICLE_WAIT_SEC}"
else
  echo "[Leap1 Manual Drive] 模式: 轻量遥控，不启动本地 vehicle runtime"
  echo "[Leap1 Manual Drive] 假设远端树莓派运行态已就绪: ${REMOTE_VEHICLE_HOST}"
fi

exec "${SCRIPT_DIR}/run_leap1_joy.sh"
