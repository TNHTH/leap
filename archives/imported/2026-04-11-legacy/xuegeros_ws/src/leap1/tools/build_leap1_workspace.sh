#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
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

set +u
source /opt/ros/humble/setup.bash
set -u

cd "${WS_ROOT}"
COLCON_PYTHON_EXECUTABLE=/usr/bin/python3.10 colcon build \
  --base-paths src/leap1 \
  --symlink-install \
  --cmake-clean-cache \
  --cmake-args \
    -DPython3_EXECUTABLE=/usr/bin/python3.10 \
    -DPYTHON_EXECUTABLE=/usr/bin/python3.10 \
  "$@"
