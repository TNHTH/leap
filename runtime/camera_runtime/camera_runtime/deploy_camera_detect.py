from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import cv2
from ultralytics import YOLO


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Deploy Ultralytics YOLO detect on a camera/stream (USB index or RTSP/HTTP URL)."
    )
    p.add_argument(
        "--weights",
        type=str,
        required=True,
        help="模型权重路径，例如训练输出的 weights/best.pt",
    )
    p.add_argument(
        "--source",
        type=str,
        default="0",
        help='相机源：USB 用 "0"/"1"；网络流用 rtsp://... 或 http://...（也支持视频文件路径）',
    )
    p.add_argument("--imgsz", type=int, default=640)
    p.add_argument("--conf", type=float, default=0.25)
    p.add_argument("--iou", type=float, default=0.45)
    p.add_argument("--device", type=str, default="", help='"" 自动；或 "0" / "cpu"')
    p.add_argument("--half", action="store_true", help="GPU 半精度推理（CUDA 时）")
    p.add_argument("--max-det", type=int, default=300)
    p.add_argument("--line-width", type=int, default=2)

    p.add_argument("--show", action=argparse.BooleanOptionalAction, default=True, help="是否弹窗显示")
    p.add_argument(
        "--save-dir",
        type=str,
        default="",
        help="若指定，则把带框结果写成图片序列（jpg）到该目录",
    )
    p.add_argument("--save-every", type=int, default=1, help="保存间隔（帧）")
    p.add_argument(
        "--window-name",
        type=str,
        default="yolov8_deploy",
        help="OpenCV 窗口标题（--no-show 时忽略）",
    )

    p.add_argument(
        "--warmup",
        type=int,
        default=2,
        help="启动后先跑几次空推理做 warmup（减少首帧统计抖动）",
    )
    return p.parse_args()


def open_capture(source: str) -> cv2.VideoCapture:
    if source.isdigit():
        if sys.platform.startswith("win"):
            cap = cv2.VideoCapture(int(source), cv2.CAP_DSHOW)  # Windows 下 DSHOW 通常更稳
        else:
            cap = cv2.VideoCapture(int(source))
    else:
        cap = cv2.VideoCapture(source, cv2.CAP_FFMPEG)
    if not cap.isOpened():
        raise RuntimeError(f"无法打开视频源: {source}")
    return cap


def main() -> None:
    args = parse_args()
    weights = str(Path(args.weights).expanduser().resolve())
    if not Path(weights).is_file():
        raise FileNotFoundError(weights)

    model = YOLO(weights)

    save_dir = Path(args.save_dir).expanduser().resolve() if args.save_dir.strip() else None
    if save_dir is not None:
        save_dir.mkdir(parents=True, exist_ok=True)

    cap = open_capture(str(args.source))

    if args.show:
        cv2.namedWindow(args.window_name, cv2.WINDOW_NORMAL)

    # warmup
    for _ in range(max(0, int(args.warmup))):
        ok, frame = cap.read()
        if not ok or frame is None:
            break
        _ = model.predict(
            source=frame,
            imgsz=int(args.imgsz),
            conf=float(args.conf),
            iou=float(args.iou),
            device=args.device or None,
            half=bool(args.half),
            max_det=int(args.max_det),
            verbose=False,
        )

    frame_id = 0
    fps_ema = 0.0

    try:
        while True:
            t_loop0 = time.perf_counter()
            ok, frame = cap.read()
            if not ok or frame is None:
                # 网络流偶发断帧：短暂等待再试，避免直接退出
                time.sleep(0.01)
                continue

            t_infer0 = time.perf_counter()
            results = model.predict(
                source=frame,
                imgsz=int(args.imgsz),
                conf=float(args.conf),
                iou=float(args.iou),
                device=args.device or None,
                half=bool(args.half),
                max_det=int(args.max_det),
                verbose=False,
            )
            out = results[0].plot(line_width=int(args.line_width))
            infer_ms = (time.perf_counter() - t_infer0) * 1000.0

            frame_id += 1
            loop_ms = (time.perf_counter() - t_loop0) * 1000.0
            fps_inst = 1000.0 / max(1e-3, loop_ms)
            fps_ema = fps_inst if fps_ema <= 0 else (fps_ema * 0.9 + fps_inst * 0.1)

            cv2.putText(
                out,
                f"FPS~:{fps_ema:5.1f}  loop:{loop_ms:6.1f}ms  infer:{infer_ms:6.1f}ms  frame:{frame_id}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 0),
                2,
                cv2.LINE_AA,
            )

            if args.show:
                cv2.imshow(args.window_name, out)
                key = cv2.waitKey(1) & 0xFF
                if key in (27, ord("q")):
                    break

            if save_dir is not None and args.save_every > 0 and (frame_id % int(args.save_every) == 0):
                out_path = save_dir / f"frame_{frame_id:08d}.jpg"
                cv2.imwrite(str(out_path), out)
    finally:
        cap.release()
        if args.show:
            cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
