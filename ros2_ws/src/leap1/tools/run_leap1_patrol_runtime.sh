#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export LEAP1_AGENT_TRANSPORT="${LEAP1_AGENT_TRANSPORT:-external_serial}"
export LEAP1_AGENT_SERIAL_DEV="${LEAP1_AGENT_SERIAL_DEV:-/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0}"
export LEAP1_AGENT_SERIAL_BAUD="${LEAP1_AGENT_SERIAL_BAUD:-921600}"
export LEAP1_MAPPING_BACKEND="${LEAP1_MAPPING_BACKEND:-slam_toolbox}"
export LEAP1_NAV_PROFILE="${LEAP1_NAV_PROFILE:-stable}"
export LEAP1_LIDAR_BACKEND="${LEAP1_LIDAR_BACKEND:-ydlidar}"
export LEAP1_WITH_A20_STACK=true
export LEAP1_WITH_WEB_TELEOP=false
export LEAP1_WITH_VEHICLE_CAMERA="${LEAP1_WITH_VEHICLE_CAMERA:-true}"
export LEAP1_WITH_GROUND_CAMERA=false
export LEAP1_WITH_KEEPOUT_FILTER="${LEAP1_WITH_KEEPOUT_FILTER:-true}"
export LEAP1_VEHICLE_CAMERA_DEVICE="${LEAP1_VEHICLE_CAMERA_DEVICE:-/dev/video0}"
export LEAP1_WITH_YOLO_DETECTOR="${LEAP1_WITH_YOLO_DETECTOR:-true}"
export LEAP1_YOLO_MODEL_PATH="${LEAP1_YOLO_MODEL_PATH:-}"
export LEAP1_A20_TOPIC_PREFIX="${LEAP1_A20_TOPIC_PREFIX:-/a20}"
export LEAP1_PREFLIGHT_MODE=vehicle

echo "[Leap1 Patrol Runtime] 启动车端巡航运行态"
echo "[Leap1 Patrol Runtime] mapping_backend=${LEAP1_MAPPING_BACKEND} nav_profile=${LEAP1_NAV_PROFILE}"
"${SCRIPT_DIR}/run_leap1_preflight.sh"
"${SCRIPT_DIR}/run_leap1_stack.sh" backend:=real with_mapping:=false with_navigation:=true with_rviz:=false "$@"
