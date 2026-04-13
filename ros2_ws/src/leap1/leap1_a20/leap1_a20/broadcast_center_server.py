from __future__ import annotations

import mimetypes
import os
import shutil
import socket
import subprocess
import threading
import time
from collections import deque
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict
from urllib.parse import urlparse

import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from sensor_msgs.msg import BatteryState
from std_msgs.msg import Bool, String

from leap1_a20_interfaces.msg import MissionState

from .common import (
    CAMERA_STATUS_TOPIC,
    FIRE_COMMAND_TOPIC,
    MISSION_COMMAND_TOPIC,
    MISSION_LOG_TOPIC,
    MISSION_STATE_TOPIC,
    PATROL_STATUS_TOPIC,
    clamp,
    json_dumps,
    parse_json,
    utc_now_text,
)
from .map_tools import (
    draw_keepout_mask,
    keepout_png_bytes,
    list_maps,
    load_annotations,
    map_dir,
    map_png_bytes,
    save_annotations,
    sanitize_map_id,
)
from .paths import ensure_runtime_layout, package_share, repo_root


class _ThreadingHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class BroadcastCenterServer(Node):
    """统一 Web 面板后端。"""

    def __init__(self) -> None:
        super().__init__("broadcast_center_server")
        self.declare_parameter("bind_host", "0.0.0.0")
        self.declare_parameter("bind_port", 8090)
        self.declare_parameter("panel_mode", "full_stack")
        self.declare_parameter("expected_vehicle_camera", True)
        self.declare_parameter("expected_ground_camera", False)
        self.declare_parameter("teleop_hz", 20.0)
        self.declare_parameter("teleop_timeout_sec", 0.8)
        self.declare_parameter("runtime_root", "")

        self.bind_host = str(self.get_parameter("bind_host").value)
        self.bind_port = int(self.get_parameter("bind_port").value)
        self.panel_mode = str(self.get_parameter("panel_mode").value)
        self.expected_vehicle_camera = bool(self.get_parameter("expected_vehicle_camera").value)
        self.expected_ground_camera = bool(self.get_parameter("expected_ground_camera").value)
        self.teleop_hz = float(self.get_parameter("teleop_hz").value)
        self.teleop_timeout_sec = float(self.get_parameter("teleop_timeout_sec").value)
        self.runtime_root = ensure_runtime_layout(str(self.get_parameter("runtime_root").value))
        self.web_root = package_share() / "web"
        self._boot_time = time.time()
        self._hostname = socket.gethostname()

        self.cmd_vel_pub = self.create_publisher(Twist, "/cmd_vel", 10)
        self.pump_pub = self.create_publisher(Bool, "/pump_cmd", 10)
        self.fire_cmd_pub = self.create_publisher(String, FIRE_COMMAND_TOPIC, 10)
        self.mission_cmd_pub = self.create_publisher(String, MISSION_COMMAND_TOPIC, 10)

        self.create_subscription(MissionState, MISSION_STATE_TOPIC, self._on_mission_state, 10)
        self.create_subscription(String, CAMERA_STATUS_TOPIC, self._on_camera_status, 10)
        self.create_subscription(Bool, "/pump_state", self._on_pump_state, 10)
        self.create_subscription(BatteryState, "/battery_state", self._on_battery_state, 10)
        self.create_subscription(Odometry, "/odom", self._on_odom, 10)
        self.create_subscription(String, PATROL_STATUS_TOPIC, self._on_patrol_status, 10)
        self.create_subscription(String, MISSION_LOG_TOPIC, self._on_mission_log, 10)

        self._lock = threading.Lock()
        self._logs: deque[Dict[str, Any]] = deque(maxlen=120)
        self._mission: Dict[str, Any] = {
            "state": "BOOT",
            "detail": "等待状态机上线",
            "updated_at": utc_now_text(),
        }
        self._camera_heartbeats: Dict[str, float] = {}
        self._cameras: Dict[str, Dict[str, Any]] = {
            "vehicle_camera": {"online": False, "mjpeg_port": 8091},
            "ground_camera": {"online": False, "mjpeg_port": 8092},
        }
        self._battery: Dict[str, Any] = {}
        self._odom: Dict[str, Any] = {}
        self._last_odom_monotonic: float | None = None
        self._patrol: Dict[str, Any] = {}
        self._pump_state = False
        self._teleop_target = {"vx": 0.0, "vz": 0.0}
        self._last_teleop_input = 0.0
        self._teleop_zero_sent = True
        self._http_server: _ThreadingHTTPServer | None = None

        self.create_timer(1.0 / max(self.teleop_hz, 1.0), self._teleop_tick)
        self._start_http_server()
        self._append_log("info", "广播中心已启动")

    def _read_meminfo(self) -> Dict[str, int]:
        result: Dict[str, int] = {}
        try:
            for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
                if ":" not in line:
                    continue
                key, value = line.split(":", 1)
                number = value.strip().split()[0]
                result[key] = int(number)
        except (FileNotFoundError, ValueError):
            return {}
        return result

    def _resolve_ipv4_addresses(self) -> list[str]:
        addresses: list[str] = []
        try:
            probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                probe.connect(("8.8.8.8", 80))
                candidate = probe.getsockname()[0]
                if candidate and not candidate.startswith("127."):
                    addresses.append(candidate)
            finally:
                probe.close()
        except OSError:
            pass

        try:
            for _, _, _, _, sockaddr in socket.getaddrinfo(self._hostname, None, socket.AF_INET):
                candidate = sockaddr[0]
                if candidate and not candidate.startswith("127.") and candidate not in addresses:
                    addresses.append(candidate)
        except socket.gaierror:
            pass
        return addresses

    def _system_payload(self) -> Dict[str, Any]:
        meminfo = self._read_meminfo()
        memory_total_kib = int(meminfo.get("MemTotal", 0))
        memory_available_kib = int(meminfo.get("MemAvailable", 0))
        memory_used_kib = max(memory_total_kib - memory_available_kib, 0)
        memory_used_percent = (
            round((memory_used_kib / memory_total_kib) * 100.0, 1)
            if memory_total_kib
            else 0.0
        )

        disk_usage = shutil.disk_usage(self.runtime_root)
        disk_used = disk_usage.total - disk_usage.free
        disk_used_percent = round((disk_used / max(disk_usage.total, 1)) * 100.0, 1)

        odom_age_sec = None
        if self._last_odom_monotonic is not None:
            odom_age_sec = max(0.0, time.monotonic() - self._last_odom_monotonic)

        vehicle_camera_age_sec = None
        if "vehicle_camera" in self._camera_heartbeats:
            vehicle_camera_age_sec = max(0.0, time.monotonic() - self._camera_heartbeats["vehicle_camera"])
        ground_camera_age_sec = None
        if "ground_camera" in self._camera_heartbeats:
            ground_camera_age_sec = max(0.0, time.monotonic() - self._camera_heartbeats["ground_camera"])

        uptime_sec = 0
        try:
            uptime_sec = int(float(Path("/proc/uptime").read_text(encoding="utf-8").split()[0]))
        except (FileNotFoundError, ValueError, IndexError):
            uptime_sec = max(0, int(time.time() - self._boot_time))

        return {
            "panel_mode": self.panel_mode,
            "hostname": self._hostname,
            "ipv4": self._resolve_ipv4_addresses(),
            "uptime_sec": uptime_sec,
            "loadavg": [round(value, 2) for value in os.getloadavg()],
            "cpu_count": os.cpu_count() or 0,
            "memory": {
                "total_kib": memory_total_kib,
                "available_kib": memory_available_kib,
                "used_percent": memory_used_percent,
            },
            "disk": {
                "total_bytes": disk_usage.total,
                "free_bytes": disk_usage.free,
                "used_percent": disk_used_percent,
            },
            "signals": {
                "odom_online": odom_age_sec is not None and odom_age_sec <= 1.5,
                "odom_age_sec": odom_age_sec,
                "vehicle_camera_expected": self.expected_vehicle_camera,
                "vehicle_camera_online": bool(self._cameras.get("vehicle_camera", {}).get("online", False)),
                "vehicle_camera_age_sec": vehicle_camera_age_sec,
                "ground_camera_expected": self.expected_ground_camera,
                "ground_camera_online": bool(self._cameras.get("ground_camera", {}).get("online", False)),
                "ground_camera_age_sec": ground_camera_age_sec,
            },
            "runtime_root": str(self.runtime_root),
            "updated_at": utc_now_text(),
        }

    def destroy_node(self) -> bool:
        if rclpy.ok():
            try:
                self._publish_zero()
                self._publish_pump(False)
            except Exception as exc:  # noqa: BLE001
                self.get_logger().debug(f"广播中心关闭时停止命令发布失败: {exc}")
        if self._http_server is not None:
            self._http_server.shutdown()
            self._http_server.server_close()
        return super().destroy_node()

    def _append_log(self, level: str, message: str) -> None:
        with self._lock:
            self._logs.appendleft(
                {
                    "level": level,
                    "message": message,
                    "updated_at": utc_now_text(),
                }
            )

    def _publish_json_topic(self, publisher, payload: Dict[str, Any]) -> None:
        msg = String()
        msg.data = json_dumps(payload)
        publisher.publish(msg)

    def _publish_zero(self) -> None:
        self.cmd_vel_pub.publish(Twist())

    def _publish_pump(self, enabled: bool) -> None:
        msg = Bool()
        msg.data = enabled
        self.pump_pub.publish(msg)

    def _teleop_tick(self) -> None:
        now = time.monotonic()
        if now - self._last_teleop_input <= self.teleop_timeout_sec:
            msg = Twist()
            msg.linear.x = float(self._teleop_target["vx"])
            msg.angular.z = float(self._teleop_target["vz"])
            self.cmd_vel_pub.publish(msg)
            self._teleop_zero_sent = False
            return
        if not self._teleop_zero_sent:
            self._publish_zero()
            self._teleop_zero_sent = True

    def _on_mission_state(self, msg: MissionState) -> None:
        with self._lock:
            previous_state = self._mission.get("state")
            self._mission = {
                "state": msg.state,
                "detail": msg.detail,
                "healthy": msg.healthy,
                "fault_code": msg.fault_code,
                "map_id": msg.map_id,
                "route_id": msg.route_id,
                "patrol_active": msg.patrol_active,
                "fire_active": msg.fire_active,
                "updated_at": utc_now_text(),
            }
        if previous_state != msg.state:
            self._append_log("info", f"状态切换到 {msg.state}: {msg.detail}")

    def _on_camera_status(self, msg: String) -> None:
        payload = parse_json(msg.data)
        name = str(payload.get("camera_name", ""))
        if not name:
            return
        self._camera_heartbeats[name] = time.monotonic()
        with self._lock:
            self._cameras[name] = payload

    def _on_pump_state(self, msg: Bool) -> None:
        with self._lock:
            self._pump_state = bool(msg.data)

    def _on_battery_state(self, msg: BatteryState) -> None:
        with self._lock:
            self._battery = {
                "voltage": msg.voltage,
                "percentage": msg.percentage,
                "updated_at": utc_now_text(),
            }

    def _on_odom(self, msg: Odometry) -> None:
        self._last_odom_monotonic = time.monotonic()
        with self._lock:
            self._odom = {
                "x": msg.pose.pose.position.x,
                "y": msg.pose.pose.position.y,
                "linear_x": msg.twist.twist.linear.x,
                "angular_z": msg.twist.twist.angular.z,
                "updated_at": utc_now_text(),
            }

    def _on_patrol_status(self, msg: String) -> None:
        with self._lock:
            self._patrol = parse_json(msg.data)

    def _on_mission_log(self, msg: String) -> None:
        payload = parse_json(msg.data)
        self._append_log(str(payload.get("level", "info")), str(payload.get("message", msg.data)))

    def _status_payload(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "mission": dict(self._mission),
                "cameras": dict(self._cameras),
                "battery": dict(self._battery),
                "odom": dict(self._odom),
                "pump_state": self._pump_state,
                "patrol": dict(self._patrol),
                "teleop": {
                    "vx": self._teleop_target["vx"],
                    "vz": self._teleop_target["vz"],
                    "active": time.monotonic() - self._last_teleop_input <= self.teleop_timeout_sec,
                },
                "system": self._system_payload(),
                "maps": list_maps(self.runtime_root),
                "logs": list(self._logs),
                "updated_at": utc_now_text(),
            }

    def _apply_cmd_vel(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        vx = clamp(float(payload.get("vx", 0.0)), -0.4, 0.4)
        vz = clamp(float(payload.get("vz", 0.0)), -1.5, 1.5)
        self._teleop_target = {"vx": vx, "vz": vz}
        self._last_teleop_input = time.monotonic()
        self._teleop_zero_sent = False
        return {"vx": vx, "vz": vz}

    def _stop_teleop(self) -> Dict[str, Any]:
        self._teleop_target = {"vx": 0.0, "vz": 0.0}
        self._last_teleop_input = 0.0
        self._publish_zero()
        self._teleop_zero_sent = True
        return {"stopped": True}

    def _publish_mission_command(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        self._publish_json_topic(self.mission_cmd_pub, payload)
        self._append_log("info", f"任务命令: {payload.get('command', '')}")
        return {"published": True, "payload": payload}

    def _publish_fire_command(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        self._publish_json_topic(self.fire_cmd_pub, payload)
        self._append_log("warning", f"火情命令: active={payload.get('active')}")
        return {"published": True, "payload": payload}

    def _save_map(self, map_id: str) -> Dict[str, Any]:
        safe_map_id = sanitize_map_id(map_id)
        target_dir = map_dir(self.runtime_root, safe_map_id)
        target_dir.mkdir(parents=True, exist_ok=True)
        prefix = target_dir / "map"
        result = subprocess.run(
            ["ros2", "run", "nav2_map_server", "map_saver_cli", "-f", str(prefix)],
            cwd=str(repo_root()),
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "map_saver_cli 执行失败")
        self._publish_json_topic(
            self.mission_cmd_pub,
            {"command": "map_saved", "map_id": safe_map_id, "detail": f"地图 {safe_map_id} 已保存"},
        )
        self._append_log("info", f"地图已保存: {safe_map_id}")
        return {
            "map_id": safe_map_id,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }

    def _save_annotations(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        map_id = sanitize_map_id(str(payload.get("map_id", "")))
        annotations = save_annotations(self.runtime_root, map_id, payload.get("annotations", {}))
        keepout = draw_keepout_mask(self.runtime_root, map_id, annotations)
        self._append_log("info", f"地图标注已保存: {map_id}")
        return {"map_id": map_id, "annotations": annotations, "keepout": keepout}

    def _serve_file(self, path: Path, handler: BaseHTTPRequestHandler) -> None:
        if not path.exists():
            handler.send_error(HTTPStatus.NOT_FOUND, "file not found")
            return
        mime_type, _ = mimetypes.guess_type(path.name)
        content_type = mime_type or "application/octet-stream"
        data = path.read_bytes()
        handler.send_response(HTTPStatus.OK)
        handler.send_header("Content-Type", content_type)
        handler.send_header("Content-Length", str(len(data)))
        handler.end_headers()
        handler.wfile.write(data)

    def _serve_generated_png(self, generator, map_id: str, handler: BaseHTTPRequestHandler) -> None:
        try:
            data = generator(self.runtime_root, map_id)
        except FileNotFoundError:
            handler.send_error(HTTPStatus.NOT_FOUND, "map asset not found")
            return
        except Exception as exc:  # noqa: BLE001
            self.get_logger().error(f"生成地图 PNG 失败: {exc}")
            handler.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))
            return

        handler.send_response(HTTPStatus.OK)
        handler.send_header("Content-Type", "image/png")
        handler.send_header("Cache-Control", "no-cache")
        handler.send_header("Content-Length", str(len(data)))
        handler.end_headers()
        handler.wfile.write(data)

    def _start_http_server(self) -> None:
        node = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args) -> None:  # noqa: A003
                node.get_logger().debug(f"{self.address_string()} - {format % args}")

            def _read_json(self) -> Dict[str, Any]:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0:
                    return {}
                return parse_json(self.rfile.read(length).decode("utf-8"))

            def _send_json(self, payload: Dict[str, Any], status: int = HTTPStatus.OK) -> None:
                data = json_dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self) -> None:  # noqa: N802
                parsed = urlparse(self.path)
                path = parsed.path
                if path in {"/", "/index.html"}:
                    node._serve_file(node.web_root / "index.html", self)
                    return
                if path == "/app.js":
                    node._serve_file(node.web_root / "app.js", self)
                    return
                if path == "/styles.css":
                    node._serve_file(node.web_root / "styles.css", self)
                    return
                if path == "/api/status":
                    self._send_json(node._status_payload())
                    return
                if path == "/api/maps":
                    self._send_json({"maps": list_maps(node.runtime_root)})
                    return
                parts = [item for item in path.strip("/").split("/") if item]
                if len(parts) == 4 and parts[:2] == ["api", "maps"] and parts[3] == "annotations":
                    self._send_json(load_annotations(node.runtime_root, parts[2]))
                    return
                if len(parts) == 4 and parts[:2] == ["api", "maps"] and parts[3] == "map":
                    node._serve_generated_png(map_png_bytes, parts[2], self)
                    return
                if len(parts) == 4 and parts[:2] == ["api", "maps"] and parts[3] == "keepout":
                    node._serve_generated_png(keepout_png_bytes, parts[2], self)
                    return
                self.send_error(HTTPStatus.NOT_FOUND, "unknown path")

            def do_POST(self) -> None:  # noqa: N802
                payload = self._read_json()
                try:
                    if self.path == "/api/cmd_vel":
                        self._send_json(node._apply_cmd_vel(payload))
                        return
                    if self.path == "/api/stop":
                        self._send_json(node._stop_teleop())
                        return
                    if self.path == "/api/pump":
                        enabled = bool(payload.get("enabled", False))
                        node._publish_pump(enabled)
                        node._append_log("info", f"泵控制 -> {enabled}")
                        self._send_json({"enabled": enabled})
                        return
                    if self.path == "/api/fire":
                        self._send_json(node._publish_fire_command(payload))
                        return
                    if self.path == "/api/mission":
                        self._send_json(node._publish_mission_command(payload))
                        return
                    if self.path == "/api/maps/save":
                        self._send_json(node._save_map(str(payload.get("map_id", "map_default"))))
                        return
                    if self.path == "/api/maps/annotations":
                        self._send_json(node._save_annotations(payload))
                        return
                except Exception as exc:  # noqa: BLE001
                    node.get_logger().error(f"HTTP 接口处理失败: {exc}")
                    self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
                    return
                self.send_error(HTTPStatus.NOT_FOUND, "unknown path")

        self._http_server = _ThreadingHTTPServer((self.bind_host, self.bind_port), Handler)
        thread = threading.Thread(target=self._http_server.serve_forever, daemon=True)
        thread.start()
        self.get_logger().info(f"广播中心面板: http://127.0.0.1:{self.bind_port}/")


def main() -> None:
    rclpy.init()
    node = BroadcastCenterServer()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
