#!/usr/bin/env python3
"""Leap 小车水泵控制工具。

支持两种控制后端：
1. http: 直接访问小车网页接口 `/pump`
2. ros: 通过 ROS 2 话题 `/pump_cmd`

推荐用法：
  ./run_leap1_pump.sh --backend http --host 192.168.5.7 --pulse 2.0
  ./run_leap1_pump.sh --backend ros --pulse 1.5
  ./run_leap1_pump.sh --backend http --on
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_HOST = "192.168.5.7"
DEFAULT_TOPIC = "/pump_cmd"
DEFAULT_INTERVAL = 0.5


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Leap 小车水泵控制工具")
    parser.add_argument(
        "--backend",
        choices=("http", "ros"),
        default="http",
        help="控制后端，默认 http",
    )
    parser.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help=f"http 后端的小车 IP，默认 {DEFAULT_HOST}",
    )
    parser.add_argument(
        "--topic",
        default=DEFAULT_TOPIC,
        help=f"ros 后端的话题名，默认 {DEFAULT_TOPIC}",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=DEFAULT_INTERVAL,
        help=f"保活发送周期，单位秒，默认 {DEFAULT_INTERVAL}",
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--on", action="store_true", help="持续抽水，直到 Ctrl+C")
    group.add_argument("--off", action="store_true", help="关闭抽水")
    group.add_argument("--pulse", type=float, help="抽水指定秒数后自动关闭")
    return parser.parse_args()


def bash_ros_command(topic: str, enabled: bool) -> list[str]:
    payload = "{data: true}" if enabled else "{data: false}"
    command = (
        "source /opt/ros/humble/setup.bash >/dev/null 2>&1 && "
        f"ros2 topic pub --once {topic} std_msgs/msg/Bool '{payload}' >/dev/null"
    )
    return ["bash", "-lc", command]


def send_ros_command(topic: str, enabled: bool) -> None:
    subprocess.run(bash_ros_command(topic, enabled), check=True, cwd=REPO_ROOT)


def send_http_command(host: str, enabled: bool) -> None:
    url = f"http://{host}/pump?enabled={1 if enabled else 0}"
    with urllib.request.urlopen(url, timeout=2.5) as response:
        response.read()


def send_command(args: argparse.Namespace, enabled: bool) -> None:
    if args.backend == "http":
        send_http_command(args.host, enabled)
        return
    send_ros_command(args.topic, enabled)


def keep_pumping(args: argparse.Namespace, duration: float | None) -> None:
    start_time = time.monotonic()
    send_command(args, True)
    try:
        while True:
            time.sleep(args.interval)
            if duration is not None and (time.monotonic() - start_time) >= duration:
                break
            send_command(args, True)
    finally:
        send_command(args, False)


def main() -> int:
    args = parse_args()
    try:
        if args.off:
            send_command(args, False)
            print("已发送关泵命令")
            return 0

        if args.on:
            print("开始持续抽水，按 Ctrl+C 停止")
            keep_pumping(args, None)
            return 0

        assert args.pulse is not None
        if args.pulse <= 0:
            raise ValueError("--pulse 必须大于 0")
        print(f"开始抽水 {args.pulse:.2f} 秒")
        keep_pumping(args, args.pulse)
        print("抽水完成，已自动关闭")
        return 0
    except KeyboardInterrupt:
        print("\n收到中断，已关闭抽水")
        return 130
    except (subprocess.CalledProcessError, urllib.error.URLError, TimeoutError, ValueError) as exc:
        print(f"抽水命令执行失败: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
