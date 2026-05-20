#!/usr/bin/env bash
set -euo pipefail

echo "[Preflight] 开始检查 Leap1 A20 运行环境"
MODE="${LEAP1_PREFLIGHT_MODE:-vehicle}"
AGENT_TRANSPORT="${LEAP1_AGENT_TRANSPORT:-udp}"

fail() {
  echo "[Preflight] FAIL: $1" >&2
  exit 1
}

check_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "缺少命令: $1"
}

if [[ -f /opt/ros/humble/setup.bash ]]; then
  set +u
  # shellcheck disable=SC1091
  source /opt/ros/humble/setup.bash
  set -u
fi

check_cmd ros2
check_cmd python3

if [[ "${MODE}" != "center" ]]; then
  check_cmd socat
fi

if [[ "${MODE}" != "center" && "${AGENT_TRANSPORT}" != "external_serial" && "${AGENT_TRANSPORT}" != "none" && -n "${LEAP1_AGENT_SERIAL_DEV:-}" && ! -e "${LEAP1_AGENT_SERIAL_DEV}" ]]; then
  fail "找不到串口设备: ${LEAP1_AGENT_SERIAL_DEV}"
fi

if [[ "${MODE}" != "center" && "${AGENT_TRANSPORT}" == "external_serial" ]]; then
  echo "[Preflight] INFO: external_serial 模式，跳过本机串口设备检查"
fi

if [[ "${MODE}" != "center" && -n "${LEAP1_VEHICLE_CAMERA_DEVICE:-}" && ! -e "${LEAP1_VEHICLE_CAMERA_DEVICE}" ]]; then
  fail "找不到车载相机设备: ${LEAP1_VEHICLE_CAMERA_DEVICE}"
fi

if [[ -n "${LEAP1_GROUND_CAMERA_DEVICE:-}" && "${LEAP1_GROUND_CAMERA_DEVICE}" != "" && ! -e "${LEAP1_GROUND_CAMERA_DEVICE}" ]]; then
  fail "找不到固定摄像头设备: ${LEAP1_GROUND_CAMERA_DEVICE}"
fi

if ! groups | grep -q '\bdocker\b'; then
  echo "[Preflight] WARN: 当前用户不在 docker 组，若使用 Docker 版 agent 可能失败"
fi

echo "[Preflight] PASS"
