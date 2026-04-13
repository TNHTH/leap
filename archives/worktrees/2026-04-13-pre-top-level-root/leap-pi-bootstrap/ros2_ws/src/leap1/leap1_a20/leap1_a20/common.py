import json
import math
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

MISSION_COMMAND_TOPIC = "/a20/mission/command"
MISSION_STATE_TOPIC = "/a20/mission/state"
MISSION_LOG_TOPIC = "/a20/mission/log"
FIRE_EVENT_TOPIC = "/a20/fire_event"
FIRE_COMMAND_TOPIC = "/a20/fire_command"
MAP_REQUEST_TOPIC = "/a20/map/request"
MAP_RESPONSE_TOPIC = "/a20/map/response"
PATROL_STATUS_TOPIC = "/a20/patrol/status"
CAMERA_STATUS_TOPIC = "/a20/camera/status"


def now_stamp(node) -> Time:
    return node.get_clock().now().to_msg()


def utc_now_text() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def json_dumps(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


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
