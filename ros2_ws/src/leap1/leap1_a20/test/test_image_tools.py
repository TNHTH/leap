from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np


REPO_PKG_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_PKG_ROOT))

from leap1_a20.image_tools import channels_for_encoding, image_to_bgr


@dataclass
class _Image:
    width: int
    height: int
    step: int
    encoding: str
    data: bytes


class _Logger:
    def __init__(self) -> None:
        self.warnings: list[str] = []

    def warning(self, message: str) -> None:
        self.warnings.append(message)


def test_channels_for_encoding_keeps_existing_supported_set() -> None:
    assert channels_for_encoding("mono8") == 1
    assert channels_for_encoding("8uc1") == 1
    assert channels_for_encoding("bgr8") == 3
    assert channels_for_encoding("rgb8") == 3
    assert channels_for_encoding("bgra8") == 4
    assert channels_for_encoding("rgba8") == 4
    assert channels_for_encoding("unsupported") == 0


def test_image_to_bgr_preserves_bgr8_pixels() -> None:
    pixels = np.array([[[1, 2, 3], [4, 5, 6]]], dtype=np.uint8)
    msg = _Image(width=2, height=1, step=6, encoding="bgr8", data=pixels.tobytes())

    converted = image_to_bgr(msg)

    assert converted is not None
    assert converted.tolist() == pixels.tolist()


def test_image_to_bgr_converts_rgb8_to_bgr8() -> None:
    rgb = np.array([[[10, 20, 30]]], dtype=np.uint8)
    msg = _Image(width=1, height=1, step=3, encoding="rgb8", data=rgb.tobytes())

    converted = image_to_bgr(msg)

    assert converted is not None
    assert converted.tolist() == [[[30, 20, 10]]]


def test_image_to_bgr_rejects_short_rows_with_warning() -> None:
    logger = _Logger()
    msg = _Image(width=2, height=1, step=5, encoding="bgr8", data=b"\x00" * 5)

    assert image_to_bgr(msg, logger=logger) is None
    assert logger.warnings
