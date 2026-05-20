from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image

from leap1_a20_interfaces.msg import PerceptionDetection

from .common import PERCEPTION_DETECTION_TOPIC, camera_image_topic, clamp, now_stamp
from .image_tools import channels_for_encoding, image_to_bgr


@dataclass(frozen=True)
class FlameCandidate:
    x: int
    y: int
    width: int
    height: int
    contour_area: float
    bbox_area_ratio: float
    fill_ratio: float
    brightness_ratio: float
    warm_ratio: float
    confidence: float


class FlameDetectionNode(Node):
    """基于 OpenCV 的轻量火焰检测节点，输出统一感知合同。"""

    def __init__(self) -> None:
        super().__init__("flame_detection_node")
        self.declare_parameter("camera_id", "vehicle_camera")
        self.declare_parameter("image_topic", "")
        self.declare_parameter("output_topic", PERCEPTION_DETECTION_TOPIC)
        self.declare_parameter("source", "flame_detection_node")
        self.declare_parameter("model_name", "opencv_flame")
        self.declare_parameter("model_version", "2026-04-13")
        self.declare_parameter("process_every_n_frames", 2)
        self.declare_parameter("max_width", 320)
        self.declare_parameter("min_region_area_px", 180.0)
        self.declare_parameter("min_bbox_area_ratio", 0.010)
        self.declare_parameter("min_fill_ratio", 0.18)
        self.declare_parameter("confidence_threshold", 0.70)
        self.declare_parameter("warm_h_low", 0)
        self.declare_parameter("warm_h_high", 45)
        self.declare_parameter("warm_s_min", 90)
        self.declare_parameter("warm_v_min", 170)
        self.declare_parameter("white_v_min", 220)
        self.declare_parameter("white_s_max", 110)
        self.declare_parameter("red_min", 160)
        self.declare_parameter("red_margin", 18)

        self.camera_id = str(self.get_parameter("camera_id").value)
        image_topic_param = str(self.get_parameter("image_topic").value).strip()
        self.image_topic = image_topic_param or camera_image_topic(self.camera_id)
        self.output_topic = str(self.get_parameter("output_topic").value)
        self.source = str(self.get_parameter("source").value)
        self.model_name = str(self.get_parameter("model_name").value)
        self.model_version = str(self.get_parameter("model_version").value)
        self.process_every_n_frames = max(1, int(self.get_parameter("process_every_n_frames").value))
        self.max_width = max(0, int(self.get_parameter("max_width").value))
        self.min_region_area_px = max(1.0, float(self.get_parameter("min_region_area_px").value))
        self.min_bbox_area_ratio = max(0.0, float(self.get_parameter("min_bbox_area_ratio").value))
        self.min_fill_ratio = clamp(float(self.get_parameter("min_fill_ratio").value), 0.0, 1.0)
        self.confidence_threshold = clamp(float(self.get_parameter("confidence_threshold").value), 0.0, 1.0)
        self.warm_h_low = int(self.get_parameter("warm_h_low").value)
        self.warm_h_high = int(self.get_parameter("warm_h_high").value)
        self.warm_s_min = int(self.get_parameter("warm_s_min").value)
        self.warm_v_min = int(self.get_parameter("warm_v_min").value)
        self.white_v_min = int(self.get_parameter("white_v_min").value)
        self.white_s_max = int(self.get_parameter("white_s_max").value)
        self.red_min = int(self.get_parameter("red_min").value)
        self.red_margin = int(self.get_parameter("red_margin").value)

        self.publisher = self.create_publisher(PerceptionDetection, self.output_topic, 10)
        self.create_subscription(Image, self.image_topic, self._on_image, 10)

        self._frame_count = 0
        self._last_detected = False
        self._kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))

        self.get_logger().info(
            f"火焰检测已启动 input={self.image_topic} output={self.output_topic} model={self.model_name}:{self.model_version}"
        )

    def _on_image(self, msg: Image) -> None:
        self._frame_count += 1
        if self.process_every_n_frames > 1 and (self._frame_count % self.process_every_n_frames) != 0:
            return

        frame = self._image_to_bgr(msg)
        if frame is None:
            return

        original_height, original_width = frame.shape[:2]
        detection_frame = self._resize_frame(frame)
        candidate = self._detect_candidate(detection_frame)
        detection = self._build_detection(msg, candidate, original_width=original_width, original_height=original_height)
        self.publisher.publish(detection)

        if detection.detected != self._last_detected:
            self._last_detected = detection.detected
            self.get_logger().info(
                f"火焰检测状态切换 detected={detection.detected} confidence={detection.confidence:.2f} note={detection.note}"
            )

    def _image_to_bgr(self, msg: Image) -> np.ndarray | None:
        return image_to_bgr(msg, logger=self.get_logger())

    @staticmethod
    def _channels_for_encoding(encoding: str) -> int:
        return channels_for_encoding(encoding)

    def _resize_frame(self, frame: np.ndarray) -> np.ndarray:
        if self.max_width <= 0:
            return frame
        height, width = frame.shape[:2]
        if width <= self.max_width:
            return frame
        scale = self.max_width / float(width)
        new_height = max(1, int(round(height * scale)))
        return cv2.resize(frame, (self.max_width, new_height), interpolation=cv2.INTER_AREA)

    def _detect_candidate(self, frame: np.ndarray) -> FlameCandidate | None:
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blue, green, red = cv2.split(frame)

        warm_mask = cv2.inRange(
            hsv,
            (self.warm_h_low, self.warm_s_min, self.warm_v_min),
            (self.warm_h_high, 255, 255),
        )
        white_core_mask = cv2.inRange(
            hsv,
            (0, 0, self.white_v_min),
            (179, self.white_s_max, 255),
        )
        bright_mask = cv2.inRange(gray, self.warm_v_min, 255)
        dominant_red_mask = (
            (red >= self.red_min)
            & (red.astype(np.int16) >= green.astype(np.int16) + self.red_margin)
            & (green.astype(np.int16) >= blue.astype(np.int16) - self.red_margin)
        )

        mask = cv2.bitwise_or(warm_mask, white_core_mask)
        mask = cv2.bitwise_and(mask, bright_mask)
        mask = cv2.bitwise_and(mask, dominant_red_mask.astype(np.uint8) * 255)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, self._kernel, iterations=1)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, self._kernel, iterations=2)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None

        frame_area = float(frame.shape[0] * frame.shape[1])
        best_candidate: FlameCandidate | None = None
        best_score = -1.0

        for contour in contours:
            contour_area = float(cv2.contourArea(contour))
            if contour_area < self.min_region_area_px:
                continue

            x, y, width, height = cv2.boundingRect(contour)
            if width <= 0 or height <= 0:
                continue

            bbox_area = float(width * height)
            bbox_area_ratio = bbox_area / frame_area
            fill_ratio = contour_area / bbox_area
            if bbox_area_ratio < self.min_bbox_area_ratio or fill_ratio < self.min_fill_ratio:
                continue

            roi = frame[y : y + height, x : x + width]
            roi_gray = gray[y : y + height, x : x + width]
            roi_red = red[y : y + height, x : x + width]
            roi_green = green[y : y + height, x : x + width]
            roi_blue = blue[y : y + height, x : x + width]

            brightness_ratio = float(np.mean(roi_gray)) / 255.0
            mean_red = float(np.mean(roi_red))
            mean_green = float(np.mean(roi_green))
            mean_blue = float(np.mean(roi_blue))
            warm_ratio = clamp((mean_red - max(mean_green, mean_blue)) / max(mean_red, 1.0), 0.0, 1.0)

            confidence = clamp(
                0.45 * min(1.0, bbox_area_ratio / max(self.min_bbox_area_ratio * 4.0, 1e-6))
                + 0.25 * fill_ratio
                + 0.15 * brightness_ratio
                + 0.15 * warm_ratio,
                0.0,
                1.0,
            )
            score = confidence + bbox_area_ratio
            if score <= best_score:
                continue

            best_score = score
            best_candidate = FlameCandidate(
                x=x,
                y=y,
                width=width,
                height=height,
                contour_area=contour_area,
                bbox_area_ratio=bbox_area_ratio,
                fill_ratio=fill_ratio,
                brightness_ratio=brightness_ratio,
                warm_ratio=warm_ratio,
                confidence=confidence,
            )

        return best_candidate

    def _build_detection(
        self,
        msg: Image,
        candidate: FlameCandidate | None,
        *,
        original_width: int,
        original_height: int,
    ) -> PerceptionDetection:
        detection = PerceptionDetection()
        detection.stamp = msg.header.stamp if (msg.header.stamp.sec or msg.header.stamp.nanosec) else now_stamp(self)
        detection.hazard_type = "fire"
        detection.source = self.source
        detection.camera_id = self.camera_id
        detection.model_name = self.model_name
        detection.model_version = self.model_version
        detection.image_width = max(0, original_width)
        detection.image_height = max(0, original_height)
        detection.temperature_c = 0.0
        detection.region_id = "vehicle_camera"
        detection.frame_ref = self._frame_ref(msg)

        if candidate is None or candidate.confidence < self.confidence_threshold:
            detection.detected = False
            detection.confidence = candidate.confidence if candidate is not None else 0.0
            detection.note = "opencv_flame:no_candidate" if candidate is None else "opencv_flame:below_threshold"
            return detection

        frame_width = float(self._resize_frame_shape(original_width, original_height)[0])
        frame_height = float(self._resize_frame_shape(original_width, original_height)[1])
        detection.detected = True
        detection.confidence = candidate.confidence
        detection.bbox_cx = clamp((candidate.x + candidate.width * 0.5) / frame_width, 0.0, 1.0)
        detection.bbox_cy = clamp((candidate.y + candidate.height * 0.5) / frame_height, 0.0, 1.0)
        detection.bbox_w = clamp(candidate.width / frame_width, 0.0, 1.0)
        detection.bbox_h = clamp(candidate.height / frame_height, 0.0, 1.0)
        detection.note = (
            f"opencv_flame:area={candidate.bbox_area_ratio:.4f};fill={candidate.fill_ratio:.3f};warm={candidate.warm_ratio:.3f}"
        )
        return detection

    def _resize_frame_shape(self, width: int, height: int) -> tuple[int, int]:
        if self.max_width <= 0 or width <= self.max_width:
            return width, height
        scale = self.max_width / float(width)
        return self.max_width, max(1, int(round(height * scale)))

    @staticmethod
    def _frame_ref(msg: Image) -> str:
        return f"{msg.header.stamp.sec}.{msg.header.stamp.nanosec:09d}"


def main() -> None:
    rclpy.init()
    node = FlameDetectionNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
