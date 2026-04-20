#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
TEMPLATE_PARAMS="${WORKSPACE_ROOT}/src/leap1/xuegecar_bringup/config/ydlidar_udp_bridge.yaml"

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

LIDAR_LINK="${LEAP1_LIDAR_LINK:-/tmp/lidar}"
LIDAR_UDP_PORT="${LEAP1_LIDAR_UDP_PORT:-8889}"
ROS_DOMAIN_ID_VALUE="${LEAP1_LIDAR_ACCEPTANCE_DOMAIN_ID:-77}"
WAIT_READY_SEC="${LEAP1_LIDAR_ACCEPTANCE_WAIT_SEC:-8}"
ECHO_TIMEOUT_SEC="${LEAP1_LIDAR_ACCEPTANCE_ECHO_TIMEOUT_SEC:-5}"
TMP_ROOT="${LEAP1_LIDAR_ACCEPTANCE_TMP:-/dev/shm/leap1-lidar-acceptance}"
PARAMS_FILE="${TMP_ROOT}/ydlidar_udp_bridge.generated.yaml"
SOCAT_LOG="${TMP_ROOT}/socat.log"
YDLIDAR_LOG="${TMP_ROOT}/ydlidar.log"

SOCAT_PID=""
YDLIDAR_PID=""

log() {
  echo "[Lidar Acceptance] $*"
}

fail() {
  echo "[Lidar Acceptance] FAIL: $*" >&2
  exit 1
}

check_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "缺少命令: $1"
}

cleanup() {
  if [[ -n "${YDLIDAR_PID}" ]] && kill -0 "${YDLIDAR_PID}" 2>/dev/null; then
    kill "${YDLIDAR_PID}" 2>/dev/null || true
    wait "${YDLIDAR_PID}" 2>/dev/null || true
  fi
  if [[ -n "${SOCAT_PID}" ]] && kill -0 "${SOCAT_PID}" 2>/dev/null; then
    kill "${SOCAT_PID}" 2>/dev/null || true
    wait "${SOCAT_PID}" 2>/dev/null || true
  fi
}

trap cleanup EXIT

main() {
  set +u
  # shellcheck disable=SC1091
  source /opt/ros/humble/setup.bash
  # shellcheck disable=SC1091
  source "${WORKSPACE_ROOT}/install/setup.bash"
  set -u
  export ROS_DOMAIN_ID="${ROS_DOMAIN_ID_VALUE}"

  check_cmd socat
  check_cmd ros2
  check_cmd timeout
  [[ -f "${TEMPLATE_PARAMS}" ]] || fail "缺少参数模板: ${TEMPLATE_PARAMS}"

  mkdir -p "${TMP_ROOT}"
  rm -f "${LIDAR_LINK}" "${SOCAT_LOG}" "${YDLIDAR_LOG}" "${PARAMS_FILE}"

  sed "s#port: /tmp/lidar#port: ${LIDAR_LINK}#" "${TEMPLATE_PARAMS}" > "${PARAMS_FILE}"

  log "启动 UDP -> PTY 桥接: UDP ${LIDAR_UDP_PORT} -> ${LIDAR_LINK}"
  timeout $((WAIT_READY_SEC + ECHO_TIMEOUT_SEC + 6)) \
    socat -u "UDP4-RECV:${LIDAR_UDP_PORT},reuseaddr" "PTY,link=${LIDAR_LINK},raw,echo=0,mode=666" \
    >"${SOCAT_LOG}" 2>&1 &
  SOCAT_PID=$!

  for _ in $(seq 1 10); do
    [[ -e "${LIDAR_LINK}" ]] && break
    sleep 0.2
  done
  [[ -e "${LIDAR_LINK}" ]] || fail "未生成 PTY 设备: ${LIDAR_LINK}"

  log "启动 ydlidar_ros2_driver，参数文件: ${PARAMS_FILE}"
  timeout $((WAIT_READY_SEC + ECHO_TIMEOUT_SEC + 6)) \
    ros2 run ydlidar_ros2_driver ydlidar_ros2_driver_node \
    --ros-args --params-file "${PARAMS_FILE}" \
    >"${YDLIDAR_LOG}" 2>&1 &
  YDLIDAR_PID=$!

  local deadline=$((SECONDS + WAIT_READY_SEC))
  while (( SECONDS < deadline )); do
    if ros2 topic list 2>/dev/null | grep -Fxq "/scan"; then
      break
    fi
    sleep 1
  done

  ros2 topic list 2>/dev/null | grep -Fxq "/scan" || {
    tail -n 80 "${YDLIDAR_LOG}" >&2 || true
    fail "超时未发现 /scan"
  }

  log "检测到 /scan，开始抓取一帧"
  timeout "${ECHO_TIMEOUT_SEC}" ros2 topic echo /scan --once >/dev/null || {
    tail -n 80 "${YDLIDAR_LOG}" >&2 || true
    fail "未能在 ${ECHO_TIMEOUT_SEC}s 内读取 /scan"
  }

  log "最近的 ydlidar 日志:"
  tail -n 20 "${YDLIDAR_LOG}" || true
  log "PASS"
}

main "$@"
