#!/usr/bin/env bash
set -euo pipefail

LOG_FILE="/var/log/leap-bootstrap.log"
mkdir -p "$(dirname "${LOG_FILE}")"
exec > >(tee -a "${LOG_FILE}") 2>&1

echo "[Leap Bootstrap] 开始时间: $(date '+%F %T')"

export DEBIAN_FRONTEND=noninteractive

LEAP_USER="${LEAP_USER:-leap}"
LEAP_HOME="/home/${LEAP_USER}"
LEAP_REPO_DIR="${LEAP_REPO_DIR:-${LEAP_HOME}/leap}"
LEAP_WS_ROOT="${LEAP_REPO_DIR}/ros2_ws"
LEAP_BOOTSTRAP_DIR="${LEAP_HOME}/bootstrap"
LEAP_RUNTIME_DIR="${LEAP_REPO_DIR}/runtime/a20"
MICROROS_WS_ROOT="${LEAP_HOME}/microros_ws"
YDLIDAR_SDK_DIR="${LEAP_HOME}/ydlidar-sdk"
ROS_APT_DEB_PATH="${ROS_APT_DEB_PATH:-${LEAP_BOOTSTRAP_DIR}/ros2-apt-source.deb}"

ROS_APT_REPO_API="https://api.github.com/repos/ros-infrastructure/ros-apt-source/releases/latest"

if ! id "${LEAP_USER}" >/dev/null 2>&1; then
  echo "[Leap Bootstrap] 未找到用户 ${LEAP_USER}，终止。"
  exit 1
fi

install -d -m 0755 /var/lib/leap
install -d -m 0755 /etc/apt/apt.conf.d
cat > /etc/apt/apt.conf.d/99force-ipv4 <<'EOF'
Acquire::ForceIPv4 "true";
EOF

apt-get update
apt-get install -y \
  software-properties-common \
  curl \
  ca-certificates \
  gnupg \
  jq \
  lsb-release \
  git \
  build-essential \
  cmake \
  pkg-config \
  python3-pip \
  python3-venv \
  python3-opencv \
  python3-numpy \
  python3-yaml \
  python3-serial \
  socat \
  docker.io \
  v4l-utils \
  net-tools \
  tmux \
  avahi-daemon

add-apt-repository -y universe || true

if ! dpkg -s ros2-apt-source >/dev/null 2>&1; then
  echo "[Leap Bootstrap] 安装 ROS 2 APT 源。"
  if [ -f "${ROS_APT_DEB_PATH}" ]; then
    echo "[Leap Bootstrap] 使用预置 ROS 2 APT 源包: ${ROS_APT_DEB_PATH}"
    dpkg -i "${ROS_APT_DEB_PATH}"
  else
    UBUNTU_CODENAME="$(. /etc/os-release && echo "${VERSION_CODENAME}")"
    ROS_APT_TAG="$(curl -fsSL "${ROS_APT_REPO_API}" | jq -r '.tag_name')"
    TMP_DIR="$(mktemp -d)"
    trap 'rm -rf "${TMP_DIR}"' EXIT
    curl -fL \
      -o "${TMP_DIR}/ros2-apt-source.deb" \
      "https://github.com/ros-infrastructure/ros-apt-source/releases/download/${ROS_APT_TAG}/ros2-apt-source_${ROS_APT_TAG#v}.${UBUNTU_CODENAME}_all.deb"
    dpkg -i "${TMP_DIR}/ros2-apt-source.deb"
  fi
fi

apt-get update
apt-get install -y \
  python3-rosdep2 \
  ros-humble-ros-base \
  ros-humble-navigation2 \
  ros-humble-nav2-bringup \
  ros-humble-robot-localization \
  ros-humble-joint-state-publisher \
  ros-humble-robot-state-publisher \
  ros-humble-tf2-geometry-msgs \
  ros-humble-message-filters \
  ros-humble-xacro

if ! command -v colcon >/dev/null 2>&1; then
  apt-get install -y python3-colcon-common-extensions || true
fi

if ! command -v vcs >/dev/null 2>&1; then
  apt-get install -y python3-vcstool || apt-get install -y python3-vcstools || true
fi

if ! command -v colcon >/dev/null 2>&1 || ! command -v vcs >/dev/null 2>&1 || ! python3 -c "import rosdep2" >/dev/null 2>&1; then
  python3 -m pip install --upgrade pip
  python3 -m pip install colcon-common-extensions vcstool rosdep
fi

systemctl enable --now docker
usermod -aG docker,dialout,video "${LEAP_USER}"

# 首启中断后仓库目录可能残留 root 所有权，先纠正再切到普通用户执行后续步骤。
chown -R "${LEAP_USER}:${LEAP_USER}" "${LEAP_HOME}"

if [ ! -f /etc/ros/rosdep/sources.list.d/20-default.list ]; then
  rosdep init
fi

sudo -u "${LEAP_USER}" rosdep update --rosdistro humble

install -d -m 0755 "${LEAP_RUNTIME_DIR}"
install -d -m 0755 "${MICROROS_WS_ROOT}/src"

cd "${LEAP_WS_ROOT}"

echo "[Leap Bootstrap] 安装工作空间系统依赖。"
rosdep install \
  --from-paths src/leap1 \
  --ignore-src \
  --rosdistro humble \
  -r -y \
  --skip-keys="rviz2 gazebo_ros cartographer_ros"

echo "[Leap Bootstrap] 构建 Leap ROS 2 工作空间。"
sudo -u "${LEAP_USER}" bash -lc "
  set -euo pipefail
  cd '${LEAP_WS_ROOT}'
  ./src/leap1/tools/build_leap1_workspace.sh \
    --packages-select \
      leap1_a20_interfaces \
      leap1_a20 \
      xuegecar_bringup \
      xuegecar_navigation2 \
      xuegecar_description \
      ydlidar_ros2_driver \
      openslam_gmapping \
      slam_gmapping
"

if [ -d "${YDLIDAR_SDK_DIR}" ]; then
  echo "[Leap Bootstrap] 构建并安装 YDLidar SDK。"
  sudo -u "${LEAP_USER}" bash -lc "
    set -euo pipefail
    rm -rf '${YDLIDAR_SDK_DIR}/build'
    cmake -S '${YDLIDAR_SDK_DIR}' -B '${YDLIDAR_SDK_DIR}/build' -DCMAKE_BUILD_TYPE=Release
    cmake --build '${YDLIDAR_SDK_DIR}/build' -j4
  "
  cmake --install "${YDLIDAR_SDK_DIR}/build"
fi

if [ -d "${MICROROS_WS_ROOT}/src/micro_ros_setup" ]; then
  echo "[Leap Bootstrap] 构建本地 micro-ROS agent。"
  sudo -u "${LEAP_USER}" bash -lc "
    set -euo pipefail
    source /opt/ros/humble/setup.bash
    cd '${MICROROS_WS_ROOT}'
    colcon build --packages-select micro_ros_setup
    source '${MICROROS_WS_ROOT}/install/local_setup.bash'
    ros2 run micro_ros_setup create_agent_ws.sh
  " || true
fi

grep -qxF "source /opt/ros/humble/setup.bash" "${LEAP_HOME}/.bashrc" \
  || echo "source /opt/ros/humble/setup.bash" >> "${LEAP_HOME}/.bashrc"
grep -qxF "source ${LEAP_WS_ROOT}/install/setup.bash" "${LEAP_HOME}/.bashrc" \
  || echo "source ${LEAP_WS_ROOT}/install/setup.bash" >> "${LEAP_HOME}/.bashrc"
grep -qxF "source ${MICROROS_WS_ROOT}/install/setup.bash" "${LEAP_HOME}/.bashrc" \
  || echo "source ${MICROROS_WS_ROOT}/install/setup.bash" >> "${LEAP_HOME}/.bashrc"

install -m 0644 \
  "${LEAP_BOOTSTRAP_DIR}/leap1-microros-agent.service" \
  /etc/systemd/system/leap1-microros-agent.service

install -m 0644 \
  "${LEAP_BOOTSTRAP_DIR}/leap1-a20.service" \
  /etc/systemd/system/leap1-a20.service

systemctl daemon-reload
systemctl enable leap1-microros-agent.service
systemctl enable leap1-a20.service

touch /var/lib/leap/bootstrap.done

echo "[Leap Bootstrap] 完成时间: $(date '+%F %T')"
echo "[Leap Bootstrap] 可执行: sudo systemctl start leap1-a20.service"
