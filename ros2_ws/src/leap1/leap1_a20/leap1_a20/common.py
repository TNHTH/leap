import json
import math
import os
import time
from typing import Any, Dict

from builtin_interfaces.msg import Time


MISSION_STATES = [
    "BOOT",
    "IDLE",
    "MAPPING",
    "MAP_READY",
    "ANNOTATING",
    "MISSION_READY",
    "PATROLLING",
    "FIRE_ALERT",
    "STOPPING",
    "SPRAYING",
    "COOLDOWN",
    "FAULT",
]

def _topic_prefix() -> str:
    prefix = os.environ.get("LEAP1_A20_TOPIC_PREFIX", "/a20").strip() or "/a20"
    if not prefix.startswith("/"):
        prefix = f"/{prefix}"
    return prefix.rstrip("/")


TOPIC_PREFIX = _topic_prefix()


def scoped_topic(path: str) -> str:
    suffix = path if path.startswith("/") else f"/{path}"
    return f"{TOPIC_PREFIX}{suffix}"


def camera_image_topic(camera_name: str) -> str:
    return scoped_topic(f"/{camera_name}/image_raw")


def camera_info_topic(camera_name: str) -> str:
    return scoped_topic(f"/{camera_name}/camera_info")


MISSION_COMMAND_TOPIC = scoped_topic("/mission/command")
MISSION_STATE_TOPIC = scoped_topic("/mission/state")
MISSION_LOG_TOPIC = scoped_topic("/mission/log")
FIRE_EVENT_TOPIC = scoped_topic("/fire_event")
FIRE_COMMAND_TOPIC = scoped_topic("/fire_command")
MAP_REQUEST_TOPIC = scoped_topic("/map/request")
MAP_RESPONSE_TOPIC = scoped_topic("/map/response")
PATROL_STATUS_TOPIC = scoped_topic("/patrol/status")
CAMERA_STATUS_TOPIC = scoped_topic("/camera/status")
PERCEPTION_DETECTION_TOPIC = scoped_topic("/perception/detection")
PERCEPTION_STATUS_TOPIC = scoped_topic("/perception/status")
SAFETY_STATUS_TOPIC = scoped_topic("/safety/status")


def now_stamp(node) -> Time:
    return node.get_clock().now().to_msg()


def utc_now_text() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _sanitize_json_value(value: Any) -> Any:
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {key: _sanitize_json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_json_value(item) for item in value]
    return value


def json_dumps(payload: Dict[str, Any]) -> str:
    return json.dumps(
        _sanitize_json_value(payload),
        ensure_ascii=False,
        sort_keys=True,
        allow_nan=False,
    )


def parse_json(text: str, default: Dict[str, Any] | None = None) -> Dict[str, Any]:
    if not text:
        return default or {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return default or {}


def quaternion_from_yaw(yaw: float) -> Dict[str, float]:
    half_yaw = yaw * 0.5
    return {
        "x": 0.0,
        "y": 0.0,
        "z": math.sin(half_yaw),
        "w": math.cos(half_yaw),
    }
