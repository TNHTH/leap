#!/usr/bin/env bash
set -euo pipefail

HOST="${LEAP1_A20_SMOKE_HOST:-127.0.0.1}"
PORT="${LEAP1_A20_SMOKE_PORT:-8090}"
TOPIC_TIMEOUT_SEC="${LEAP1_A20_TOPIC_TIMEOUT_SEC:-10}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PACKAGE_ROOT="${WORKSPACE_ROOT}/leap1_a20"

required_files=(
  "${PACKAGE_ROOT}/package.xml"
  "${PACKAGE_ROOT}/launch/a20_vehicle.launch.py"
  "${PACKAGE_ROOT}/config/default_params.yaml"
  "${PACKAGE_ROOT}/leap1_a20/perception_bridge_node.py"
  "${PACKAGE_ROOT}/leap1_a20/broadcast_center_server.py"
  "${PACKAGE_ROOT}/leap1_a20/web/index.html"
  "${PACKAGE_ROOT}/leap1_a20/web/app.js"
  "${PACKAGE_ROOT}/leap1_a20/web/styles.css"
)

required_topics=(
  "/a20/mission/state"
  "/a20/fire_event"
  "/a20/perception/detection"
  "/a20/perception/status"
  "/a20/camera/status"
  "/a20/map/request"
  "/a20/map/response"
)

required_http_gets=(
  "/"
  "/index.html"
  "/app.js"
  "/styles.css"
  "/api/status"
  "/api/maps"
)

log() {
  echo "[A20 Smoke] $*"
}

fail() {
  echo "[A20 Smoke] FAIL: $*" >&2
  exit 1
}

check_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "缺少命令: $1"
}

check_file() {
  local path="$1"
  [[ -e "${path}" ]] || fail "缺少文件: ${path}"
  log "文件存在: ${path}"
}

check_http_get() {
  local path="$1"
  local url="http://${HOST}:${PORT}${path}"
  local status
  status="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 3 "${url}")" || fail "HTTP 请求失败: ${url}"
  [[ "${status}" == "200" ]] || fail "HTTP 状态异常 ${status}: ${url}"
  log "HTTP OK: ${url}"
}

check_topics_ready() {
  local deadline
  deadline=$((SECONDS + TOPIC_TIMEOUT_SEC))
  while (( SECONDS < deadline )); do
    local topic_list
    if topic_list="$(ros2 topic list 2>/dev/null)"; then
      local missing=0
      for topic in "${required_topics[@]}"; do
        if ! grep -Fxq "${topic}" <<<"${topic_list}"; then
          missing=1
          break
        fi
      done
      if (( missing == 0 )); then
        for topic in "${required_topics[@]}"; do
          log "Topic 在线: ${topic}"
        done
        return 0
      fi
    fi
    sleep 1
  done

  local topic_list=""
  topic_list="$(ros2 topic list 2>/dev/null || true)"
  for topic in "${required_topics[@]}"; do
    grep -Fxq "${topic}" <<<"${topic_list}" || fail "缺少 topic: ${topic}"
  done
}

main() {
  check_cmd ros2
  check_cmd curl

  log "开始文件存在性检查"
  for path in "${required_files[@]}"; do
    check_file "${path}"
  done

  log "开始 ROS topic 检查，超时 ${TOPIC_TIMEOUT_SEC}s"
  check_topics_ready

  log "开始 HTTP API 检查: http://${HOST}:${PORT}"
  for path in "${required_http_gets[@]}"; do
    check_http_get "${path}"
  done

  log "PASS"
}

main "$@"
