#!/usr/bin/env bash
set -euo pipefail

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

MICROROS_WS_ROOT="${MICROROS_WS_ROOT:-/home/leap/microros_ws}"
MICROROS_AGENT_DEV="${MICROROS_AGENT_DEV:-/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0}"
MICROROS_AGENT_BAUD="${MICROROS_AGENT_BAUD:-921600}"
MICROROS_AGENT_VERBOSITY="${MICROROS_AGENT_VERBOSITY:-6}"

set +u
source /opt/ros/humble/setup.bash
source "${MICROROS_WS_ROOT}/install/setup.bash"
set -u

echo "[micro-ROS Agent] 设备: ${MICROROS_AGENT_DEV}"
echo "[micro-ROS Agent] 波特率: ${MICROROS_AGENT_BAUD}"
echo "[micro-ROS Agent] 详细级别: ${MICROROS_AGENT_VERBOSITY}"

exec ros2 run micro_ros_agent micro_ros_agent \
  serial \
  --dev "${MICROROS_AGENT_DEV}" \
  -b "${MICROROS_AGENT_BAUD}" \
  -v"${MICROROS_AGENT_VERBOSITY}"
