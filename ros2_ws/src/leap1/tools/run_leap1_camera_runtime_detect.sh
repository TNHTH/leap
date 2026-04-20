#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../../.." && pwd)"
RUNTIME_ROOT="${LEAP1_CAMERA_RUNTIME_ROOT:-${PROJECT_ROOT}/runtime/camera_runtime}"
ZIP_PATH="${LEAP1_CAMERA_RUNTIME_ZIP:-/home/gwh/下载/camera_runtime.zip}"
SOURCE_URL="${LEAP1_CAMERA_RUNTIME_SOURCE:-http://127.0.0.1:8092/stream}"
WEIGHTS_PATH="${LEAP1_CAMERA_RUNTIME_WEIGHTS:-${RUNTIME_ROOT}/camera_runtime/weights/best.pt}"
PYTHON_BIN="${LEAP1_CAMERA_RUNTIME_PYTHON:-/usr/bin/python3}"

export PATH="/usr/bin:/bin:/usr/sbin:/sbin:${PATH}"
unset PYTHONPATH
unset CONDA_PREFIX
unset CONDA_DEFAULT_ENV
unset CONDA_EXE
unset CONDA_PYTHON_EXE
unset CONDA_SHLVL
unset _CE_CONDA
unset _CE_M

if [[ ! -f "${RUNTIME_ROOT}/camera_runtime/deploy_camera_detect.py" ]]; then
  [[ -f "${ZIP_PATH}" ]] || {
    echo "[Leap1 Camera Runtime] FAIL: 找不到 ${ZIP_PATH}" >&2
    exit 1
  }
  mkdir -p "${RUNTIME_ROOT}"
  unzip -n "${ZIP_PATH}" -d "${RUNTIME_ROOT}" >/dev/null
fi

"${PYTHON_BIN}" - <<'PY'
try:
    import ultralytics  # noqa: F401
except Exception as exc:
    raise SystemExit(
        "[Leap1 Camera Runtime] FAIL: 缺少 ultralytics。请先安装: python3 -m pip install --user ultralytics\n"
        f"原始错误: {exc}"
    )
PY

[[ -f "${WEIGHTS_PATH}" ]] || {
  echo "[Leap1 Camera Runtime] FAIL: 找不到权重 ${WEIGHTS_PATH}" >&2
  exit 1
}

echo "[Leap1 Camera Runtime] source=${SOURCE_URL}"
echo "[Leap1 Camera Runtime] weights=${WEIGHTS_PATH}"

exec "${PYTHON_BIN}" "${RUNTIME_ROOT}/camera_runtime/deploy_camera_detect.py" \
  --weights "${WEIGHTS_PATH}" \
  --source "${SOURCE_URL}" \
  "$@"
