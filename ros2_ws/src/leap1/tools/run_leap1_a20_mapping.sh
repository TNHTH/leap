#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export LEAP1_AGENT_TRANSPORT="${LEAP1_AGENT_TRANSPORT:-external_serial}"
export LEAP1_AGENT_SERIAL_DEV="${LEAP1_AGENT_SERIAL_DEV:-/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0}"
export LEAP1_AGENT_SERIAL_BAUD="${LEAP1_AGENT_SERIAL_BAUD:-921600}"
export LEAP1_WITH_A20_STACK=true
export LEAP1_WITH_WEB_TELEOP=true
export LEAP1_WITH_KEEPOUT_FILTER="${LEAP1_WITH_KEEPOUT_FILTER:-false}"
export LEAP1_WITH_VEHICLE_CAMERA="${LEAP1_WITH_VEHICLE_CAMERA:-true}"
export LEAP1_WITH_GROUND_CAMERA="${LEAP1_WITH_GROUND_CAMERA:-true}"
export LEAP1_VEHICLE_CAMERA_DEVICE="${LEAP1_VEHICLE_CAMERA_DEVICE:-/dev/video0}"
export LEAP1_GROUND_CAMERA_DEVICE="${LEAP1_GROUND_CAMERA_DEVICE:-}"
export LEAP1_A20_WEB_PORT="${LEAP1_A20_WEB_PORT:-8090}"
export LEAP1_A20_RUNTIME_ROOT="${LEAP1_A20_RUNTIME_ROOT:-}"
export LEAP1_KEEPOUT_MASK_YAML="${LEAP1_KEEPOUT_MASK_YAML:-}"
export LEAP1_A20_TOPIC_PREFIX="${LEAP1_A20_TOPIC_PREFIX:-/a20}"

echo "[Leap1 A20 Mapping] 将启动 external serial micro-ROS + bringup + gmapping + Nav2 + 广播中心"
echo "[Leap1 A20 Mapping] Web 面板: http://127.0.0.1:${LEAP1_A20_WEB_PORT}/"
echo "[Leap1 A20 Mapping] 话题前缀: ${LEAP1_A20_TOPIC_PREFIX}"

"${SCRIPT_DIR}/run_leap1_stack.sh" backend:=real with_mapping:=true with_navigation:=true with_rviz:=false "$@"
