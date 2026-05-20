#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Joy
from std_msgs.msg import Bool, String


MISSION_COMMAND_TOPIC = "/a20/mission/command"


class JoyPumpBridge(Node):
    def __init__(self, button_index: int, button_label: str, keepalive_sec: float, auth_duration_sec: float) -> None:
        super().__init__("joy_pump_bridge")
        self.button_index = button_index
        self.button_label = button_label
        self.keepalive_sec = max(0.2, keepalive_sec)
        self.auth_duration_sec = max(1.0, auth_duration_sec)
        self.active = False
        self.last_keepalive = 0.0

        self.pump_pub = self.create_publisher(Bool, "/pump_cmd", 10)
        self.command_pub = self.create_publisher(String, MISSION_COMMAND_TOPIC, 10)
        self.create_subscription(Joy, "/joy", self.on_joy, 10)
        self.create_timer(self.keepalive_sec, self.on_timer)
        self.get_logger().info(
            f"手柄泵控已启动: 按住 {self.button_label} button={self.button_index} 抽水，松开停止"
        )

    def publish_pump(self, enabled: bool) -> None:
        msg = Bool()
        msg.data = enabled
        self.pump_pub.publish(msg)

    def publish_authorization(self) -> None:
        msg = String()
        msg.data = json.dumps(
            {
                "command": "authorized_pump_test",
                "duration_sec": max(2.0, self.auth_duration_sec),
                "detail": f"手柄按钮 {self.button_label} 按住抽水",
            },
            ensure_ascii=False,
        )
        self.command_pub.publish(msg)

    def set_active(self, active: bool) -> None:
        if active == self.active:
            return
        self.active = active
        if active:
            self.publish_authorization()
            self.publish_pump(True)
            self.last_keepalive = time.monotonic()
            self.get_logger().info(f"{self.button_label} 按下，开始抽水")
        else:
            self.publish_pump(False)
            self.get_logger().info(f"{self.button_label} 松开，停止抽水")

    def on_joy(self, msg: Joy) -> None:
        pressed = False
        if 0 <= self.button_index < len(msg.buttons):
            pressed = bool(msg.buttons[self.button_index])
        self.set_active(pressed)

    def on_timer(self) -> None:
        if not self.active:
            return
        now = time.monotonic()
        if now - self.last_keepalive < self.keepalive_sec:
            return
        self.publish_authorization()
        self.publish_pump(True)
        self.last_keepalive = now

    def stop(self) -> None:
        self.active = False
        self.publish_pump(False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="把 /joy 按钮转换成按住抽水控制")
    parser.add_argument("--button-index", type=int, default=5)
    parser.add_argument("--button-label", default="RB")
    parser.add_argument("--keepalive-sec", type=float, default=0.4)
    parser.add_argument("--auth-duration-sec", type=float, default=1.5)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rclpy.init()
    node = JoyPumpBridge(
        button_index=args.button_index,
        button_label=args.button_label,
        keepalive_sec=args.keepalive_sec,
        auth_duration_sec=args.auth_duration_sec,
    )
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.stop()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
