from __future__ import annotations

import mimetypes
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Callable, Dict
from urllib.parse import urlparse

from .common import json_dumps, parse_json
from .http_utils import ReusableThreadingHTTPServer
from .map_tools import keepout_png_bytes, list_maps, load_annotations, map_png_bytes


class BroadcastCenterHttpServer:
    """封装广播中心 HTTP 路由，避免 ROS 节点类堆积 Web 细节。"""

    def __init__(self, node) -> None:
        self.node = node
        self.server = ReusableThreadingHTTPServer(
            (node.bind_host, node.bind_port),
            self._handler_class(),
        )
        self.thread: threading.Thread | None = None
        self._started = False

    def start(self) -> None:
        if self._started:
            return
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self._started = True
        self.node.get_logger().info(f"广播中心面板: http://127.0.0.1:{self.node.bind_port}/")

    def stop(self) -> None:
        if self._started:
            self.server.shutdown()
            if self.thread is not None:
                self.thread.join(timeout=2.0)
            self._started = False
        self.server.server_close()

    def serve_file(self, path: Path, handler: BaseHTTPRequestHandler) -> None:
        if not path.exists():
            handler.send_error(HTTPStatus.NOT_FOUND, "file not found")
            return
        data = path.read_bytes()
        mime_type, _ = mimetypes.guess_type(path.name)
        handler.send_response(HTTPStatus.OK)
        handler.send_header("Content-Type", mime_type or "application/octet-stream")
        handler.send_header("Content-Length", str(len(data)))
        handler.end_headers()
        handler.wfile.write(data)

    def serve_generated_png(
        self,
        generator: Callable[[Path, str], bytes],
        map_id: str,
        handler: BaseHTTPRequestHandler,
    ) -> None:
        try:
            data = generator(self.node.runtime_root, map_id)
        except FileNotFoundError:
            handler.send_error(HTTPStatus.NOT_FOUND, "map asset not found")
            return
        except Exception as exc:  # noqa: BLE001
            self.node.get_logger().error(f"生成地图 PNG 失败: {exc}")
            handler.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))
            return

        handler.send_response(HTTPStatus.OK)
        handler.send_header("Content-Type", "image/png")
        handler.send_header("Cache-Control", "no-cache")
        handler.send_header("Content-Length", str(len(data)))
        handler.end_headers()
        handler.wfile.write(data)

    def _handler_class(self):
        owner = self
        node = self.node

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args) -> None:  # noqa: A003
                node.get_logger().debug(f"{self.address_string()} - {format % args}")

            def _read_json(self) -> Dict[str, Any]:
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                except (TypeError, ValueError) as exc:
                    raise ValueError("invalid Content-Length") from exc
                if length < 0:
                    raise ValueError("invalid Content-Length")
                if length <= 0:
                    return {}
                try:
                    return parse_json(self.rfile.read(length).decode("utf-8"))
                except UnicodeDecodeError as exc:
                    raise ValueError("request body must be utf-8") from exc

            def _send_json(self, payload: Dict[str, Any], status: int = HTTPStatus.OK) -> None:
                data = json_dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self) -> None:  # noqa: N802
                if self._handle_static_get():
                    return
                if self._handle_api_get():
                    return
                self.send_error(HTTPStatus.NOT_FOUND, "unknown path")

            def do_POST(self) -> None:  # noqa: N802
                try:
                    payload = self._read_json()
                    if self._handle_control_post(payload):
                        return
                    if self._handle_map_post(payload):
                        return
                except ValueError as exc:
                    node.get_logger().warning(f"HTTP 请求体无效: {exc}")
                    self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                    return
                except Exception as exc:  # noqa: BLE001
                    node.get_logger().error(f"HTTP 接口处理失败: {exc}")
                    self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
                    return
                self.send_error(HTTPStatus.NOT_FOUND, "unknown path")

            def _handle_static_get(self) -> bool:
                path = urlparse(self.path).path
                if path == "/favicon.ico":
                    self.send_response(HTTPStatus.NO_CONTENT)
                    self.end_headers()
                    return True
                static_files = {
                    "/": "index.html",
                    "/index.html": "index.html",
                    "/app.js": "app.js",
                    "/styles.css": "styles.css",
                }
                if path in static_files:
                    owner.serve_file(node.web_root / static_files[path], self)
                    return True
                return False

            def _handle_api_get(self) -> bool:
                path = urlparse(self.path).path
                if path == "/api/status":
                    self._send_json(node._status_payload())
                    return True
                if path == "/api/test-report-summary":
                    self._send_json(node._test_report_summary_payload())
                    return True
                if path == "/api/maps":
                    self._send_json({"maps": list_maps(node.runtime_root)})
                    return True
                return self._handle_map_asset_get(path)

            def _handle_map_asset_get(self, path: str) -> bool:
                parts = [item for item in path.strip("/").split("/") if item]
                if len(parts) != 4 or parts[:2] != ["api", "maps"]:
                    return False
                if parts[3] == "annotations":
                    self._send_json(load_annotations(node.runtime_root, parts[2]))
                    return True
                if parts[3] == "map":
                    owner.serve_generated_png(map_png_bytes, parts[2], self)
                    return True
                if parts[3] == "keepout":
                    owner.serve_generated_png(keepout_png_bytes, parts[2], self)
                    return True
                return False

            def _handle_control_post(self, payload: Dict[str, Any]) -> bool:
                if self.path == "/api/cmd_vel":
                    self._send_json(node._apply_cmd_vel(payload))
                    return True
                if self.path == "/api/stop":
                    self._send_json(node._stop_teleop())
                    return True
                if self.path == "/api/pump":
                    result = node._handle_pump_request(payload)
                    status = HTTPStatus.OK if result.get("ok", True) else HTTPStatus.FORBIDDEN
                    self._send_json(result, status=status)
                    return True
                if self.path == "/api/fire":
                    self._send_json(node._publish_fire_command(payload))
                    return True
                if self.path == "/api/mission":
                    self._send_json(node._publish_mission_command(payload))
                    return True
                return False

            def _handle_map_post(self, payload: Dict[str, Any]) -> bool:
                if self.path == "/api/maps/save":
                    if node._panel_is_status_only():
                        self._send_json(
                            {"ok": False, "error": "status_only 模式禁止保存地图"},
                            status=HTTPStatus.FORBIDDEN,
                        )
                        return True
                    self._send_json(node._save_map(str(payload.get("map_id", "map_default"))))
                    return True
                if self.path == "/api/runtime/mapping/start":
                    self._send_json(node._start_mapping_workbench())
                    return True
                if self.path == "/api/runtime/patrol/ensure_remote":
                    self._send_json(node._ensure_remote_patrol_mode())
                    return True
                if self.path == "/api/maps/annotations":
                    if node._panel_is_status_only():
                        self._send_json(
                            {"ok": False, "error": "status_only 模式禁止修改地图标注"},
                            status=HTTPStatus.FORBIDDEN,
                        )
                        return True
                    self._send_json(node._save_annotations(payload))
                    return True
                return False

        return Handler
