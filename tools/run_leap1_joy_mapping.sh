#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
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

WITH_RVIZ="${LEAP1_WITH_RVIZ:-true}"
START_AGENT_IF_NEEDED="${LEAP1_START_AGENT_IF_NEEDED:-true}"
START_LIDAR_BRIDGE_IF_NEEDED="${LEAP1_START_LIDAR_BRIDGE_IF_NEEDED:-true}"
BRINGUP_WAIT="${LEAP1_BRINGUP_WAIT:-3}"
LIDAR_WAIT="${LEAP1_LIDAR_WAIT:-5}"
JOY_DEVICE_ID="${LEAP1_JOY_DEVICE_ID:-0}"
JOY_DEADZONE="${LEAP1_JOY_DEADZONE:-0.15}"
JOY_AUTOREPEAT_RATE="${LEAP1_JOY_AUTOREPEAT_RATE:-20.0}"
REQUIRE_ENABLE_BUTTON="${LEAP1_REQUIRE_ENABLE_BUTTON:-false}"
ENABLE_BUTTON="${LEAP1_ENABLE_BUTTON:-4}"
AXIS_LINEAR_X="${LEAP1_AXIS_LINEAR_X:-1}"
SCALE_LINEAR_X="${LEAP1_SCALE_LINEAR_X:-0.25}"
AXIS_ANGULAR_YAW="${LEAP1_AXIS_ANGULAR_YAW:-0}"
SCALE_ANGULAR_YAW="${LEAP1_SCALE_ANGULAR_YAW:-0.8}"

DOCKER_IMAGE='registry.cn-hangzhou.aliyuncs.com/fishros/micro-ros-agent:humble'
MICRO_ROS_PORT='8888'
LIDAR_UDP_PORT='8889'
LIDAR_LINK='/tmp/lidar'
LEGACY_LIDAR_LINK='/home/gwh/leap/tmp/lidar'
LIDAR_PARAMS="${REPO_ROOT}/xuegecar_bringup/config/ydlidar_udp_bridge.yaml"
RVIZ_CONFIG="${REPO_ROOT}/xuegecar_navigation2/rviz/fishbot_navigation2.rviz"

port_in_use() {
  local port="$1"
  ss -lun "sport = :${port}" | tail -n +2 | grep -q .
}

topic_has_publisher() {
  local topic_name="$1"
  local info
  if ! info="$(ros2 topic info "${topic_name}" 2>/dev/null)"; then
    return 1
  fi

  local count
  count="$(printf '%s\n' "${info}" | awk -F': ' '/Publisher count/ {print $2}')"
  [[ -n "${count}" && "${count}" != "0" ]]
}

ensure_lidar_link() {
  if [[ -e "${LIDAR_LINK}" ]]; then
    return 0
  fi

  if [[ -e "${LEGACY_LIDAR_LINK}" ]]; then
    ln -sfn "${LEGACY_LIDAR_LINK}" "${LIDAR_LINK}"
    echo "[Leap1 Joy Mapping] 已将 ${LIDAR_LINK} 指向现有雷达口 ${LEGACY_LIDAR_LINK}。"
    return 0
  fi

  return 1
}

cleanup() {
  local exit_code=$?
  trap - EXIT INT TERM

  for pid_var in TELEOP_PID JOY_PID RVIZ_PID SLAM_PID LIDAR_PID BRINGUP_PID LIDAR_BRIDGE_PID AGENT_PID; do
    if [[ -n "${!pid_var:-}" ]] && kill -0 "${!pid_var}" 2>/dev/null; then
      kill "${!pid_var}" 2>/dev/null || true
      wait "${!pid_var}" 2>/dev/null || true
    fi
  done

  exit "${exit_code}"
}

trap cleanup EXIT INT TERM

set +u
source /opt/ros/humble/setup.bash
source "${WS_ROOT}/install/setup.bash"
set -u

echo "[Leap1 Joy Mapping] 工作区: ${WS_ROOT}"
echo "[Leap1 Joy Mapping] RViz: ${WITH_RVIZ}"
echo "[Leap1 Joy Mapping] 手柄设备: /dev/input/js${JOY_DEVICE_ID}"

if port_in_use "${MICRO_ROS_PORT}"; then
  echo "[Leap1 Joy Mapping] 检测到 ${MICRO_ROS_PORT} 端口已有 micro-ROS agent，直接复用。"
elif [[ "${START_AGENT_IF_NEEDED}" == "true" ]]; then
  echo "[Leap1 Joy Mapping] 未检测到 micro-ROS agent，正在启动..."
  sg docker -c "docker run --rm -v /dev:/dev -v /dev/shm:/dev/shm --privileged --net=host ${DOCKER_IMAGE} udp4 --port ${MICRO_ROS_PORT} -v6" &
  AGENT_PID=$!
  sleep 2
else
  echo "[Leap1 Joy Mapping] 未检测到 micro-ROS agent，且配置为不自动启动。"
  exit 1
fi

REUSE_EXISTING_SCAN=false
if topic_has_publisher /scan; then
  REUSE_EXISTING_SCAN=true
  echo "[Leap1 Joy Mapping] 检测到系统里已有 /scan 发布者，直接复用现有激光链。"
else
  if port_in_use "${LIDAR_UDP_PORT}"; then
    echo "[Leap1 Joy Mapping] 检测到 ${LIDAR_UDP_PORT} 端口已有雷达 UDP 桥，直接复用。"
    ensure_lidar_link || true
  elif [[ "${START_LIDAR_BRIDGE_IF_NEEDED}" == "true" ]]; then
    echo "[Leap1 Joy Mapping] 未检测到雷达 UDP 桥，正在启动..."
    socat -d -d PTY,link="${LIDAR_LINK}",raw,echo=0,mode=666 UDP4-LISTEN:${LIDAR_UDP_PORT},reuseaddr,fork &
    LIDAR_BRIDGE_PID=$!
    sleep 1
  else
    echo "[Leap1 Joy Mapping] 未检测到雷达 UDP 桥，且配置为不自动启动。"
    exit 1
  fi

  if ! ensure_lidar_link; then
    echo "[Leap1 Joy Mapping] 未找到可用的雷达串口入口，期望路径为 ${LIDAR_LINK}。"
    exit 1
  fi
fi

echo "[Leap1 Joy Mapping] 正在启动底盘 TF 与机器人描述..."
ros2 launch xuegecar_bringup xuegecar_bringup.launch.py use_joint_state_publisher:=false use_sim_time:=false &
BRINGUP_PID=$!
sleep "${BRINGUP_WAIT}"

if [[ "${REUSE_EXISTING_SCAN}" == "false" ]]; then
  echo "[Leap1 Joy Mapping] 正在启动雷达节点..."
  ros2 launch ydlidar_ros2_driver ydlidar_launch.py params_file:="${LIDAR_PARAMS}" &
  LIDAR_PID=$!
  sleep "${LIDAR_WAIT}"
fi

echo "[Leap1 Joy Mapping] 正在启动 gmapping..."
ros2 launch slam_gmapping slam_gmapping.launch.py use_sim_time:=false &
SLAM_PID=$!
sleep 2

if [[ "${WITH_RVIZ}" == "true" ]]; then
  echo "[Leap1 Joy Mapping] 正在启动 RViz..."
  ros2 run rviz2 rviz2 -d "${RVIZ_CONFIG}" &
  RVIZ_PID=$!
  sleep 2
fi

echo "[Leap1 Joy Mapping] 正在启动手柄节点..."
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

echo "[Leap1 Joy Mapping] 已启动手柄控制、激光雷达、gmapping 和 RViz。按 Ctrl+C 退出。"
echo "[Leap1 Joy Mapping] 保存地图命令:"
echo "  source /opt/ros/humble/setup.bash && source ${WS_ROOT}/install/setup.bash && ros2 run nav2_map_server map_saver_cli -f ~/leap1_map"

pids=("${BRINGUP_PID}" "${SLAM_PID}" "${JOY_PID}" "${TELEOP_PID}")
if [[ -n "${LIDAR_PID:-}" ]]; then
  pids+=("${LIDAR_PID}")
fi
if [[ -n "${RVIZ_PID:-}" ]]; then
  pids+=("${RVIZ_PID}")
fi
if [[ -n "${LIDAR_BRIDGE_PID:-}" ]]; then
  pids+=("${LIDAR_BRIDGE_PID}")
fi
if [[ -n "${AGENT_PID:-}" ]]; then
  pids+=("${AGENT_PID}")
fi

wait -n "${pids[@]}"
