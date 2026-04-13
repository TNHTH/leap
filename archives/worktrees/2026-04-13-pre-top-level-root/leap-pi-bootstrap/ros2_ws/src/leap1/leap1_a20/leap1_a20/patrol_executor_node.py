from __future__ import annotations

from typing import Dict, List

import rclpy
from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateThroughPoses
from rclpy.action import ActionClient
from rclpy.node import Node
from std_msgs.msg import String

from leap1_a20_interfaces.msg import MissionState

from .common import (
    MISSION_COMMAND_TOPIC,
    MISSION_STATE_TOPIC,
    PATROL_STATUS_TOPIC,
    json_dumps,
    parse_json,
    quaternion_from_yaw,
    utc_now_text,
)
from .map_tools import load_annotations, load_map_meta, pixel_to_world
from .paths import ensure_runtime_layout


class PatrolExecutorNode(Node):
    """基于 Nav2 NavigateThroughPoses 的最小巡航执行器。"""

    def __init__(self) -> None:
        super().__init__("patrol_executor_node")
        self.declare_parameter("runtime_root", "")
        self.runtime_root = ensure_runtime_layout(str(self.get_parameter("runtime_root").value))

        self.command_pub = self.create_publisher(String, MISSION_COMMAND_TOPIC, 10)
        self.status_pub = self.create_publisher(String, PATROL_STATUS_TOPIC, 10)
        self.create_subscription(String, MISSION_COMMAND_TOPIC, self._on_command, 10)
        self.create_subscription(MissionState, MISSION_STATE_TOPIC, self._on_mission_state, 10)
        self.action_client = ActionClient(self, NavigateThroughPoses, "navigate_through_poses")

        self._active_map_id = ""
        self._active_route_id = ""
        self._loop_mode = False
        self._goal_handle = None
        self._active_poses: List[PoseStamped] = []
        self._mission_state = "IDLE"

        self.create_timer(1.0, self._publish_status)

    def _publish_status(self, message: str = "") -> None:
        payload = String()
        payload.data = json_dumps(
            {
                "map_id": self._active_map_id,
                "route_id": self._active_route_id,
                "loop_mode": self._loop_mode,
                "active": self._goal_handle is not None,
                "mission_state": self._mission_state,
                "message": message,
                "updated_at": utc_now_text(),
            }
        )
        self.status_pub.publish(payload)

    def _emit_command(self, command: str, **kwargs) -> None:
        payload = {"command": command}
        payload.update(kwargs)
        msg = String()
        msg.data = json_dumps(payload)
        self.command_pub.publish(msg)

    def _on_mission_state(self, msg: MissionState) -> None:
        state = msg.state
        if state:
            self._mission_state = state
        if state in {"FIRE_ALERT", "STOPPING", "SPRAYING", "COOLDOWN", "FAULT"}:
            self._cancel_goal("状态机要求中止巡航")

    def _on_command(self, msg: String) -> None:
        payload = parse_json(msg.data)
        command = str(payload.get("command", ""))
        if command == "start_patrol":
            map_id = str(payload.get("map_id", ""))
            route_id = str(payload.get("route_id", ""))
            patrol_mode = str(payload.get("mode", "single_run"))
            self._start_patrol(map_id, route_id, patrol_mode == "loop")
        elif command == "stop_patrol":
            self._cancel_goal("收到 stop_patrol 命令")

    def _build_poses(self, map_id: str, route_id: str) -> List[PoseStamped]:
        annotations = load_annotations(self.runtime_root, map_id)
        meta = load_map_meta(self.runtime_root, map_id)

        routes = annotations.get("routes", [])
        route = None
        for item in routes:
            if item.get("id") == route_id or item.get("name") == route_id:
                route = item
                break
        if route is None and routes:
            route = routes[0]
        if route is None:
            raise RuntimeError("当前地图还没有可执行的 route。")

        waypoint_map: Dict[str, Dict] = {
            str(item.get("id")): item for item in annotations.get("waypoints", [])
        }
        poses: List[PoseStamped] = []
        for waypoint_id in route.get("waypoint_ids", []):
            waypoint = waypoint_map.get(str(waypoint_id))
            if waypoint is None:
                raise RuntimeError(f"route 中引用了不存在的 waypoint: {waypoint_id}")
            pixel = waypoint.get("pixel", {})
            world_x, world_y = pixel_to_world(meta, float(pixel["x"]), float(pixel["y"]))
            pose = PoseStamped()
            pose.header.frame_id = "map"
            pose.header.stamp = self.get_clock().now().to_msg()
            pose.pose.position.x = world_x
            pose.pose.position.y = world_y
            pose.pose.position.z = 0.0
            quat = quaternion_from_yaw(float(waypoint.get("yaw", 0.0)))
            pose.pose.orientation.x = quat["x"]
            pose.pose.orientation.y = quat["y"]
            pose.pose.orientation.z = quat["z"]
            pose.pose.orientation.w = quat["w"]
            poses.append(pose)

        if not poses:
            raise RuntimeError("route 为空，无法执行巡航。")

        self._active_route_id = str(route.get("id", route_id))
        return poses

    def _start_patrol(self, map_id: str, route_id: str, loop_mode: bool) -> None:
        self._cancel_goal("收到新的巡航任务，先清理旧目标")
        try:
            self._active_map_id = map_id
            self._active_poses = self._build_poses(map_id, route_id)
            self._loop_mode = loop_mode
        except Exception as exc:  # noqa: BLE001
            self.get_logger().error(f"巡航准备失败: {exc}")
            self._emit_command("patrol_failed", detail=str(exc))
            self._publish_status(message=str(exc))
            return

        if not self.action_client.wait_for_server(timeout_sec=3.0):
            message = "NavigateThroughPoses action server 未就绪"
            self.get_logger().error(message)
            self._emit_command("patrol_failed", detail=message)
            self._publish_status(message=message)
            return

        goal_msg = NavigateThroughPoses.Goal()
        goal_msg.poses = self._active_poses
        self.get_logger().info(
            f"开始执行巡航 route={self._active_route_id} poses={len(self._active_poses)} loop={self._loop_mode}"
        )
        future = self.action_client.send_goal_async(goal_msg)
        future.add_done_callback(self._on_goal_response)
        self._publish_status(message="巡航目标已下发")

    def _on_goal_response(self, future) -> None:
        goal_handle = future.result()
        if goal_handle is None or not goal_handle.accepted:
            message = "Nav2 拒绝了当前巡航目标"
            self.get_logger().error(message)
            self._emit_command("patrol_failed", detail=message)
            self._publish_status(message=message)
            return

        self._goal_handle = goal_handle
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self._on_goal_result)
        self._publish_status(message="巡航目标已被 Nav2 接收")

    def _on_goal_result(self, future) -> None:
        self._goal_handle = None
        result = future.result()
        if result is None:
            message = "巡航结果为空"
            self._emit_command("patrol_failed", detail=message)
            self._publish_status(message=message)
            return

        status = result.status
        if status == GoalStatus.STATUS_SUCCEEDED:
            message = "巡航完成"
            self.get_logger().info(message)
            self._publish_status(message=message)
            if self._loop_mode and self._mission_state == "PATROLLING":
                self._start_patrol(self._active_map_id, self._active_route_id, True)
                return
            self._emit_command(
                "patrol_completed",
                map_id=self._active_map_id,
                route_id=self._active_route_id,
                detail=message,
            )
            return

        if status == GoalStatus.STATUS_CANCELED:
            self._publish_status(message="巡航已取消")
            return

        message = f"巡航失败，Nav2 status={status}"
        self.get_logger().error(message)
        self._emit_command("patrol_failed", detail=message)
        self._publish_status(message=message)

    def _cancel_goal(self, reason: str) -> None:
        if self._goal_handle is None:
            return
        self.get_logger().warning(f"取消当前巡航: {reason}")
        self._goal_handle.cancel_goal_async()
        self._goal_handle = None
        self._publish_status(message=reason)


def main() -> None:
    rclpy.init()
    node = PatrolExecutorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
