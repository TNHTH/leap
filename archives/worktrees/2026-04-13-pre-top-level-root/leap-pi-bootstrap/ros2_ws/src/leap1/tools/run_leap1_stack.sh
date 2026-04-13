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

DEFAULT_ARGS=()
[[ -n "${LEAP1_AGENT_TRANSPORT:-}" ]] && DEFAULT_ARGS+=("agent_transport:=${LEAP1_AGENT_TRANSPORT}")
[[ -n "${LEAP1_AGENT_SERIAL_DEV:-}" ]] && DEFAULT_ARGS+=("agent_serial_dev:=${LEAP1_AGENT_SERIAL_DEV}")
[[ -n "${LEAP1_AGENT_SERIAL_BAUD:-}" ]] && DEFAULT_ARGS+=("agent_serial_baud:=${LEAP1_AGENT_SERIAL_BAUD}")
[[ -n "${LEAP1_WITH_A20_STACK:-}" ]] && DEFAULT_ARGS+=("with_a20_stack:=${LEAP1_WITH_A20_STACK}")
[[ -n "${LEAP1_WITH_WEB_TELEOP:-}" ]] && DEFAULT_ARGS+=("with_vehicle_web_teleop:=${LEAP1_WITH_WEB_TELEOP}")
[[ -n "${LEAP1_WITH_KEEPOUT_FILTER:-}" ]] && DEFAULT_ARGS+=("with_keepout_filter:=${LEAP1_WITH_KEEPOUT_FILTER}")
[[ -n "${LEAP1_KEEPOUT_MASK_YAML:-}" ]] && DEFAULT_ARGS+=("keepout_mask_yaml:=${LEAP1_KEEPOUT_MASK_YAML}")
[[ -n "${LEAP1_WITH_VEHICLE_CAMERA:-}" ]] && DEFAULT_ARGS+=("with_vehicle_camera:=${LEAP1_WITH_VEHICLE_CAMERA}")
[[ -n "${LEAP1_WITH_GROUND_CAMERA:-}" ]] && DEFAULT_ARGS+=("with_ground_camera:=${LEAP1_WITH_GROUND_CAMERA}")
[[ -n "${LEAP1_VEHICLE_CAMERA_DEVICE:-}" ]] && DEFAULT_ARGS+=("vehicle_camera_device:=${LEAP1_VEHICLE_CAMERA_DEVICE}")
[[ -n "${LEAP1_GROUND_CAMERA_DEVICE:-}" ]] && DEFAULT_ARGS+=("ground_camera_device:=${LEAP1_GROUND_CAMERA_DEVICE}")
[[ -n "${LEAP1_A20_RUNTIME_ROOT:-}" ]] && DEFAULT_ARGS+=("a20_runtime_root:=${LEAP1_A20_RUNTIME_ROOT}")
[[ -n "${LEAP1_A20_WEB_PORT:-}" ]] && DEFAULT_ARGS+=("a20_web_port:=${LEAP1_A20_WEB_PORT}")

ros2 launch xuegecar_bringup leap1_stack.launch.py "${DEFAULT_ARGS[@]}" "$@"
