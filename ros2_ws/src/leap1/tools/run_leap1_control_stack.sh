#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WS_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
PROJECT_ROOT="$(cd "${WS_ROOT}/.." && pwd)"
LOCAL_LOG_DIR="${PROJECT_ROOT}/runtime/a20/logs"

REMOTE_HOST="${LEAP1_REMOTE_HOST:-leap@10.127.143.229}"
REMOTE_MODE="${LEAP1_REMOTE_MODE:-vehicle}"
WEB_PORT="${LEAP1_A20_WEB_PORT:-8090}"
OPEN_BROWSER="${LEAP1_OPEN_BROWSER:-true}"
WAIT_WEB_SEC="${LEAP1_WAIT_WEB_SEC:-25}"
SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout=8)

usage() {
  cat <<'EOF'
用法:
  run_leap1_control_stack.sh [--remote-host HOST] [--remote-mode vehicle|patrol] [--no-open]

默认行为:
  1. 检查并启动树莓派端 micro-ROS agent
  2. 启动车端运行态:
     - vehicle: 基础车端运行态
     - patrol: 树莓派端巡航/避障运行态
  3. 本地后台启动广播中心网页
  4. 等待 http://127.0.0.1:8090/ 就绪并可选自动打开浏览器

环境变量:
  LEAP1_REMOTE_HOST
  LEAP1_REMOTE_MODE
  LEAP1_A20_WEB_PORT
  LEAP1_OPEN_BROWSER=true|false
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --remote-host)
      REMOTE_HOST="${2:?missing host}"
      shift 2
      ;;
    --remote-mode)
      REMOTE_MODE="${2:?missing mode}"
      shift 2
      ;;
    --no-open)
      OPEN_BROWSER=false
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[Leap1 Control Stack] FAIL: 未知参数 $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ "${REMOTE_MODE}" != "vehicle" && "${REMOTE_MODE}" != "patrol" ]]; then
  echo "[Leap1 Control Stack] FAIL: --remote-mode 只支持 vehicle 或 patrol" >&2
  exit 1
fi

log() {
  echo "[Leap1 Control Stack] $*"
}

fail() {
  echo "[Leap1 Control Stack] FAIL: $*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "缺少命令: $1"
}

remote_exec() {
  ssh "${SSH_OPTS[@]}" "${REMOTE_HOST}" "$@"
}

remote_bash() {
  remote_exec "bash -lc '$1'"
}

ensure_local_log_dir() {
  mkdir -p "${LOCAL_LOG_DIR}"
}

is_local_web_ready() {
  curl -fsS "http://127.0.0.1:${WEB_PORT}/api/status" >/dev/null 2>&1
}

wait_local_web() {
  local elapsed=0
  while (( elapsed < WAIT_WEB_SEC )); do
    if is_local_web_ready; then
      return 0
    fi
    sleep 1
    ((elapsed+=1))
  done
  return 1
}

start_local_web() {
  ensure_local_log_dir

  if is_local_web_ready; then
    log "检测到本地网页已在运行，直接复用。"
    return 0
  fi

  local log_file="${LOCAL_LOG_DIR}/control-stack-web-$(date +%Y%m%d-%H%M%S).log"
  log "本地启动广播中心网页，日志: ${log_file}"
  (
    cd "${SCRIPT_DIR}"
    nohup ./run_leap1_web_control.sh >"${log_file}" 2>&1 &
  )

  wait_local_web || fail "本地网页在 ${WAIT_WEB_SEC}s 内未就绪，请检查 ${log_file}"
}

open_browser() {
  local url="http://127.0.0.1:${WEB_PORT}/"
  if [[ "${OPEN_BROWSER}" != "true" ]]; then
    log "网页已就绪: ${url}"
    return 0
  fi
  if command -v xdg-open >/dev/null 2>&1; then
    nohup xdg-open "${url}" >/dev/null 2>&1 &
    log "已尝试打开浏览器: ${url}"
  else
    log "未找到 xdg-open，请手动打开: ${url}"
  fi
}

remote_services_available() {
  remote_bash "sudo -n systemctl cat leap1-microros-agent.service >/dev/null 2>&1 && sudo -n systemctl cat leap1-vehicle-runtime.service >/dev/null 2>&1"
}

start_remote_with_systemd() {
  log "树莓派使用 systemd 启动。"
  remote_bash "sudo -n systemctl start leap1-microros-agent.service"

  if [[ "${REMOTE_MODE}" == "vehicle" ]]; then
    remote_bash "pkill -f '^bash /home/leap/leap/ros2_ws/src/leap1/tools/run_leap1_patrol_runtime.sh$' >/dev/null 2>&1 || true; sudo -n systemctl start leap1-vehicle-runtime.service"
  else
    remote_bash "sudo -n systemctl stop leap1-vehicle-runtime.service >/dev/null 2>&1 || true; pgrep -f '^bash /home/leap/leap/ros2_ws/src/leap1/tools/run_leap1_patrol_runtime.sh$' >/dev/null || nohup /home/leap/leap/ros2_ws/src/leap1/tools/run_leap1_patrol_runtime.sh >/tmp/leap1_patrol_runtime.log 2>&1 &"
  fi
}

start_remote_with_user_scripts() {
  log "树莓派未使用 systemd 或无免密 sudo，回退到用户脚本启动。"
  remote_bash "pgrep -f 'micro_ros_agent serial --dev' >/dev/null || nohup /home/leap/leap/ros2_ws/src/leap1/tools/run_leap1_microros_agent.sh >/tmp/leap1_microros_agent.log 2>&1 &"

  if [[ "${REMOTE_MODE}" == "vehicle" ]]; then
    remote_bash "pkill -f '^bash /home/leap/leap/ros2_ws/src/leap1/tools/run_leap1_patrol_runtime.sh$' >/dev/null 2>&1 || true; pgrep -f '^bash /home/leap/leap/ros2_ws/src/leap1/tools/run_leap1_vehicle_runtime.sh$' >/dev/null || nohup /home/leap/leap/ros2_ws/src/leap1/tools/run_leap1_vehicle_runtime.sh >/tmp/leap1_vehicle_runtime.log 2>&1 &"
  else
    remote_bash "pkill -f '^bash /home/leap/leap/ros2_ws/src/leap1/tools/run_leap1_vehicle_runtime.sh$' >/dev/null 2>&1 || true; pgrep -f '^bash /home/leap/leap/ros2_ws/src/leap1/tools/run_leap1_patrol_runtime.sh$' >/dev/null || nohup /home/leap/leap/ros2_ws/src/leap1/tools/run_leap1_patrol_runtime.sh >/tmp/leap1_patrol_runtime.log 2>&1 &"
  fi
}

remote_summary() {
  local output
  output="$(remote_bash "echo host=\$(hostname); pgrep -af '^bash /home/leap/leap/ros2_ws/src/leap1/tools/run_leap1_patrol_runtime.sh$' || true; pgrep -af '^bash /home/leap/leap/ros2_ws/src/leap1/tools/run_leap1_vehicle_runtime.sh$' || true; pgrep -af 'micro_ros_agent serial --dev' || true")" || true
  [[ -n "${output}" ]] && printf '%s\n' "${output}"
}

main() {
  require_cmd ssh
  require_cmd curl

  log "检查树莓派连通性: ${REMOTE_HOST}"
  remote_exec "true" >/dev/null 2>&1 || fail "无法 SSH 到 ${REMOTE_HOST}"

  if remote_services_available >/dev/null 2>&1; then
    start_remote_with_systemd
  else
    start_remote_with_user_scripts
  fi

  start_local_web
  open_browser

  log "统一启动完成。"
  remote_summary
}

main "$@"
