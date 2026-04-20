#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WS_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
DEFAULT_A20_RUNTIME_ROOT="$(cd "${WS_ROOT}/.." && pwd)/runtime/a20"

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

# 强制把系统 C++ 运行时放到最前，避免误命中 Miniconda 的 libstdc++。
LD_PATH_ENTRIES=(
  "/usr/lib/x86_64-linux-gnu"
  "/opt/ros/humble/opt/rviz_ogre_vendor/lib"
  "/opt/ros/humble/lib/x86_64-linux-gnu"
  "/opt/ros/humble/lib"
  "/usr/lib/x86_64-linux-gnu/gazebo-11/plugins"
  "/usr/local/cuda-12.9/lib64"
)
export LD_LIBRARY_PATH="$(IFS=:; echo "${LD_PATH_ENTRIES[*]}")"
export LEAP1_A20_RUNTIME_ROOT="${LEAP1_A20_RUNTIME_ROOT:-${DEFAULT_A20_RUNTIME_ROOT}}"

set +u
source /opt/ros/humble/setup.bash
source "${WS_ROOT}/install/setup.bash"
set -u

DEFAULT_ARGS=()
[[ -n "${LEAP1_AGENT_TRANSPORT:-}" ]] && DEFAULT_ARGS+=("agent_transport:=${LEAP1_AGENT_TRANSPORT}")
[[ -n "${LEAP1_AGENT_SERIAL_DEV:-}" ]] && DEFAULT_ARGS+=("agent_serial_dev:=${LEAP1_AGENT_SERIAL_DEV}")
[[ -n "${LEAP1_AGENT_SERIAL_BAUD:-}" ]] && DEFAULT_ARGS+=("agent_serial_baud:=${LEAP1_AGENT_SERIAL_BAUD}")
[[ -n "${LEAP1_WITH_A20_STACK:-}" ]] && DEFAULT_ARGS+=("with_a20_stack:=${LEAP1_WITH_A20_STACK}")
[[ -n "${LEAP1_WITH_WEB_TELEOP:-}" ]] && DEFAULT_ARGS+=("with_vehicle_web_teleop:=${LEAP1_WITH_WEB_TELEOP}")
[[ -n "${LEAP1_MAPPING_BACKEND:-}" ]] && DEFAULT_ARGS+=("mapping_backend:=${LEAP1_MAPPING_BACKEND}")
[[ -n "${LEAP1_NAV_PROFILE:-}" ]] && DEFAULT_ARGS+=("nav_profile:=${LEAP1_NAV_PROFILE}")
[[ -n "${LEAP1_LIDAR_BACKEND:-}" ]] && DEFAULT_ARGS+=("lidar_backend:=${LEAP1_LIDAR_BACKEND}")
[[ -n "${LEAP1_MAP_YAML:-}" ]] && DEFAULT_ARGS+=("map_yaml:=${LEAP1_MAP_YAML}")
[[ -n "${LEAP1_WITH_KEEPOUT_FILTER:-}" ]] && DEFAULT_ARGS+=("with_keepout_filter:=${LEAP1_WITH_KEEPOUT_FILTER}")
[[ -n "${LEAP1_KEEPOUT_MASK_YAML:-}" ]] && DEFAULT_ARGS+=("keepout_mask_yaml:=${LEAP1_KEEPOUT_MASK_YAML}")
[[ -n "${LEAP1_WITH_VEHICLE_CAMERA:-}" ]] && DEFAULT_ARGS+=("with_vehicle_camera:=${LEAP1_WITH_VEHICLE_CAMERA}")
[[ -n "${LEAP1_WITH_FLAME_DETECTOR:-}" ]] && DEFAULT_ARGS+=("with_flame_detector:=${LEAP1_WITH_FLAME_DETECTOR}")
[[ -n "${LEAP1_WITH_YOLO_DETECTOR:-}" ]] && DEFAULT_ARGS+=("with_yolo_detector:=${LEAP1_WITH_YOLO_DETECTOR}")
[[ -n "${LEAP1_WITH_GROUND_CAMERA:-}" ]] && DEFAULT_ARGS+=("with_ground_camera:=${LEAP1_WITH_GROUND_CAMERA}")
[[ -n "${LEAP1_WITH_GROUND_YOLO_DETECTOR:-}" ]] && DEFAULT_ARGS+=("with_ground_yolo_detector:=${LEAP1_WITH_GROUND_YOLO_DETECTOR}")
[[ -n "${LEAP1_VEHICLE_CAMERA_DEVICE:-}" ]] && DEFAULT_ARGS+=("vehicle_camera_device:=${LEAP1_VEHICLE_CAMERA_DEVICE}")
[[ -n "${LEAP1_GROUND_CAMERA_DEVICE:-}" ]] && DEFAULT_ARGS+=("ground_camera_device:=${LEAP1_GROUND_CAMERA_DEVICE}")
[[ -n "${LEAP1_YOLO_MODEL_PATH:-}" ]] && DEFAULT_ARGS+=("yolo_model_path:=${LEAP1_YOLO_MODEL_PATH}")
[[ -n "${LEAP1_GROUND_CAMERA_RESPONSE_ROUTE_ID:-}" ]] && DEFAULT_ARGS+=("ground_camera_response_route_id:=${LEAP1_GROUND_CAMERA_RESPONSE_ROUTE_ID}")
[[ -n "${LEAP1_A20_RUNTIME_ROOT:-}" ]] && DEFAULT_ARGS+=("a20_runtime_root:=${LEAP1_A20_RUNTIME_ROOT}")
[[ -n "${LEAP1_A20_WEB_PORT:-}" ]] && DEFAULT_ARGS+=("a20_web_port:=${LEAP1_A20_WEB_PORT}")
[[ -n "${LEAP1_CENTER_PANEL_MODE:-}" ]] && DEFAULT_ARGS+=("center_panel_mode:=${LEAP1_CENTER_PANEL_MODE}")
[[ -n "${LEAP1_WITH_MANUAL_FIRE_TOOLS:-}" ]] && DEFAULT_ARGS+=("with_manual_fire_tools:=${LEAP1_WITH_MANUAL_FIRE_TOOLS}")
[[ -n "${LEAP1_WITH_AUX_DETECTION_PLACEHOLDERS:-}" ]] && DEFAULT_ARGS+=("with_aux_detection_placeholders:=${LEAP1_WITH_AUX_DETECTION_PLACEHOLDERS}")

ros2 launch xuegecar_bringup leap1_stack.launch.py "${DEFAULT_ARGS[@]}" "$@"
