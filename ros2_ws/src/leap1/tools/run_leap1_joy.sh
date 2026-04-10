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

JOY_DEVICE_ID="${LEAP1_JOY_DEVICE_ID:-0}"
JOY_DEADZONE="${LEAP1_JOY_DEADZONE:-0.15}"
JOY_AUTOREPEAT_RATE="${LEAP1_JOY_AUTOREPEAT_RATE:-20.0}"
REQUIRE_ENABLE_BUTTON="${LEAP1_REQUIRE_ENABLE_BUTTON:-false}"
ENABLE_BUTTON="${LEAP1_ENABLE_BUTTON:-4}"
AXIS_LINEAR_X="${LEAP1_AXIS_LINEAR_X:-1}"
SCALE_LINEAR_X="${LEAP1_SCALE_LINEAR_X:-0.25}"
AXIS_ANGULAR_YAW="${LEAP1_AXIS_ANGULAR_YAW:-0}"
SCALE_ANGULAR_YAW="${LEAP1_SCALE_ANGULAR_YAW:-0.8}"

cleanup() {
  local exit_code=$?
  trap - EXIT INT TERM
  if [[ -n "${TELEOP_PID:-}" ]] && kill -0 "${TELEOP_PID}" 2>/dev/null; then
    kill "${TELEOP_PID}" 2>/dev/null || true
    wait "${TELEOP_PID}" 2>/dev/null || true
  fi
  if [[ -n "${JOY_PID:-}" ]] && kill -0 "${JOY_PID}" 2>/dev/null; then
    kill "${JOY_PID}" 2>/dev/null || true
    wait "${JOY_PID}" 2>/dev/null || true
  fi
  exit "${exit_code}"
}

trap cleanup EXIT INT TERM

set +u
source /opt/ros/humble/setup.bash
source "${WS_ROOT}/install/setup.bash"
set -u

echo "[Leap1 Joy] 工作区: ${WS_ROOT}"
echo "[Leap1 Joy] 手柄设备: /dev/input/js${JOY_DEVICE_ID}"
echo "[Leap1 Joy] 线速度比例: ${SCALE_LINEAR_X}"
echo "[Leap1 Joy] 角速度比例: ${SCALE_ANGULAR_YAW}"
echo "[Leap1 Joy] 使能按钮模式: ${REQUIRE_ENABLE_BUTTON}"

ros2 run joy joy_node --ros-args \
  -p device_id:="${JOY_DEVICE_ID}" \
  -p deadzone:="${JOY_DEADZONE}" \
  -p autorepeat_rate:="${JOY_AUTOREPEAT_RATE}" &
JOY_PID=$!

sleep 1

ros2 run teleop_twist_joy teleop_node --ros-args \
  -r cmd_vel:=/cmd_vel \
  -p require_enable_button:="${REQUIRE_ENABLE_BUTTON}" \
  -p enable_button:="${ENABLE_BUTTON}" \
  -p axis_linear.x:="${AXIS_LINEAR_X}" \
  -p scale_linear.x:="${SCALE_LINEAR_X}" \
  -p axis_angular.yaw:="${AXIS_ANGULAR_YAW}" \
  -p scale_angular.yaw:="${SCALE_ANGULAR_YAW}" &
TELEOP_PID=$!

echo "[Leap1 Joy] 已启动 joy_node 与 teleop_twist_joy，按 Ctrl+C 退出。"

wait -n "${JOY_PID}" "${TELEOP_PID}"
