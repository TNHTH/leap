from __future__ import annotations

"""
USB RGB 摄像头实时检测（Ultralytics YOLO）。

默认使用本仓库已训练好的权重（可按需改 DEFAULT_WEIGHTS）。
依赖：仓库根目录 requirements.txt + yolov8s_pipeline/camera_runtime/requirements-deploy.txt（opencv-python）
"""

import sys
from pathlib import Path

import cv2
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[2]

# 改成你的 best.pt 路径；默认指向你当前工程里已有的 phase2 权重
DEFAULT_WEIGHTS = (
    ROOT
    / "runs"
    / "yolov8s_pipeline_detect"
    / "yolov8s_two_phase_phase2"
    / "weights"
    / "best.pt"
)
DEFAULT_CAMERA_INDEX = 0
IMGSZ = 640
CONF = 0.25


def open_camera(index: int) -> cv2.VideoCapture:
    if sys.platform.startswith("win"):
        cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    else:
        cap = cv2.VideoCapture(index)
    if not cap.isOpened():
        raise RuntimeError(f"无法打开摄像头 index={index}")
    return cap


def main() -> None:
    weights = DEFAULT_WEIGHTS
    if not weights.is_file():
        raise FileNotFoundError(
            f"未找到默认权重: {weights}\n请编辑 camera_rgb_detect.py 里的 DEFAULT_WEIGHTS 为你的 best.pt 路径。"
        )

    model = YOLO(str(weights))
    cap = open_camera(DEFAULT_CAMERA_INDEX)
    win = "fire_smoke_detect"

    cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            results = model.predict(
                source=frame,
                imgsz=IMGSZ,
                conf=CONF,
                verbose=False,
            )
            out = results[0].plot()
            cv2.imshow(win, out)
            if (cv2.waitKey(1) & 0xFF) in (27, ord("q")):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
