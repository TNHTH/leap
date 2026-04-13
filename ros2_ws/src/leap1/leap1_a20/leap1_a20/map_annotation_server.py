from __future__ import annotations

from typing import Any, Dict

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from .common import MAP_REQUEST_TOPIC, MAP_RESPONSE_TOPIC, json_dumps, parse_json, utc_now_text
from .map_tools import draw_keepout_mask, list_maps, load_annotations, save_annotations
from .paths import ensure_runtime_layout


class MapAnnotationServer(Node):
    """地图标注服务节点，负责落盘标注与 keepout mask 生成。"""

    def __init__(self) -> None:
        super().__init__("map_annotation_server")
        self.declare_parameter("runtime_root", "")
        self.runtime_root = ensure_runtime_layout(str(self.get_parameter("runtime_root").value))
        self.response_pub = self.create_publisher(String, MAP_RESPONSE_TOPIC, 10)
        self.subscription = self.create_subscription(String, MAP_REQUEST_TOPIC, self._handle_request, 10)

    def _reply(self, request_id: str, command: str, ok: bool, result: Dict[str, Any] | None = None, error: str = "") -> None:
        message = String()
        message.data = json_dumps(
            {
                "request_id": request_id,
                "command": command,
                "ok": ok,
                "result": result or {},
                "error": error,
                "updated_at": utc_now_text(),
            }
        )
        self.response_pub.publish(message)

    def _handle_request(self, msg: String) -> None:
        payload = parse_json(msg.data)
        request_id = str(payload.get("request_id", ""))
        command = str(payload.get("command", ""))
        map_id = str(payload.get("map_id", ""))
        try:
            if command == "list_maps":
                self._reply(request_id, command, True, {"maps": list_maps(self.runtime_root)})
                return
            if command == "load_annotations":
                annotations = load_annotations(self.runtime_root, map_id)
                self._reply(request_id, command, True, {"annotations": annotations})
                return
            if command == "save_annotations":
                annotations = save_annotations(self.runtime_root, map_id, payload.get("annotations", {}))
                keepout = draw_keepout_mask(self.runtime_root, map_id, annotations)
                self._reply(
                    request_id,
                    command,
                    True,
                    {"annotations": annotations, "keepout": keepout},
                )
                return
            self._reply(request_id, command, False, error=f"不支持的命令: {command}")
        except Exception as exc:  # noqa: BLE001
            self.get_logger().error(f"地图标注处理失败: {exc}")
            self._reply(request_id, command, False, error=str(exc))


def main() -> None:
    rclpy.init()
    node = MapAnnotationServer()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
