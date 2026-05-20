from __future__ import annotations

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from std_srvs.srv import SetBool, Trigger

from leap1_a20_interfaces.msg import FireEvent

from .common import FIRE_COMMAND_TOPIC, FIRE_EVENT_TOPIC, now_stamp, parse_json


class FireEventPlaceholderNode(Node):
    """人工火情占位节点，后续可无缝替换为真实视觉检测。"""

    def __init__(self) -> None:
        super().__init__("fire_event_placeholder_node")
        self.publisher = self.create_publisher(FireEvent, FIRE_EVENT_TOPIC, 10)
        self.subscription = self.create_subscription(String, FIRE_COMMAND_TOPIC, self._on_fire_command, 10)
        self.set_active_srv = self.create_service(SetBool, "~/set_active", self._handle_set_active)
        self.clear_srv = self.create_service(Trigger, "~/clear", self._handle_clear)
        self._last_event = FireEvent()
        self._last_event.stamp = now_stamp(self)
        self._last_event.active = False
        self._last_event.source = "placeholder"
        self._last_event.camera_id = "manual"
        self._last_event.level = "info"
        self._last_event.description = "等待人工触发"
        self.create_timer(1.0, self._republish_last_event)

    def _publish_event(
        self,
        active: bool,
        source: str = "placeholder",
        camera_id: str = "manual",
        level: str = "warning",
        description: str = "",
    ) -> None:
        event = FireEvent()
        event.stamp = now_stamp(self)
        event.active = active
        event.source = source
        event.camera_id = camera_id
        event.level = level
        event.description = description or ("手动触发火情" if active else "手动清除火情")
        self._last_event = event
        self.publisher.publish(event)
        self.get_logger().info(
            f"火情占位事件已发布: active={event.active} source={event.source} desc={event.description}"
        )

    def _republish_last_event(self) -> None:
        self.publisher.publish(self._last_event)

    def _on_fire_command(self, msg: String) -> None:
        payload = parse_json(msg.data)
        self._publish_event(
            active=bool(payload.get("active", False)),
            source=str(payload.get("source", "web_panel")),
            camera_id=str(payload.get("camera_id", "manual")),
            level=str(payload.get("level", "warning")),
            description=str(payload.get("description", "")),
        )

    def _handle_set_active(self, request: SetBool.Request, response: SetBool.Response) -> SetBool.Response:
        self._publish_event(active=request.data, source="service", camera_id="manual", description="")
        response.success = True
        response.message = "火情状态已更新"
        return response

    def _handle_clear(self, request: Trigger.Request, response: Trigger.Response) -> Trigger.Response:
        del request
        self._publish_event(active=False, source="service", camera_id="manual", description="手动清除火情")
        response.success = True
        response.message = "火情已清除"
        return response


def main() -> None:
    rclpy.init()
    node = FireEventPlaceholderNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
