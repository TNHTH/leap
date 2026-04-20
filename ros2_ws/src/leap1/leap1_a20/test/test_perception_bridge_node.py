from __future__ import annotations

import sys
import types
from dataclasses import dataclass, field
from pathlib import Path


REPO_PKG_ROOT = Path("/home/gwh/leap/ros2_ws/src/leap1/leap1_a20")
if str(REPO_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_PKG_ROOT))


def _install_ros_stubs() -> None:
    if "rclpy" not in sys.modules:
        rclpy_mod = types.ModuleType("rclpy")
        rclpy_mod.init = lambda: None
        rclpy_mod.spin = lambda node: None
        rclpy_mod.shutdown = lambda: None
        rclpy_mod.ok = lambda: False
        sys.modules["rclpy"] = rclpy_mod

    if "rclpy.node" not in sys.modules:
        node_mod = types.ModuleType("rclpy.node")

        class Node:
            pass

        node_mod.Node = Node
        sys.modules["rclpy.node"] = node_mod

    if "builtin_interfaces.msg" not in sys.modules:
        builtin_msg_mod = types.ModuleType("builtin_interfaces.msg")

        @dataclass
        class Time:
            sec: int = 0
            nanosec: int = 0

        builtin_msg_mod.Time = Time
        sys.modules["builtin_interfaces.msg"] = builtin_msg_mod
        builtin_mod = types.ModuleType("builtin_interfaces")
        builtin_mod.msg = builtin_msg_mod
        sys.modules["builtin_interfaces"] = builtin_mod

    if "std_msgs.msg" not in sys.modules:
        std_msg_mod = types.ModuleType("std_msgs.msg")

        @dataclass
        class String:
            data: str = ""

        std_msg_mod.String = String
        sys.modules["std_msgs.msg"] = std_msg_mod
        std_mod = types.ModuleType("std_msgs")
        std_mod.msg = std_msg_mod
        sys.modules["std_msgs"] = std_mod

    if "diagnostic_msgs.msg" not in sys.modules:
        diag_msg_mod = types.ModuleType("diagnostic_msgs.msg")

        @dataclass
        class KeyValue:
            key: str = ""
            value: str = ""

        @dataclass
        class DiagnosticStatus:
            OK = 0
            WARN = 1
            ERROR = 2

            level: int = 0
            name: str = ""
            hardware_id: str = ""
            message: str = ""
            values: list[KeyValue] = field(default_factory=list)

        @dataclass
        class Header:
            stamp: object | None = None

        @dataclass
        class DiagnosticArray:
            header: Header = field(default_factory=Header)
            status: list[DiagnosticStatus] = field(default_factory=list)

        diag_msg_mod.KeyValue = KeyValue
        diag_msg_mod.DiagnosticStatus = DiagnosticStatus
        diag_msg_mod.DiagnosticArray = DiagnosticArray
        sys.modules["diagnostic_msgs.msg"] = diag_msg_mod
        diag_mod = types.ModuleType("diagnostic_msgs")
        diag_mod.msg = diag_msg_mod
        sys.modules["diagnostic_msgs"] = diag_mod

    if "leap1_a20_interfaces.msg" not in sys.modules:
        iface_msg_mod = types.ModuleType("leap1_a20_interfaces.msg")

        @dataclass
        class FireEvent:
            stamp: object | None = None
            active: bool = False
            source: str = ""
            camera_id: str = ""
            level: str = ""
            description: str = ""

        @dataclass
        class PerceptionDetection:
            stamp: object | None = None
            hazard_type: str = "fire"
            source: str = ""
            camera_id: str = ""
            model_name: str = ""
            model_version: str = ""
            detected: bool = False
            confidence: float = 0.0
            image_width: int = 0
            image_height: int = 0
            bbox_cx: float = 0.0
            bbox_cy: float = 0.0
            bbox_w: float = 0.0
            bbox_h: float = 0.0
            temperature_c: float = 0.0
            region_id: str = ""
            frame_ref: str = ""
            note: str = ""

        @dataclass
        class MissionState:
            map_id: str = ""
            state: str = ""

        iface_msg_mod.FireEvent = FireEvent
        iface_msg_mod.PerceptionDetection = PerceptionDetection
        iface_msg_mod.MissionState = MissionState
        sys.modules["leap1_a20_interfaces.msg"] = iface_msg_mod
        iface_mod = types.ModuleType("leap1_a20_interfaces")
        iface_mod.msg = iface_msg_mod
        sys.modules["leap1_a20_interfaces"] = iface_mod

    if "leap1_a20.common" not in sys.modules:
        common_mod = types.ModuleType("leap1_a20.common")
        common_mod.MISSION_COMMAND_TOPIC = "/a20/mission/command"
        common_mod.MISSION_STATE_TOPIC = "/a20/mission/state"
        common_mod.FIRE_EVENT_TOPIC = "/a20/fire_event"
        common_mod.PERCEPTION_DETECTION_TOPIC = "/a20/perception/detection"
        common_mod.PERCEPTION_STATUS_TOPIC = "/a20/perception/status"
        common_mod.json_dumps = lambda payload: str(payload)
        common_mod.now_stamp = lambda node: node.get_clock().now().to_msg()
        common_mod.utc_now_text = lambda: "2026-04-13T00:00:00"
        sys.modules["leap1_a20.common"] = common_mod


_install_ros_stubs()

from leap1_a20.perception_bridge_node import PerceptionBridgeNode
from leap1_a20_interfaces.msg import FireEvent, PerceptionDetection


class _FakePublisher:
    def __init__(self) -> None:
        self.messages = []

    def publish(self, msg) -> None:
        self.messages.append(msg)


class _FakeLogger:
    def __init__(self) -> None:
        self.lines = []

    def info(self, text: str) -> None:
        self.lines.append(("info", text))


class _FakeClockNow:
    def to_msg(self):
        return object()


class _FakeClock:
    def now(self):
        return _FakeClockNow()


class _BridgeHarness:
    def __init__(self) -> None:
        self.hazard_type = "fire"
        self.frame_confidence_threshold = 0.50
        self.trigger_confidence_threshold = 0.70
        self.trigger_consecutive_hits = 3
        self.clear_consecutive_misses = 2
        self.stale_timeout_sec = 0.1
        self.clear_timeout_sec = 0.2
        self.minimum_bbox_area = 0.01
        self.vehicle_camera_id = "vehicle_camera"
        self.monitor_camera_names = {"ground_camera"}
        self.monitor_dispatch_map_id = ""
        self.monitor_dispatch_route_id = "ground_camera_response"
        self.monitor_dispatch_cooldown_sec = 10.0
        self.fire_event_pub = _FakePublisher()
        self.mission_cmd_pub = _FakePublisher()
        self.status_pub = _FakePublisher()
        self.diagnostics_pub = _FakePublisher()
        self._consecutive_hits = 0
        self._consecutive_misses = 0
        self._last_detection_monotonic = 0.0
        self._last_event = FireEvent(active=False, source="perception_bridge", camera_id="vehicle_camera", level="info", description="waiting")
        self._last_source = ""
        self._last_model = ""
        self._last_confidence = 0.0
        self._last_note = ""
        self._last_frame_ref = ""
        self._current_map_id = "map_demo"
        self._monitor_hits = {}
        self._monitor_last_dispatch = {}
        self._logger = _FakeLogger()

    def get_clock(self):
        return _FakeClock()

    def get_logger(self):
        return self._logger

    def _area(self, msg: PerceptionDetection) -> float:
        return PerceptionBridgeNode._area(self, msg)

    def _is_positive_frame(self, msg: PerceptionDetection) -> bool:
        return PerceptionBridgeNode._is_positive_frame(self, msg)

    def _publish_fire_event(self, active: bool, msg: PerceptionDetection | None = None, reason: str = "") -> None:
        return PerceptionBridgeNode._publish_fire_event(self, active, msg=msg, reason=reason)

    def _publish_mission_command(self, payload: dict) -> None:
        return PerceptionBridgeNode._publish_mission_command(self, payload)

    def _on_monitor_detection(self, msg: PerceptionDetection) -> None:
        return PerceptionBridgeNode._on_monitor_detection(self, msg)

    def _publish_status(self) -> None:
        return PerceptionBridgeNode._publish_status(self)


def _make_detection(**overrides) -> PerceptionDetection:
    payload = {
        "hazard_type": "fire",
        "source": "adapter",
        "camera_id": "vehicle_camera",
        "model_name": "demo",
        "model_version": "v1",
        "detected": True,
        "confidence": 0.92,
        "bbox_w": 0.2,
        "bbox_h": 0.2,
        "frame_ref": "frame-001",
        "note": "ok",
    }
    payload.update(overrides)
    return PerceptionDetection(**payload)


def test_positive_frame_filters_invalid_detection() -> None:
    bridge = _BridgeHarness()

    assert bridge._is_positive_frame(_make_detection()) is True
    assert bridge._is_positive_frame(_make_detection(hazard_type="smoke")) is False
    assert bridge._is_positive_frame(_make_detection(detected=False)) is False
    assert bridge._is_positive_frame(_make_detection(confidence=0.49)) is False
    assert bridge._is_positive_frame(_make_detection(bbox_w=0.05, bbox_h=0.05)) is False


def test_detection_requires_consecutive_hits_before_trigger() -> None:
    bridge = _BridgeHarness()

    for frame_idx in range(2):
        PerceptionBridgeNode._on_detection(bridge, _make_detection(frame_ref=f"frame-{frame_idx}"))
        assert bridge._last_event.active is False

    PerceptionBridgeNode._on_detection(bridge, _make_detection(frame_ref="frame-2"))

    assert bridge._last_event.active is True
    assert bridge._last_event.description.startswith("fire detected")
    assert [msg.active for msg in bridge.fire_event_pub.messages] == [True]


def test_ground_camera_dispatches_patrol_without_direct_fire_event() -> None:
    bridge = _BridgeHarness()

    for frame_idx in range(3):
        PerceptionBridgeNode._on_detection(
            bridge,
            _make_detection(
                camera_id="ground_camera",
                region_id="ground_camera_response",
                frame_ref=f"ground-{frame_idx}",
            ),
        )

    assert bridge.fire_event_pub.messages == []
    assert bridge.mission_cmd_pub.messages, "固定监控报警应发布派车命令"
    command_text = bridge.mission_cmd_pub.messages[-1].data
    assert "start_patrol" in command_text
    assert "map_demo" in command_text
    assert "ground_camera_response" in command_text


def test_timer_clears_active_event_after_stale_timeout(monkeypatch) -> None:
    bridge = _BridgeHarness()
    PerceptionBridgeNode._on_detection(bridge, _make_detection(frame_ref="frame-a"))
    PerceptionBridgeNode._on_detection(bridge, _make_detection(frame_ref="frame-b"))
    PerceptionBridgeNode._on_detection(bridge, _make_detection(frame_ref="frame-c"))
    assert bridge._last_event.active is True

    import leap1_a20.perception_bridge_node as perception_bridge_node

    monkeypatch.setattr(perception_bridge_node.time, "monotonic", lambda: 100.0)
    bridge._last_detection_monotonic = 99.7

    PerceptionBridgeNode._on_timer(bridge)

    assert bridge._last_event.active is False
    assert bridge._consecutive_misses == bridge.clear_consecutive_misses
    assert [msg.active for msg in bridge.fire_event_pub.messages][-1] is False
    assert bridge.status_pub.messages, "应发布状态消息"
    assert bridge.diagnostics_pub.messages, "应发布诊断消息"
