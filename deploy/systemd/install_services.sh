#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "用法: $0 <linux-user>" >&2
  exit 1
fi

USER_NAME="$1"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

install_one() {
  local src="$1"
  local dst="/etc/systemd/system/$(basename "$src")"
  sed "s/__LEAP_USER__/${USER_NAME}/g" "$src" | sudo tee "$dst" >/dev/null
}

install_one "${SCRIPT_DIR}/leap1-microros-agent.service"
install_one "${SCRIPT_DIR}/leap1-vehicle-runtime.service"
install_one "${SCRIPT_DIR}/leap1-center-console.service"

sudo systemctl daemon-reload
echo "已安装 systemd 模板，请按需执行:"
echo "  sudo systemctl enable --now leap1-microros-agent.service"
echo "  sudo systemctl enable --now leap1-vehicle-runtime.service"
echo "  sudo systemctl enable --now leap1-center-console.service"
