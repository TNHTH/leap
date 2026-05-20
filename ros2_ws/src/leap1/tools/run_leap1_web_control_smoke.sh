#!/usr/bin/env bash
set -euo pipefail

HOST="${LEAP1_WEB_SMOKE_HOST:-127.0.0.1}"
PORT="${LEAP1_WEB_SMOKE_PORT:-8090}"

log() {
  echo "[Leap1 Web Smoke] $*"
}

fail() {
  echo "[Leap1 Web Smoke] FAIL: $*" >&2
  exit 1
}

check_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "缺少命令: $1"
}

get_json() {
  local path="$1"
  curl -sS "http://${HOST}:${PORT}${path}"
}

post_json() {
  local path="$1"
  local payload="$2"
  curl -sS -X POST "http://${HOST}:${PORT}${path}" \
    -H 'Content-Type: application/json' \
    -d "${payload}"
}

validate_json() {
  printf '%s' "$1" | /usr/bin/python3 -m json.tool >/dev/null
}

main() {
  check_cmd curl
  check_cmd /usr/bin/python3

  validate_json "$(get_json /api/status)" || fail "/api/status 不是合法 JSON"
  log "/api/status OK"

  validate_json "$(get_json /api/maps)" || fail "/api/maps 不是合法 JSON"
  log "/api/maps OK"

  validate_json "$(post_json /api/cmd_vel '{"vx":0.0,"vz":0.0}')" || fail "/api/cmd_vel 返回异常"
  log "/api/cmd_vel OK"

  validate_json "$(post_json /api/stop '{}')" || fail "/api/stop 返回异常"
  log "/api/stop OK"

  validate_json "$(post_json /api/pump '{"enabled":false}')" || fail "/api/pump(off) 返回异常"
  log "/api/pump(off) OK"

  log "PASS"
}

main "$@"
