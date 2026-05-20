from __future__ import annotations

import os
from pathlib import Path
from typing import Dict

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image

from leap1_a20_interfaces.msg import PerceptionDetection

from .common import PERCEPTION_DETECTION_TOPIC, camera_image_topic, now_stamp
from .image_tools import image_to_bgr


def _split_csv(text: str) -> list[str]:
    return [item.strip() for item in text.split(",") if item.strip()]


def _parse_class_hazard_map(text: str) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for item in _split_csv(text):
        if ":" not in item:
            result[item] = item
            continue
        class_name, hazard_type = item.split(":", 1)
        result[class_name.strip()] = hazard_type.strip()
    return result


def _default_weight_candidates() -> list[Path]:
    env_weight = os.environ.get("LEAP1_CAMERA_RUNTIME_WEIGHTS", "").strip()
    candidates: list[Path] = []
    if env_weight:
        candidates.append(Path(env_weight).expanduser())
    candidates.extend(
        [
            Path.home() / "leap" / "runtime" / "camera_runtime" / "camera_runtime" / "weights" / "best.pt",
            Path("/home/gwh/leap/runtime/camera_runtime/camera_runtime/weights/best.pt"),
            Path("/home/leap/leap/runtime/camera_runtime/camera_runtime/weights/best.pt"),
        ]
    )
    return candidates


class YoloDetectionNode(Node):
    """把 camera_runtime YOLO smoke/fire 模型接成 A20 感知检测消息。"""

    def __init__(self) -> None:
        super().__init__("yolo_detection_node")
        self.declare_parameter("camera_id", "vehicle_camera")
        self.declare_parameter("image_topic", "")
        self.declare_parameter("output_topic", PERCEPTION_DETECTION_TOPIC)
        self.declare_parameter("model_path", "")
        self.declare_parameter("model_name", "camera_runtime_yolo")
        self.declare_parameter("model_version", "best.pt")
        self.declare_parameter("expected_classes", "smoke,fire")
        self.declare_parameter("class_hazard_map", "smoke:fire,fire:fire")
        self.declare_parameter("strict_model_semantics", True)
        self.declare_parameter("region_id", "")
        self.declare_parameter("process_every_n_frames", 3)
        self.declare_parameter("imgsz", 640)
        self.declare_parameter("conf", 0.25)
        self.declare_parameter("iou", 0.45)
        self.declare_parameter("device", "")
        self.declare_parameter("max_det", 20)

        self.camera_id = str(self.get_parameter("camera_id").value)
        image_topic_param = str(self.get_parameter("image_topic").value).strip()
        self.image_topic = image_topic_param or camera_image_topic(self.camera_id)
        self.output_topic = str(self.get_parameter("output_topic").value)
        self.model_name = str(self.get_parameter("model_name").value)
        self.model_version = str(self.get_parameter("model_version").value)
        self.expected_classes = set(_split_csv(str(self.get_parameter("expected_classes").value)))
        self.class_hazard_map = _parse_class_hazard_map(str(self.get_parameter("class_hazard_map").value))
        self.strict_model_semantics = bool(self.get_parameter("strict_model_semantics").value)
        self.region_id = str(self.get_parameter("region_id").value)
        self.process_every_n_frames = max(1, int(self.get_parameter("process_every_n_frames").value))
        self.imgsz = int(self.get_parameter("imgsz").value)
        self.conf = float(self.get_parameter("conf").value)
        self.iou = float(self.get_parameter("iou").value)
        self.device = str(self.get_parameter("device").value).strip() or None
        self.max_det = int(self.get_parameter("max_det").value)

        self.publisher = self.create_publisher(PerceptionDetection, self.output_topic, 10)
        self.create_subscription(Image, self.image_topic, self._on_image, 10)
        self._frame_count = 0
        self.model = self._load_model()

        self.get_logger().info(
            f"YOLO 检测节点已启动 camera={self.camera_id} input={self.image_topic} output={self.output_topic}"
        )

    def _resolve_model_path(self) -> Path:
        configured = str(self.get_parameter("model_path").value).strip()
        candidates = [Path(configured).expanduser()] if configured else _default_weight_candidates()
        for candidate in candidates:
            if candidate.is_file():
                return candidate.resolve()
        raise FileNotFoundError("未找到 YOLO 权重，请设置 model_path 或 LEAP1_CAMERA_RUNTIME_WEIGHTS")

    def _load_model(self):
        from ultralytics import YOLO

        model_path = self._resolve_model_path()
        model = YOLO(str(model_path))
        names = {str(value) for value in getattr(model, "names", {}).values()}
        expected_overlap = names & self.expected_classes
        if self.expected_classes and not expected_overlap:
            message = f"模型类别不匹配: names={sorted(names)} expected={sorted(self.expected_classes)}"
            if self.strict_model_semantics:
                raise RuntimeError(message)
            self.get_logger().warning(message)
        unexpected = names - self.expected_classes
        if unexpected:
            self.get_logger().warning(f"模型包含额外类别: {sorted(unexpected)}")
        self.get_logger().info(f"已加载 YOLO 权重 {model_path} names={sorted(names)}")
        return model

    def _on_image(self, msg: Image) -> None:
        self._frame_count += 1
        if self.process_every_n_frames > 1 and (self._frame_count % self.process_every_n_frames) != 0:
            return

        frame = self._image_to_bgr(msg)
        if frame is None:
            return

        result = self.model.predict(
            source=frame,
            imgsz=self.imgsz,
            conf=self.conf,
            iou=self.iou,
            device=self.device,
            max_det=self.max_det,
            verbose=False,
        )[0]
        detection = self._build_detection(msg, result)
        self.publisher.publish(detection)

    def _image_to_bgr(self, msg: Image) -> np.ndarray | None:
        return image_to_bgr(msg, logger=self.get_logger())

    def _build_detection(self, image_msg: Image, result) -> PerceptionDetection:
        best = None
        names = getattr(result, "names", getattr(self.model, "names", {}))
        boxes = getattr(result, "boxes", None)
        for box in boxes if boxes is not None else []:
            class_id = int(box.cls[0].item())
            class_name = str(names.get(class_id, class_id))
            if self.expected_classes and class_name not in self.expected_classes:
                continue
            confidence = float(box.conf[0].item())
            if best is None or confidence > best["confidence"]:
                best = {
                    "class_name": class_name,
                    "confidence": confidence,
                    "xyxy": [float(value) for value in box.xyxy[0].tolist()],
                }

        msg = PerceptionDetection()
        msg.stamp = now_stamp(self)
        msg.source = "yolo_detection_node"
        msg.camera_id = self.camera_id
        msg.model_name = self.model_name
        msg.model_version = self.model_version
        msg.image_width = int(image_msg.width)
        msg.image_height = int(image_msg.height)
        msg.region_id = self.region_id
        msg.frame_ref = f"{self.camera_id}:{image_msg.header.stamp.sec}.{image_msg.header.stamp.nanosec}"

        if best is None:
            msg.hazard_type = "fire"
            msg.detected = False
            msg.confidence = 0.0
            msg.note = "no_smoke_or_fire"
            return msg

        class_name = best["class_name"]
        x1, y1, x2, y2 = best["xyxy"]
        width = max(1.0, float(image_msg.width))
        height = max(1.0, float(image_msg.height))
        msg.hazard_type = self.class_hazard_map.get(class_name, class_name)
        msg.detected = True
        msg.confidence = float(best["confidence"])
        msg.bbox_cx = float(((x1 + x2) * 0.5) / width)
        msg.bbox_cy = float(((y1 + y2) * 0.5) / height)
        msg.bbox_w = float(max(0.0, x2 - x1) / width)
        msg.bbox_h = float(max(0.0, y2 - y1) / height)
        msg.note = f"class={class_name}"
        return msg


def main() -> None:
    rclpy.init()
    node = YoloDetectionNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
