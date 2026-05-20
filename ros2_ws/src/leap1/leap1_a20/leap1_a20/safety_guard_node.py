from __future__ import annotations

import time

import rclpy
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from std_msgs.msg import Bool, String

from leap1_a20_interfaces.msg import MissionState

from .common import (
    CAMERA_STATUS_TOPIC,
    MISSION_COMMAND_TOPIC,
    MISSION_LOG_TOPIC,
    MISSION_STATE_TOPIC,
    PERCEPTION_STATUS_TOPIC,
    SAFETY_STATUS_TOPIC,
    json_dumps,
    now_stamp,
    parse_json,
    utc_now_text,
)


class SafetyGuardNode(Node):
    """独立安全守护节点，关键链路失活时强制停泵停转。"""

    def __init__(self) -> None:
        super().__init__("safety_guard_node")
        self.declare_parameter("mission_timeout_sec", 2.0)
        self.declare_parameter("perception_timeout_sec", 2.5)
        self.declare_parameter("camera_timeout_sec", 3.5)
        self.declare_parameter("odom_timeout_sec", 2.0)
        self.declare_parameter("startup_grace_sec", 8.0)
        self.declare_parameter("required_camera_name", "vehicle_camera")

        self.mission_timeout_sec = float(self.get_parameter("mission_timeout_sec").value)
        self.perception_timeout_sec = float(self.get_parameter("perception_timeout_sec").value)
        self.camera_timeout_sec = float(self.get_parameter("camera_timeout_sec").value)
        self.odom_timeout_sec = float(self.get_parameter("odom_timeout_sec").value)
        self.startup_grace_sec = float(self.get_parameter("startup_grace_sec").value)
        self.required_camera_name = str(self.get_parameter("required_camera_name").value)

        self.cmd_vel_pub = self.create_publisher(Twist, "/cmd_vel", 10)
        self.pump_pub = self.create_publisher(Bool, "/pump_cmd", 10)
        self.mission_cmd_pub = self.create_publisher(String, MISSION_COMMAND_TOPIC, 10)
        self.log_pub = self.create_publisher(String, MISSION_LOG_TOPIC, 10)
        self.status_pub = self.create_publisher(String, SAFETY_STATUS_TOPIC, 10)
        self.diagnostics_pub = self.create_publisher(DiagnosticArray, "/diagnostics", 10)

        self.create_subscription(MissionState, MISSION_STATE_TOPIC, self._on_mission_state, 10)
        self.create_subscription(String, PERCEPTION_STATUS_TOPIC, self._on_perception_status, 10)
        self.create_subscription(String, CAMERA_STATUS_TOPIC, self._on_camera_status, 10)
        self.create_subscription(Odometry, "/odom", self._on_odom, 10)
        self.create_subscription(Bool, "/pump_state", self._on_pump_state, 10)
        self.create_subscription(String, MISSION_COMMAND_TOPIC, self._on_mission_command, 10)

        self._last_mission = 0.0
        self._last_perception = 0.0
        self._last_camera = 0.0
        self._last_odom = 0.0
        self._last_fault = ""
        self._mission_state = "BOOT"
        self._pump_state = False
        self._perception_input_online = False
        self._authorized_until = 0.0
        self._start_time = time.monotonic()

        self.create_timer(0.5, self._on_timer)

    def _on_mission_state(self, msg: MissionState) -> None:
        self._last_mission = time.monotonic()
        self._mission_state = msg.state

    def _on_perception_status(self, msg: String) -> None:
        payload = parse_json(msg.data)
        if payload:
            self._last_perception = time.monotonic()
            self._perception_input_online = bool(payload.get("input_online", False))

    def _on_camera_status(self, msg: String) -> None:
        payload = parse_json(msg.data)
        if str(payload.get("camera_name", "")) == self.required_camera_name:
            self._last_camera = time.monotonic()

    def _on_odom(self, msg: Odometry) -> None:
        del msg
        self._last_odom = time.monotonic()

    def _on_pump_state(self, msg: Bool) -> None:
        self._pump_state = bool(msg.data)

    def _on_mission_command(self, msg: String) -> None:
        payload = parse_json(msg.data)
        if str(payload.get("command", "")) == "authorized_pump_test":
            duration = float(payload.get("duration_sec", 10.0))
            self._authorized_until = time.monotonic() + max(1.0, duration)

    def _publish_fault(self, fault_code: str, detail: str) -> None:
        if self._last_fault == fault_code:
            return
        self._last_fault = fault_code
        self.cmd_vel_pub.publish(Twist())
        pump_msg = Bool()
        pump_msg.data = False
        self.pump_pub.publish(pump_msg)

        fault_payload = String()
        fault_payload.data = json_dumps({"command": "fault", "fault_code": fault_code, "detail": detail})
        self.mission_cmd_pub.publish(fault_payload)

        log_msg = String()
        log_msg.data = json_dumps({"level": "error", "message": detail, "updated_at": utc_now_text()})
        self.log_pub.publish(log_msg)
        self.get_logger().error(detail)

    def _publish_status(self, active_fault: str, detail: str) -> None:
        payload = {
            "fault_code": active_fault,
            "detail": detail,
            "mission_state": self._mission_state,
            "pump_state": self._pump_state,
            "authorized_test": time.monotonic() < self._authorized_until,
            "perception_input_online": self._perception_input_online,
            "updated_at": utc_now_text(),
        }
        msg = String()
        msg.data = json_dumps(payload)
        self.status_pub.publish(msg)

        diag = DiagnosticArray()
        diag.header.stamp = now_stamp(self)
        status = DiagnosticStatus()
        status.name = "a20/safety_guard"
        status.hardware_id = "safety_guard"
        status.level = DiagnosticStatus.OK if not active_fault else DiagnosticStatus.ERROR
        status.message = detail
        status.values = [
            KeyValue(key="mission_state", value=self._mission_state),
            KeyValue(key="fault_code", value=active_fault),
        ]
        diag.status.append(status)
        self.diagnostics_pub.publish(diag)

    def _on_timer(self) -> None:
        now = time.monotonic()
        active_fault = ""
        detail = "ok"

        if now - self._start_time < self.startup_grace_sec:
            self._publish_status(active_fault, "startup_grace")
            return

        if self._last_mission == 0.0 or now - self._last_mission > self.mission_timeout_sec:
            active_fault = "mission_timeout"
            detail = "安全守护检测到 mission manager 心跳超时"
        elif self._last_odom == 0.0 or now - self._last_odom > self.odom_timeout_sec:
            active_fault = "odom_timeout"
            detail = "安全守护检测到底盘心跳超时"
        elif self._last_camera == 0.0 or now - self._last_camera > self.camera_timeout_sec:
            active_fault = "vehicle_camera_timeout"
            detail = "安全守护检测到车载相机心跳超时"
        elif self._last_perception == 0.0 or now - self._last_perception > self.perception_timeout_sec:
            active_fault = "perception_timeout"
            detail = "安全守护检测到感知适配链路超时"
        elif (
            self._pump_state
            and self._mission_state not in {"STOPPING", "SPRAYING"}
            and now >= self._authorized_until
        ):
            active_fault = "pump_interlock"
            detail = "检测到非法泵开启状态，已强制回落"

        if active_fault:
            self._publish_fault(active_fault, detail)
        else:
            self._last_fault = ""

        self._publish_status(active_fault, detail)


def main() -> None:
    rclpy.init()
    node = SafetyGuardNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
