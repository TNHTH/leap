from __future__ import annotations

import time

import rclpy
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from rclpy.node import Node
from std_msgs.msg import String

from leap1_a20_interfaces.msg import FireEvent, MissionState, PerceptionDetection

from .common import (
    FIRE_EVENT_TOPIC,
    MISSION_COMMAND_TOPIC,
    MISSION_STATE_TOPIC,
    PERCEPTION_DETECTION_TOPIC,
    PERCEPTION_STATUS_TOPIC,
    json_dumps,
    now_stamp,
    utc_now_text,
)
from .perception_rules import bbox_area_ratio, is_positive_detection


class PerceptionBridgeNode(Node):
    """把检测结果裁决成最终火情事件。"""

    def __init__(self) -> None:
        super().__init__("perception_bridge_node")
        self.declare_parameter("hazard_type", "fire")
        self.declare_parameter("frame_confidence_threshold", 0.50)
        self.declare_parameter("trigger_confidence_threshold", 0.70)
        self.declare_parameter("trigger_consecutive_hits", 3)
        self.declare_parameter("clear_consecutive_misses", 10)
        self.declare_parameter("stale_timeout_sec", 1.0)
        self.declare_parameter("clear_timeout_sec", 2.0)
        self.declare_parameter("minimum_bbox_area", 0.01)
        self.declare_parameter("publish_period_sec", 0.2)
        self.declare_parameter("vehicle_camera_id", "vehicle_camera")
        self.declare_parameter("monitor_camera_names", "ground_camera")
        self.declare_parameter("monitor_dispatch_map_id", "")
        self.declare_parameter("monitor_dispatch_route_id", "ground_camera_response")
        self.declare_parameter("monitor_dispatch_cooldown_sec", 10.0)

        self.hazard_type = str(self.get_parameter("hazard_type").value)
        self.frame_confidence_threshold = float(self.get_parameter("frame_confidence_threshold").value)
        self.trigger_confidence_threshold = float(self.get_parameter("trigger_confidence_threshold").value)
        self.trigger_consecutive_hits = int(self.get_parameter("trigger_consecutive_hits").value)
        self.clear_consecutive_misses = int(self.get_parameter("clear_consecutive_misses").value)
        self.stale_timeout_sec = float(self.get_parameter("stale_timeout_sec").value)
        self.clear_timeout_sec = float(self.get_parameter("clear_timeout_sec").value)
        self.minimum_bbox_area = float(self.get_parameter("minimum_bbox_area").value)
        self.publish_period_sec = float(self.get_parameter("publish_period_sec").value)
        self.vehicle_camera_id = str(self.get_parameter("vehicle_camera_id").value)
        self.monitor_camera_names = {
            item.strip()
            for item in str(self.get_parameter("monitor_camera_names").value).split(",")
            if item.strip()
        }
        self.monitor_dispatch_map_id = str(self.get_parameter("monitor_dispatch_map_id").value)
        self.monitor_dispatch_route_id = str(self.get_parameter("monitor_dispatch_route_id").value)
        self.monitor_dispatch_cooldown_sec = float(self.get_parameter("monitor_dispatch_cooldown_sec").value)

        self.fire_event_pub = self.create_publisher(FireEvent, FIRE_EVENT_TOPIC, 10)
        self.mission_cmd_pub = self.create_publisher(String, MISSION_COMMAND_TOPIC, 10)
        self.status_pub = self.create_publisher(String, PERCEPTION_STATUS_TOPIC, 10)
        self.diagnostics_pub = self.create_publisher(DiagnosticArray, "/diagnostics", 10)
        self.create_subscription(
            PerceptionDetection,
            PERCEPTION_DETECTION_TOPIC,
            self._on_detection,
            10,
        )
        self.create_subscription(MissionState, MISSION_STATE_TOPIC, self._on_mission_state, 10)

        self._consecutive_hits = 0
        self._consecutive_misses = 0
        self._last_detection_monotonic = 0.0
        self._last_event = FireEvent()
        self._last_event.stamp = now_stamp(self)
        self._last_event.active = False
        self._last_event.source = "perception_bridge"
        self._last_event.camera_id = "vehicle_camera"
        self._last_event.level = "info"
        self._last_event.description = "等待检测结果"
        self._last_source = ""
        self._last_model = ""
        self._last_confidence = 0.0
        self._last_note = "waiting_detection"
        self._last_frame_ref = ""
        self._current_map_id = ""
        self._monitor_hits: dict[str, int] = {}
        self._monitor_last_dispatch: dict[str, float] = {}

        self.create_timer(max(self.publish_period_sec, 0.1), self._on_timer)

    def _area(self, msg: PerceptionDetection) -> float:
        return bbox_area_ratio(msg)

    def _is_positive_frame(self, msg: PerceptionDetection) -> bool:
        return is_positive_detection(
            msg,
            hazard_type=self.hazard_type,
            confidence_threshold=self.frame_confidence_threshold,
            minimum_bbox_area=self.minimum_bbox_area,
        )

    def _on_mission_state(self, msg: MissionState) -> None:
        if msg.map_id:
            self._current_map_id = msg.map_id

    def _publish_fire_event(self, active: bool, msg: PerceptionDetection | None = None, reason: str = "") -> None:
        event = FireEvent()
        event.stamp = now_stamp(self)
        event.active = active
        event.source = self._last_source or "perception_bridge"
        event.camera_id = "vehicle_camera"
        event.level = "critical" if active and self._last_confidence >= self.trigger_confidence_threshold else "warning"
        if msg is not None:
            event.source = msg.source or event.source
            event.camera_id = msg.camera_id or event.camera_id
        event.description = reason or (
            f"{self.hazard_type} detected conf={self._last_confidence:.2f} frame={self._last_frame_ref}"
            if active
            else f"{self.hazard_type} cleared"
        )
        self._last_event = event
        self.fire_event_pub.publish(event)
        command = String()
        command.data = json_dumps(
            {
                "command": "set_fire_active",
                "active": active,
                "source": event.source,
                "camera_id": event.camera_id,
                "level": event.level,
                "detail": event.description,
            }
        )
        self.mission_cmd_pub.publish(command)
        self.get_logger().info(f"发布火情事件 active={event.active} desc={event.description}")

    def _publish_mission_command(self, payload: dict) -> None:
        command = String()
        command.data = json_dumps(payload)
        self.mission_cmd_pub.publish(command)

    def _on_monitor_detection(self, msg: PerceptionDetection) -> None:
        camera_id = msg.camera_id or "unknown"
        if not self._is_positive_frame(msg):
            self._monitor_hits[camera_id] = 0
            return

        hits = self._monitor_hits.get(camera_id, 0) + 1
        self._monitor_hits[camera_id] = hits
        if hits < self.trigger_consecutive_hits:
            return

        now = time.monotonic()
        last_dispatch = self._monitor_last_dispatch.get(camera_id, 0.0)
        if now - last_dispatch < self.monitor_dispatch_cooldown_sec:
            return

        map_id = self.monitor_dispatch_map_id or self._current_map_id
        route_id = msg.region_id or self.monitor_dispatch_route_id
        if not map_id or not route_id:
            self.get_logger().warning(
                f"固定监控 {camera_id} 报警，但缺少 map_id 或 route_id，无法派车确认。"
            )
            return

        self._monitor_last_dispatch[camera_id] = now
        self._publish_mission_command(
            {
                "command": "start_patrol",
                "map_id": map_id,
                "route_id": route_id,
                "mode": "single_run",
                "detail": f"固定监控 {camera_id} 检测到 {msg.note or self.hazard_type}，前往附近确认火源",
            }
        )
        self.get_logger().info(f"固定监控报警派车: camera={camera_id} map={map_id} route={route_id}")

    def _on_detection(self, msg: PerceptionDetection) -> None:
        if msg.hazard_type != self.hazard_type:
            return

        self._last_detection_monotonic = time.monotonic()
        self._last_source = msg.source or "teammate_model"
        self._last_model = f"{msg.model_name}:{msg.model_version}".strip(":")
        self._last_confidence = float(msg.confidence)
        self._last_frame_ref = msg.frame_ref
        self._last_note = msg.note or ""

        camera_id = msg.camera_id or ""
        if camera_id in self.monitor_camera_names and camera_id != self.vehicle_camera_id:
            self._on_monitor_detection(msg)
            return

        if camera_id and camera_id != self.vehicle_camera_id:
            return

        if self._is_positive_frame(msg):
            self._consecutive_hits += 1
            self._consecutive_misses = 0
        else:
            self._consecutive_hits = 0
            self._consecutive_misses += 1

        if (
            not self._last_event.active
            and self._consecutive_hits >= self.trigger_consecutive_hits
            and float(msg.confidence) >= self.trigger_confidence_threshold
        ):
            self._publish_fire_event(True, msg=msg)
            return

        if self._last_event.active and self._consecutive_misses >= self.clear_consecutive_misses:
            self._publish_fire_event(False, msg=msg, reason=f"{self.hazard_type} cleared by misses")

    def _publish_status(self) -> None:
        now = time.monotonic()
        age_sec = None
        if self._last_detection_monotonic > 0.0:
            age_sec = max(0.0, now - self._last_detection_monotonic)
        input_online = age_sec is not None and age_sec <= self.stale_timeout_sec
        payload = {
            "hazard_type": self.hazard_type,
            "source": self._last_source,
            "model": self._last_model,
            "active": self._last_event.active,
            "confidence": self._last_confidence,
            "consecutive_hits": self._consecutive_hits,
            "consecutive_misses": self._consecutive_misses,
            "age_sec": age_sec,
            "input_online": input_online,
            "frame_ref": self._last_frame_ref,
            "note": self._last_note,
            "updated_at": utc_now_text(),
        }
        msg = String()
        msg.data = json_dumps(payload)
        self.status_pub.publish(msg)

        diag = DiagnosticArray()
        diag.header.stamp = now_stamp(self)
        status = DiagnosticStatus()
        status.name = f"a20/perception/{self.hazard_type}"
        status.hardware_id = self._last_model or "perception_bridge"
        if not input_online:
            status.level = DiagnosticStatus.WARN
            status.message = "detection_stale"
        else:
            status.level = DiagnosticStatus.OK
            status.message = "active" if self._last_event.active else "idle"
        status.values = [
            KeyValue(key="hazard_type", value=self.hazard_type),
            KeyValue(key="source", value=self._last_source),
            KeyValue(key="confidence", value=f"{self._last_confidence:.3f}"),
            KeyValue(key="frame_ref", value=self._last_frame_ref),
        ]
        diag.status.append(status)
        self.diagnostics_pub.publish(diag)

    def _on_timer(self) -> None:
        now = time.monotonic()
        if self._last_event.active and self._last_detection_monotonic > 0.0:
            age_sec = now - self._last_detection_monotonic
            if age_sec > max(self.stale_timeout_sec, self.clear_timeout_sec):
                self._consecutive_hits = 0
                self._consecutive_misses = self.clear_consecutive_misses
                self._publish_fire_event(False, reason=f"{self.hazard_type} cleared by stale timeout")
        self._publish_status()


def main() -> None:
    rclpy.init()
    node = PerceptionBridgeNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
