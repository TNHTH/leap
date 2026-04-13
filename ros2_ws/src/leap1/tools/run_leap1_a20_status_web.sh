#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WS_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

export PATH="/usr/bin:/bin:/usr/sbin:/sbin:${PATH}"
unset PYTHONPATH
unset CONDA_PREFIX
unset CONDA_DEFAULT_ENV
unset CONDA_EXE
unset CONDA_PYTHON_EXE
unset CONDA_SHLVL
unset AMENT_PREFIX_PATH
unset COLCON_PREFIX_PATH
unset CMAKE_PREFIX_PATH
unset _CE_CONDA
unset _CE_M

set +u
source /opt/ros/humble/setup.bash
source "${WS_ROOT}/install/setup.bash"
set -u

export LEAP1_A20_RUNTIME_ROOT="${LEAP1_A20_RUNTIME_ROOT:-${WS_ROOT}/../runtime/a20}"
export LEAP1_A20_WEB_PORT="${LEAP1_A20_WEB_PORT:-8090}"
export LEAP1_PANEL_MODE="${LEAP1_PANEL_MODE:-status_only}"
export LEAP1_REQUIRE_ODOM="${LEAP1_REQUIRE_ODOM:-false}"
export LEAP1_REQUIRE_VEHICLE_CAMERA="${LEAP1_REQUIRE_VEHICLE_CAMERA:-false}"
export LEAP1_WITH_WEB_PANEL="${LEAP1_WITH_WEB_PANEL:-true}"
export LEAP1_WITH_VEHICLE_CAMERA="${LEAP1_WITH_VEHICLE_CAMERA:-true}"
export LEAP1_WITH_GROUND_CAMERA="${LEAP1_WITH_GROUND_CAMERA:-false}"
export LEAP1_VEHICLE_CAMERA_DEVICE="${LEAP1_VEHICLE_CAMERA_DEVICE:-/dev/video0}"
export LEAP1_GROUND_CAMERA_DEVICE="${LEAP1_GROUND_CAMERA_DEVICE:-}"
export LEAP1_FRONT_CAMERA_PORT="${LEAP1_FRONT_CAMERA_PORT:-8091}"
export LEAP1_GROUND_CAMERA_PORT="${LEAP1_GROUND_CAMERA_PORT:-8092}"
export LEAP1_A20_TOPIC_PREFIX="${LEAP1_A20_TOPIC_PREFIX:-/a20}"

DEFAULT_ARGS=(
  "panel_mode:=${LEAP1_PANEL_MODE}"
  "require_odom:=${LEAP1_REQUIRE_ODOM}"
  "require_vehicle_camera:=${LEAP1_REQUIRE_VEHICLE_CAMERA}"
  "runtime_root:=${LEAP1_A20_RUNTIME_ROOT}"
  "with_web_panel:=${LEAP1_WITH_WEB_PANEL}"
  "with_vehicle_camera:=${LEAP1_WITH_VEHICLE_CAMERA}"
  "with_ground_camera:=${LEAP1_WITH_GROUND_CAMERA}"
  "web_bind_port:=${LEAP1_A20_WEB_PORT}"
  "front_camera_port:=${LEAP1_FRONT_CAMERA_PORT}"
  "ground_camera_port:=${LEAP1_GROUND_CAMERA_PORT}"
)

if [[ -n "${LEAP1_VEHICLE_CAMERA_DEVICE}" ]]; then
  DEFAULT_ARGS+=("vehicle_camera_device:=${LEAP1_VEHICLE_CAMERA_DEVICE}")
fi

if [[ -n "${LEAP1_GROUND_CAMERA_DEVICE}" ]]; then
  DEFAULT_ARGS+=("ground_camera_device:=${LEAP1_GROUND_CAMERA_DEVICE}")
fi

echo "[Leap A20 Status Web] 面板地址: http://127.0.0.1:${LEAP1_A20_WEB_PORT}/"
echo "[Leap A20 Status Web] 面板模式: ${LEAP1_PANEL_MODE}"
echo "[Leap A20 Status Web] 话题前缀: ${LEAP1_A20_TOPIC_PREFIX}"
echo "[Leap A20 Status Web] 车载相机启用: ${LEAP1_WITH_VEHICLE_CAMERA}"
echo "[Leap A20 Status Web] 地面相机启用: ${LEAP1_WITH_GROUND_CAMERA}"

ros2 launch leap1_a20 a20_vehicle.launch.py "${DEFAULT_ARGS[@]}" "$@"
