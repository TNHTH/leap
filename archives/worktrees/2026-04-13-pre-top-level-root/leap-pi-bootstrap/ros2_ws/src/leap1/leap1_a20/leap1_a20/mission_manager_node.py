from __future__ import annotations

import time
from typing import Dict

import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from std_msgs.msg import Bool, String

from leap1_a20_interfaces.msg import FireEvent, MissionState

from .common import (
    CAMERA_STATUS_TOPIC,
    FIRE_EVENT_TOPIC,
    MISSION_COMMAND_TOPIC,
    MISSION_LOG_TOPIC,
    MISSION_STATE_TOPIC,
    MISSION_STATES,
    json_dumps,
    now_stamp,
    parse_json,
    utc_now_text,
)


class MissionManagerNode(Node):
    """Leap A20 唯一任务真源状态机。"""

    def __init__(self) -> None:
        super().__init__("mission_manager_node")
        self.declare_parameter("publish_hz", 5.0)
        self.declare_parameter("odom_timeout_sec", 1.5)
        self.declare_parameter("camera_timeout_sec", 3.0)
        self.declare_parameter("spray_duration_sec", 4.0)
        self.declare_parameter("cooldown_duration_sec", 5.0)
        self.declare_parameter("stop_confirm_sec", 1.0)
        self.declare_parameter("startup_grace_sec", 8.0)
        self.declare_parameter("require_vehicle_camera", True)
        self.declare_parameter("required_camera_name", "vehicle_camera")

        self.publish_hz = float(self.get_parameter("publish_hz").value)
        self.odom_timeout_sec = float(self.get_parameter("odom_timeout_sec").value)
        self.camera_timeout_sec = float(self.get_parameter("camera_timeout_sec").value)
        self.spray_duration_sec = float(self.get_parameter("spray_duration_sec").value)
        self.cooldown_duration_sec = float(self.get_parameter("cooldown_duration_sec").value)
        self.stop_confirm_sec = float(self.get_parameter("stop_confirm_sec").value)
        self.startup_grace_sec = float(self.get_parameter("startup_grace_sec").value)
        self.require_vehicle_camera = bool(self.get_parameter("require_vehicle_camera").value)
        self.required_camera_name = str(self.get_parameter("required_camera_name").value)

        self.state_pub = self.create_publisher(MissionState, MISSION_STATE_TOPIC, 10)
        self.log_pub = self.create_publisher(String, MISSION_LOG_TOPIC, 10)
        self.cmd_vel_pub = self.create_publisher(Twist, "/cmd_vel", 10)
        self.pump_pub = self.create_publisher(Bool, "/pump_cmd", 10)

        self.create_subscription(FireEvent, FIRE_EVENT_TOPIC, self._on_fire_event, 10)
        self.create_subscription(String, MISSION_COMMAND_TOPIC, self._on_command, 10)
        self.create_subscription(String, CAMERA_STATUS_TOPIC, self._on_camera_status, 10)
        self.create_subscription(Odometry, "/odom", self._on_odom, 10)

        self._state = "BOOT"
        self._detail = "A20 状态机启动中"
        self._fault_code = ""
        self._map_id = ""
        self._route_id = ""
        self._patrol_active = False
        self._fire_active = False
        self._start_time = time.monotonic()
        self._last_odom_time = self._start_time
        self._camera_heartbeats: Dict[str, float] = {}
        self._camera_online: Dict[str, bool] = {}
        self._resume_state = "MISSION_READY"
        self._state_deadline = self._start_time + 0.5
        self._stop_reason = ""
        self._last_zero_cmd_time = 0.0
        self._last_pump_cmd: bool | None = None

        self.create_timer(1.0 / max(self.publish_hz, 1.0), self._on_tick)

    def _publish_log(self, level: str, message: str) -> None:
        payload = String()
        payload.data = json_dumps(
            {
                "level": level,
                "message": message,
                "state": self._state,
                "updated_at": utc_now_text(),
            }
        )
        self.log_pub.publish(payload)

    def _transition(self, new_state: str, detail: str, fault_code: str = "") -> None:
        if new_state not in MISSION_STATES:
            self.get_logger().warning(f"忽略未知状态: {new_state}")
            return
        changed = self._state != new_state or self._detail != detail or self._fault_code != fault_code
        self._state = new_state
        self._detail = detail
        self._fault_code = fault_code
        self._state_deadline = time.monotonic()
        if changed:
            self.get_logger().info(f"状态切换 -> {new_state}: {detail}")
            self._publish_log("info", f"状态切换 -> {new_state}: {detail}")

    def _enter_fault(self, fault_code: str, detail: str) -> None:
        if self._state == "FAULT" and self._fault_code == fault_code:
            return
        self._patrol_active = False
        self._transition("FAULT", detail, fault_code=fault_code)
        self._publish_zero_cmd(force=True)
        self._publish_pump(False)

    def _publish_zero_cmd(self, force: bool = False) -> None:
        now = time.monotonic()
        if not force and now - self._last_zero_cmd_time < 0.15:
            return
        msg = Twist()
        self.cmd_vel_pub.publish(msg)
        self._last_zero_cmd_time = now

    def _publish_pump(self, enabled: bool) -> None:
        if self._last_pump_cmd is enabled:
            return
        msg = Bool()
        msg.data = enabled
        self.pump_pub.publish(msg)
        self._last_pump_cmd = enabled

    def _on_odom(self, msg: Odometry) -> None:
        del msg
        self._last_odom_time = time.monotonic()

    def _on_camera_status(self, msg: String) -> None:
        payload = parse_json(msg.data)
        name = str(payload.get("camera_name", ""))
        if not name:
            return
        self._camera_heartbeats[name] = time.monotonic()
        self._camera_online[name] = bool(payload.get("online", False))

    def _on_fire_event(self, msg: FireEvent) -> None:
        previous_fire_active = self._fire_active
        self._fire_active = bool(msg.active)
        if msg.active:
            if previous_fire_active:
                return
            self._resume_state = "PATROLLING" if self._patrol_active else "MISSION_READY"
            self._patrol_active = False
            self._transition("FIRE_ALERT", msg.description or "收到火情事件")
            self._state_deadline = time.monotonic() + 0.2
            self._publish_zero_cmd(force=True)
            self._publish_pump(False)
        elif previous_fire_active:
            self._publish_log("info", "火情已清除，等待当前处置阶段完成。")

    def _on_command(self, msg: String) -> None:
        payload = parse_json(msg.data)
        command = str(payload.get("command", ""))
        if not command:
            return

        self._map_id = str(payload.get("map_id", self._map_id))
        self._route_id = str(payload.get("route_id", self._route_id))
        detail = str(payload.get("detail", command))

        if command in {"boot_done", "enter_idle"}:
            self._patrol_active = False
            self._transition("IDLE", detail)
            return
        if command in {"enter_mapping", "start_mapping"}:
            self._patrol_active = False
            self._transition("MAPPING", detail)
            return
        if command == "map_saved":
            self._transition("MAP_READY", detail)
            return
        if command == "start_annotation":
            self._transition("ANNOTATING", detail)
            return
        if command == "mission_ready":
            self._transition("MISSION_READY", detail)
            return
        if command == "start_patrol":
            self._patrol_active = True
            self._transition("PATROLLING", detail)
            return
        if command == "stop_patrol":
            self._patrol_active = False
            self._stop_reason = "manual_stop"
            self._transition("STOPPING", detail)
            self._state_deadline = time.monotonic() + self.stop_confirm_sec
            return
        if command == "patrol_completed":
            self._patrol_active = False
            self._transition("MISSION_READY", detail)
            return
        if command == "patrol_failed":
            self._enter_fault("patrol_failed", detail or "巡航执行失败")
            return
        if command == "fault":
            self._enter_fault(str(payload.get("fault_code", "external_fault")), detail)
            return
        if command == "clear_fault":
            self._fault_code = ""
            self._transition("IDLE", detail or "人工清除故障")
            return

    def _publish_state(self) -> None:
        msg = MissionState()
        msg.stamp = now_stamp(self)
        msg.state = self._state
        msg.detail = self._detail
        msg.healthy = self._state != "FAULT"
        msg.fault_code = self._fault_code
        msg.map_id = self._map_id
        msg.route_id = self._route_id
        msg.patrol_active = self._patrol_active
        msg.fire_active = self._fire_active
        self.state_pub.publish(msg)

    def _check_timeouts(self, now: float) -> None:
        if now - self._start_time < self.startup_grace_sec:
            return
        if self._state == "FAULT":
            return
        if now - self._last_odom_time > self.odom_timeout_sec:
            self._enter_fault("odom_timeout", "里程计心跳超时，疑似 agent 掉线或底盘失联")
            return
        if self.require_vehicle_camera:
            last_camera = self._camera_heartbeats.get(self.required_camera_name, 0.0)
            camera_online = self._camera_online.get(self.required_camera_name, False)
            camera_warmup_deadline = self._start_time + self.startup_grace_sec + self.camera_timeout_sec
            if last_camera == 0.0:
                if now > camera_warmup_deadline:
                    self._enter_fault("vehicle_camera_timeout", "车载相机心跳超时或设备离线")
                return
            if now - last_camera > self.camera_timeout_sec:
                self._enter_fault("vehicle_camera_timeout", "车载相机心跳超时或设备离线")
                return
            if not camera_online and now > camera_warmup_deadline:
                self._enter_fault("vehicle_camera_timeout", "车载相机心跳超时或设备离线")

    def _tick_fire_pipeline(self, now: float) -> None:
        if self._state == "FIRE_ALERT":
            self._publish_zero_cmd()
            self._publish_pump(False)
            if now >= self._state_deadline:
                self._transition("STOPPING", "火情确认，执行强制停车")
                self._state_deadline = now + self.stop_confirm_sec
            return

        if self._state == "STOPPING":
            self._publish_zero_cmd()
            self._publish_pump(False)
            if now < self._state_deadline:
                return
            if self._fire_active:
                self._transition("SPRAYING", "停车完成，开始喷水")
                self._state_deadline = now + self.spray_duration_sec
            else:
                self._transition("MISSION_READY", "已停止巡航")
            return

        if self._state == "SPRAYING":
            self._publish_zero_cmd()
            self._publish_pump(True)
            if now >= self._state_deadline:
                self._publish_pump(False)
                self._transition("COOLDOWN", "喷水结束，进入冷却")
                self._state_deadline = now + self.cooldown_duration_sec
            return

        if self._state == "COOLDOWN":
            self._publish_zero_cmd()
            self._publish_pump(False)
            if now < self._state_deadline:
                return
            if self._fire_active:
                self._transition("FIRE_ALERT", "火情仍存在，开始下一轮处置")
                self._state_deadline = now + 0.2
                return
            if self._resume_state == "PATROLLING":
                self._patrol_active = True
                self._transition("PATROLLING", "冷却完成，恢复巡航")
            else:
                self._patrol_active = False
                self._transition("MISSION_READY", "冷却完成，等待下一条任务")

    def _on_tick(self) -> None:
        now = time.monotonic()
        if self._state == "BOOT" and now >= self._state_deadline:
            self._transition("IDLE", "A20 栈已启动，待命")

        self._check_timeouts(now)
        self._tick_fire_pipeline(now)

        if self._state == "FAULT":
            self._publish_zero_cmd()
            self._publish_pump(False)

        self._publish_state()


def main() -> None:
    rclpy.init()
    node = MissionManagerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
