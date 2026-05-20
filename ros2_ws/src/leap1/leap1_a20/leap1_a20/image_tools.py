from __future__ import annotations

from typing import Any

import cv2
import numpy as np


def channels_for_encoding(encoding: str) -> int:
    normalized = encoding.lower()
    if normalized in {"mono8", "8uc1"}:
        return 1
    if normalized in {"bgr8", "rgb8"}:
        return 3
    if normalized in {"bgra8", "rgba8"}:
        return 4
    return 0


def _warn(logger: Any | None, message: str) -> None:
    if logger is not None:
        logger.warning(message)


def image_to_bgr(msg: Any, logger: Any | None = None) -> np.ndarray | None:
    """将常见 ROS Image 编码转换为 OpenCV BGR 图像。"""
    encoding = str(msg.encoding).lower()
    channels = channels_for_encoding(encoding)
    if channels == 0:
        _warn(logger, f"暂不支持的图像编码: {msg.encoding}")
        return None

    row_bytes = int(msg.width) * channels
    if int(msg.step) < row_bytes:
        _warn(logger, f"图像步长异常 width={msg.width} channels={channels} step={msg.step}")
        return None

    required = int(msg.step) * int(msg.height)
    buffer = np.frombuffer(msg.data, dtype=np.uint8)
    if buffer.size < required:
        _warn(logger, f"图像数据长度不足 expected={required} actual={buffer.size}")
        return None

    matrix = buffer[:required].reshape((int(msg.height), int(msg.step)))
    pixels = matrix[:, :row_bytes]
    if channels == 1:
        gray = pixels.reshape((int(msg.height), int(msg.width)))
        return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

    image = np.ascontiguousarray(pixels.reshape((int(msg.height), int(msg.width), channels)))
    if encoding == "bgr8":
        return image
    if encoding == "rgb8":
        return cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    if encoding == "bgra8":
        return cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
    if encoding == "rgba8":
        return cv2.cvtColor(image, cv2.COLOR_RGBA2BGR)
    return None
