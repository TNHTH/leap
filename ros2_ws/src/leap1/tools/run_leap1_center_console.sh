#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WS_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

resolve_hj_ground_camera() {
  local device
  local video_name
  local video_index

  for device in /dev/video2 /dev/video3; do
    [[ -e "${device}" ]] || continue
    video_name="/sys/class/video4linux/${device#/dev/}/name"
    video_index="/sys/class/video4linux/${device#/dev/}/index"
    [[ -r "${video_name}" ]] || continue
    if [[ "$(cat "${video_name}")" != HJ\ USB\ 2.0\ Camera* ]]; then
      continue
    fi
    if [[ -r "${video_index}" ]] && [[ "$(cat "${video_index}")" != "0" ]]; then
      continue
    fi
    echo "${device}"
    return 0
  done

  return 1
}

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
export LEAP1_EXPECTED_VEHICLE_CAMERA="${LEAP1_EXPECTED_VEHICLE_CAMERA:-true}"
export LEAP1_WITH_GROUND_CAMERA="${LEAP1_WITH_GROUND_CAMERA:-true}"
if [[ -z "${LEAP1_GROUND_CAMERA_DEVICE:-}" ]]; then
  LEAP1_GROUND_CAMERA_DEVICE="$(resolve_hj_ground_camera || true)"
fi
export LEAP1_GROUND_CAMERA_DEVICE="${LEAP1_GROUND_CAMERA_DEVICE:-}"
export LEAP1_GROUND_CAMERA_PORT="${LEAP1_GROUND_CAMERA_PORT:-8092}"
export LEAP1_WITH_GROUND_YOLO_DETECTOR="${LEAP1_WITH_GROUND_YOLO_DETECTOR:-true}"
export LEAP1_YOLO_MODEL_PATH="${LEAP1_YOLO_MODEL_PATH:-}"
export LEAP1_GROUND_CAMERA_RESPONSE_ROUTE_ID="${LEAP1_GROUND_CAMERA_RESPONSE_ROUTE_ID:-camera:ground_camera}"
export LEAP1_A20_TOPIC_PREFIX="${LEAP1_A20_TOPIC_PREFIX:-/a20}"
export LEAP1_PREFLIGHT_MODE=center

echo "[Leap1 Center Console] 面板地址: http://127.0.0.1:${LEAP1_A20_WEB_PORT}/"
echo "[Leap1 Center Console] 话题前缀: ${LEAP1_A20_TOPIC_PREFIX}"
echo "[Leap1 Center Console] 固定摄像头: ${LEAP1_GROUND_CAMERA_DEVICE:-disabled}"

"${SCRIPT_DIR}/run_leap1_preflight.sh"

launch_args=(
  "runtime_root:=${LEAP1_A20_RUNTIME_ROOT}"
  "panel_mode:=${LEAP1_PANEL_MODE}"
  "expected_vehicle_camera:=${LEAP1_EXPECTED_VEHICLE_CAMERA}"
  "with_ground_camera:=${LEAP1_WITH_GROUND_CAMERA}"
  "with_ground_yolo_detector:=${LEAP1_WITH_GROUND_YOLO_DETECTOR}"
  "web_bind_port:=${LEAP1_A20_WEB_PORT}"
  "ground_camera_port:=${LEAP1_GROUND_CAMERA_PORT}"
  "ground_camera_response_route_id:=${LEAP1_GROUND_CAMERA_RESPONSE_ROUTE_ID}"
)

if [[ -n "${LEAP1_GROUND_CAMERA_DEVICE}" ]]; then
  launch_args+=("ground_camera_device:=${LEAP1_GROUND_CAMERA_DEVICE}")
fi
if [[ -n "${LEAP1_YOLO_MODEL_PATH}" ]]; then
  launch_args+=("yolo_model_path:=${LEAP1_YOLO_MODEL_PATH}")
fi

ros2 launch leap1_a20 a20_center.launch.py \
  "${launch_args[@]}" \
  "$@"
