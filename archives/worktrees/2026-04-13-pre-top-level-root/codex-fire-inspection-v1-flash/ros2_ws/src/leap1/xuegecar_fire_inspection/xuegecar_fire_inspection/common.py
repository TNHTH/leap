import math
from pathlib import Path
from typing import Iterable, List

from geometry_msgs.msg import PoseStamped, Quaternion


def yaw_degrees_to_quaternion(yaw_degrees: float) -> Quaternion:
    yaw = math.radians(yaw_degrees)
    quat = Quaternion()
    quat.z = math.sin(yaw / 2.0)
    quat.w = math.cos(yaw / 2.0)
    return quat


def build_waypoints(frame_id: str, xs: Iterable[float], ys: Iterable[float], yaws: Iterable[float]) -> List[PoseStamped]:
    waypoints: List[PoseStamped] = []
    for x, y, yaw in zip(xs, ys, yaws):
        pose = PoseStamped()
        pose.header.frame_id = frame_id
        pose.pose.position.x = float(x)
        pose.pose.position.y = float(y)
        pose.pose.orientation = yaw_degrees_to_quaternion(float(yaw))
        waypoints.append(pose)
    return waypoints


def ensure_directory(path: str) -> Path:
    directory = Path(path).expanduser()
    directory.mkdir(parents=True, exist_ok=True)
    return directory
