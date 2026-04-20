from __future__ import annotations

import rclpy
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from rclpy.node import Node
from std_msgs.msg import String
from std_srvs.srv import SetBool, Trigger

from leap1_a20_interfaces.msg import PerceptionDetection

from .common import PERCEPTION_DETECTION_TOPIC, now_stamp


class PerceptionPlaceholderNode(Node):
    """统一占位检测节点，用于烟雾/高温链路演示。"""

    def __init__(self, node_name: str, hazard_type: str, default_temperature: float = 0.0) -> None:
        super().__init__(node_name)
        self.declare_parameter("hazard_type", hazard_type)
        self.declare_parameter("camera_id", "vehicle_camera")
        self.declare_parameter("source", node_name)
        self.declare_parameter("confidence", 0.90)
        self.declare_parameter("temperature_c", default_temperature)

        self.hazard_type = str(self.get_parameter("hazard_type").value)
        self.camera_id = str(self.get_parameter("camera_id").value)
        self.source = str(self.get_parameter("source").value)
        self.confidence = float(self.get_parameter("confidence").value)
        self.temperature_c = float(self.get_parameter("temperature_c").value)

        self.publisher = self.create_publisher(PerceptionDetection, PERCEPTION_DETECTION_TOPIC, 10)
        self.diagnostics_pub = self.create_publisher(DiagnosticArray, "/diagnostics", 10)
        self.command_sub = self.create_subscription(String, f"~/{self.hazard_type}_command", self._on_command, 10)
        self.set_active_srv = self.create_service(SetBool, "~/set_active", self._handle_set_active)
        self.clear_srv = self.create_service(Trigger, "~/clear", self._handle_clear)
        self._active = False
        self.create_timer(1.0, self._publish_status)

    def _publish_detection(self, active: bool, note: str = "") -> None:
        msg = PerceptionDetection()
        msg.stamp = now_stamp(self)
        msg.hazard_type = self.hazard_type
        msg.source = self.source
        msg.camera_id = self.camera_id
        msg.model_name = "placeholder"
        msg.model_version = "v1"
        msg.detected = active
        msg.confidence = self.confidence if active else 0.0
        msg.image_width = 640
        msg.image_height = 480
        msg.bbox_cx = 0.5 if active else 0.0
        msg.bbox_cy = 0.5 if active else 0.0
        msg.bbox_w = 0.2 if active else 0.0
        msg.bbox_h = 0.2 if active else 0.0
        msg.temperature_c = self.temperature_c
        msg.region_id = "center"
        msg.frame_ref = ""
        msg.note = note or ("placeholder_detected" if active else "placeholder_cleared")
        self.publisher.publish(msg)
        self._active = active

    def _handle_set_active(self, request: SetBool.Request, response: SetBool.Response) -> SetBool.Response:
        self._publish_detection(request.data, note="service_toggle")
        response.success = True
        response.message = f"{self.hazard_type} 状态已更新"
        return response

    def _handle_clear(self, request: Trigger.Request, response: Trigger.Response) -> Trigger.Response:
        del request
        self._publish_detection(False, note="service_clear")
        response.success = True
        response.message = f"{self.hazard_type} 已清除"
        return response

    def _on_command(self, msg: String) -> None:
        self._publish_detection(msg.data.strip().lower() in {"1", "true", "on", self.hazard_type}, note="topic_toggle")

    def _publish_status(self) -> None:
        diag = DiagnosticArray()
        diag.header.stamp = now_stamp(self)
        status = DiagnosticStatus()
        status.name = f"a20/placeholder/{self.hazard_type}"
        status.hardware_id = self.source
        status.level = DiagnosticStatus.OK
        status.message = "active" if self._active else "idle"
        status.values = [
            KeyValue(key="hazard_type", value=self.hazard_type),
            KeyValue(key="active", value=str(self._active).lower()),
        ]
        diag.status.append(status)
        self.diagnostics_pub.publish(diag)


def run_placeholder(node_name: str, hazard_type: str, default_temperature: float = 0.0) -> None:
    rclpy.init()
    node = PerceptionPlaceholderNode(node_name=node_name, hazard_type=hazard_type, default_temperature=default_temperature)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


def smoke_main() -> None:
    run_placeholder("smoke_detection_placeholder_node", "smoke", default_temperature=0.0)


def high_temp_main() -> None:
    run_placeholder("high_temp_detection_placeholder_node", "high_temp", default_temperature=85.0)
