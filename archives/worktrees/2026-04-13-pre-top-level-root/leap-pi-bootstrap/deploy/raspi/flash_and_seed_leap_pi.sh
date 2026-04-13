#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME="ubuntu-22.04.5-preinstalled-server-arm64+raspi.img.xz"
IMAGE_BASE_URL="https://cdimage.ubuntu.com/releases/22.04/release"
IMAGE_URL="${LEAP_IMAGE_URL:-${IMAGE_BASE_URL}/${IMAGE_NAME}}"
IMAGE_SHA256="${LEAP_IMAGE_SHA256:-fd7687c5c9422a6c7ba4717c227bf6473fe4e0c954d5a9f664201dcecc63e822}"
IMAGE_CACHE_DIR="${LEAP_IMAGE_CACHE_DIR:-/var/tmp/leap-pi-images}"

LEAP_HOSTNAME="${LEAP_HOSTNAME:-leap-pi}"
LEAP_PI_USER="${LEAP_PI_USER:-leap}"
LEAP_WIFI_SSID="${LEAP_WIFI_SSID:-}"
LEAP_WIFI_PASSWORD="${LEAP_WIFI_PASSWORD:-}"
LEAP_AGENT_SERIAL_DEV="${LEAP_AGENT_SERIAL_DEV:-/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0}"
LEAP_VEHICLE_CAMERA_DEVICE="${LEAP_VEHICLE_CAMERA_DEVICE:-/dev/video0}"
LEAP_A20_WEB_PORT="${LEAP_A20_WEB_PORT:-8090}"
LEAP_SSH_PUBKEY="${LEAP_SSH_PUBKEY:-}"
ORIGINAL_USER="${SUDO_USER:-${USER:-root}}"
ORIGINAL_HOME="$(getent passwd "${ORIGINAL_USER}" | cut -d: -f6)"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

if [ "${EUID}" -ne 0 ]; then
  echo "请用 sudo 运行本脚本。"
  exit 1
fi

if [ $# -lt 1 ]; then
  echo "用法: sudo $0 /dev/sdX"
  exit 1
fi

TARGET_DEV="$1"

if [ ! -b "${TARGET_DEV}" ]; then
  echo "目标设备不存在: ${TARGET_DEV}"
  exit 1
fi

if [ -n "${LEAP_WIFI_SSID}" ] && [ -z "${LEAP_WIFI_PASSWORD}" ]; then
  echo "已提供 LEAP_WIFI_SSID，但缺少 LEAP_WIFI_PASSWORD。"
  exit 1
fi

if [ -z "${LEAP_SSH_PUBKEY}" ] && [ -n "${ORIGINAL_HOME}" ] && [ -f "${ORIGINAL_HOME}/.ssh/id_ed25519_dashgo.pub" ]; then
  LEAP_SSH_PUBKEY="$(cat "${ORIGINAL_HOME}/.ssh/id_ed25519_dashgo.pub")"
fi

if [ -z "${LEAP_SSH_PUBKEY}" ]; then
  echo "未找到 SSH 公钥，请通过 LEAP_SSH_PUBKEY 提供。"
  exit 1
fi

part_path() {
  local dev="$1"
  local idx="$2"
  if [[ "${dev}" =~ [0-9]$ ]]; then
    printf '%sp%s\n' "${dev}" "${idx}"
  else
    printf '%s%s\n' "${dev}" "${idx}"
  fi
}

echo "将被覆盖的设备候选:"
lsblk -o NAME,SIZE,FSTYPE,LABEL,MOUNTPOINT,MODEL,TRAN "${TARGET_DEV}"
echo
echo "目标设备: ${TARGET_DEV}"
echo "镜像地址: ${IMAGE_URL}"
echo "目标主机名: ${LEAP_HOSTNAME}"
if [ -n "${LEAP_WIFI_SSID}" ]; then
  echo "Wi-Fi SSID: ${LEAP_WIFI_SSID}"
else
  echo "Wi-Fi: 未配置，首启将只启用以太网 DHCP"
fi
echo

CONFIRM_TEXT="ERASE:${TARGET_DEV}"
read -r -p "输入 ${CONFIRM_TEXT} 继续刷卡: " USER_CONFIRM
if [ "${USER_CONFIRM}" != "${CONFIRM_TEXT}" ]; then
  echo "确认串不匹配，已取消。"
  exit 1
fi

mkdir -p "${IMAGE_CACHE_DIR}"
IMAGE_PATH="${IMAGE_CACHE_DIR}/${IMAGE_NAME}"

ensure_image() {
  local image_path="$1"
  local image_url="$2"
  local expected_sha="$3"
  local actual_sha=""
  local remote_size=""
  local local_size="0"

  remote_size="$(curl -fsSLI -L "${image_url}" | awk 'tolower($1) == "content-length:" {print $2}' | tr -d '\r' | tail -1)"

  if [ -f "${image_path}" ]; then
    local_size="$(stat -c '%s' "${image_path}")"
    if [ -n "${remote_size}" ] && [ "${local_size}" -lt "${remote_size}" ]; then
      echo "[1/8] 发现未完成缓存，执行断点续传。"
      curl -fL -C - --progress-bar -o "${image_path}" "${image_url}"
    else
      actual_sha="$(sha256sum "${image_path}" | awk '{print $1}')"
      if [ "${actual_sha}" = "${expected_sha}" ]; then
        echo "[1/8] 复用已校验镜像: ${image_path}"
        return 0
      fi
      echo "[1/8] 发现缓存镜像校验不匹配，删除后重新下载。"
      rm -f "${image_path}"
    fi
  fi

  if [ ! -f "${image_path}" ]; then
    echo "[1/8] 下载 Ubuntu 镜像..."
    curl -fL --progress-bar -o "${image_path}" "${image_url}"
  fi

  actual_sha="$(sha256sum "${image_path}" | awk '{print $1}')"
  if [ "${actual_sha}" != "${expected_sha}" ]; then
    echo "[1/8] 续传后的镜像校验仍不匹配，删除并全量重下。"
    rm -f "${image_path}"
    curl -fL --progress-bar -o "${image_path}" "${image_url}"
  fi
}

ensure_image "${IMAGE_PATH}" "${IMAGE_URL}" "${IMAGE_SHA256}"

echo "[2/8] 校验镜像 SHA256..."
echo "${IMAGE_SHA256}  ${IMAGE_PATH}" | sha256sum -c -

echo "[3/8] 卸载目标设备已挂载分区..."
while read -r mountpoint; do
  [ -n "${mountpoint}" ] && umount -lf "${mountpoint}" || true
done < <(lsblk -nrpo MOUNTPOINT "${TARGET_DEV}" | sort -u)

echo "[4/8] 刷写镜像到 ${TARGET_DEV}..."
xzcat "${IMAGE_PATH}" | dd of="${TARGET_DEV}" bs=4M conv=fsync status=progress
sync
partprobe "${TARGET_DEV}"
udevadm settle
sleep 5

BOOT_PART="$(part_path "${TARGET_DEV}" 1)"
ROOT_PART="$(part_path "${TARGET_DEV}" 2)"

if [ ! -b "${BOOT_PART}" ] || [ ! -b "${ROOT_PART}" ]; then
  echo "刷卡后未识别到预期分区: ${BOOT_PART}, ${ROOT_PART}"
  exit 1
fi

BOOT_MNT="$(mktemp -d /tmp/leap-boot.XXXXXX)"
ROOT_MNT="$(mktemp -d /tmp/leap-root.XXXXXX)"

cleanup() {
  set +e
  sync
  mountpoint -q "${BOOT_MNT}" && umount -lf "${BOOT_MNT}"
  mountpoint -q "${ROOT_MNT}" && umount -lf "${ROOT_MNT}"
  rm -rf "${BOOT_MNT}" "${ROOT_MNT}"
}
trap cleanup EXIT

echo "[5/8] 挂载新系统分区..."
mount "${BOOT_PART}" "${BOOT_MNT}"
mount "${ROOT_PART}" "${ROOT_MNT}"

echo "[6/8] 注入 cloud-init 配置..."
cat > "${BOOT_MNT}/meta-data" <<EOF
instance-id: ${LEAP_HOSTNAME}
local-hostname: ${LEAP_HOSTNAME}
EOF

if [ -n "${LEAP_WIFI_SSID}" ] && [ -n "${LEAP_WIFI_PASSWORD}" ]; then
  cat > "${BOOT_MNT}/network-config" <<EOF
version: 2
ethernets:
  eth0:
    dhcp4: true
    optional: true
wifis:
  wlan0:
    dhcp4: true
    optional: true
    access-points:
      "${LEAP_WIFI_SSID}":
        password: "${LEAP_WIFI_PASSWORD}"
EOF
else
  cat > "${BOOT_MNT}/network-config" <<EOF
version: 2
ethernets:
  eth0:
    dhcp4: true
    optional: true
EOF
fi

cat > "${BOOT_MNT}/user-data" <<EOF
#cloud-config
hostname: ${LEAP_HOSTNAME}
manage_etc_hosts: true
timezone: Asia/Shanghai

users:
  - default
  - name: ${LEAP_PI_USER}
    gecos: Leap Operator
    groups: [adm, sudo, dialout, video, docker]
    shell: /bin/bash
    sudo: ALL=(ALL) NOPASSWD:ALL
    lock_passwd: true
    ssh_authorized_keys:
      - ${LEAP_SSH_PUBKEY}

write_files:
  - path: /etc/systemd/system/leap-firstboot.service
    owner: root:root
    permissions: '0644'
    content: |
      [Unit]
      Description=Leap first boot bootstrap
      After=network-online.target cloud-final.service
      Wants=network-online.target
      ConditionPathExists=!/var/lib/leap/bootstrap.done

      [Service]
      Type=oneshot
      ExecStart=/bin/bash /home/${LEAP_PI_USER}/bootstrap/install_leap1_pi.sh
      RemainAfterExit=yes

      [Install]
      WantedBy=multi-user.target

runcmd:
  - [ bash, -lc, 'mkdir -p /var/lib/leap /home/${LEAP_PI_USER}/bootstrap /home/${LEAP_PI_USER}/leap/runtime/a20' ]
  - [ systemctl, daemon-reload ]
  - [ systemctl, enable, leap-firstboot.service ]
  - [ systemctl, start, --no-block, leap-firstboot.service ]
EOF

echo "[7/8] 拷贝 Leap 首启脚本与仓库快照..."
install -d -m 0755 \
  "${ROOT_MNT}/home/${LEAP_PI_USER}/bootstrap" \
  "${ROOT_MNT}/home/${LEAP_PI_USER}/leap"

install -m 0755 \
  "${SCRIPT_DIR}/install_leap1_pi.sh" \
  "${ROOT_MNT}/home/${LEAP_PI_USER}/bootstrap/install_leap1_pi.sh"

sed \
  -e "s|__LEAP_USER__|${LEAP_PI_USER}|g" \
  -e "s|/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0|${LEAP_AGENT_SERIAL_DEV}|g" \
  -e "s|/dev/video0|${LEAP_VEHICLE_CAMERA_DEVICE}|g" \
  -e "s|8090|${LEAP_A20_WEB_PORT}|g" \
  "${SCRIPT_DIR}/leap1-a20.service" \
  > "${ROOT_MNT}/home/${LEAP_PI_USER}/bootstrap/leap1-a20.service"

tar \
  --exclude='.git' \
  --exclude='.tmp' \
  --exclude='runtime' \
  --exclude='ros2_ws/build' \
  --exclude='ros2_ws/install' \
  --exclude='ros2_ws/log' \
  -C "${REPO_ROOT}" \
  -cpf - \
  README.md \
  AGENTS.md \
  docs \
  deploy/raspi \
  ros2_ws \
  | tar -C "${ROOT_MNT}/home/${LEAP_PI_USER}/leap" -xpf -

echo "[8/8] 完成刷卡与注入。"
sync
echo "树莓派卡已准备完成。"
echo "默认 SSH: ${LEAP_PI_USER}@${LEAP_HOSTNAME}.local"
if [ -n "${LEAP_WIFI_SSID}" ]; then
  echo "Wi-Fi 已写入: ${LEAP_WIFI_SSID}"
else
  echo "未写入 Wi-Fi，请用网线首启，或手动编辑 boot 分区的 network-config。"
fi
