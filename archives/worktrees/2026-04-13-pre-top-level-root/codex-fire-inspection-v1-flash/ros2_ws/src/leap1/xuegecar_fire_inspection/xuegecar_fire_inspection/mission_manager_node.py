from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2
import rclpy
from action_msgs.msg import GoalStatus
from cv_bridge import CvBridge
from geometry_msgs.msg import Twist
from nav2_msgs.action import FollowWaypoints
from rclpy.action import ActionClient
from rclpy.duration import Duration
from rclpy.node import Node
from rclpy.task import Future
from sensor_msgs.msg import Image
from std_msgs.msg import Bool, String

from .common import build_waypoints, ensure_directory


class MissionManagerNode(Node):
    def __init__(self):
        super().__init__('mission_manager_node')
        self.bridge = CvBridge()

        self.declare_parameter('image_topic', '/camera/image_raw')
        self.declare_parameter('fire_detected_topic', '/fire_detected')
        self.declare_parameter('inspection_state_topic', '/inspection_state')
        self.declare_parameter('pump_cmd_topic', '/pump_cmd')
        self.declare_parameter('cmd_vel_topic', '/cmd_vel')
        self.declare_parameter('follow_waypoints_action', '/follow_waypoints')
        self.declare_parameter('global_frame', 'map')
        self.declare_parameter('heartbeat_hz', 2.0)
        self.declare_parameter('record_fps', 10.0)
        self.declare_parameter('record_directory', '/tmp/leap1_fire_recordings')
        self.declare_parameter('required_fire_state', True)
        self.declare_parameter('spray_duration_sec', 5.0)
        self.declare_parameter('cooldown_sec', 8.0)
        self.declare_parameter('stop_publish_count', 8)
        self.declare_parameter('waypoints_x', [0.0])
        self.declare_parameter('waypoints_y', [0.0])
        self.declare_parameter('waypoints_yaw_deg', [0.0])

        self.inspection_state_publisher = self.create_publisher(
            String, self.get_parameter('inspection_state_topic').value, 10
        )
        self.pump_publisher = self.create_publisher(Bool, self.get_parameter('pump_cmd_topic').value, 10)
        self.cmd_vel_publisher = self.create_publisher(Twist, self.get_parameter('cmd_vel_topic').value, 10)

        self.create_subscription(Image, self.get_parameter('image_topic').value, self._image_callback, 10)
        self.create_subscription(Bool, self.get_parameter('fire_detected_topic').value, self._fire_callback, 10)

        self.follow_waypoints_client = ActionClient(
            self,
            FollowWaypoints,
            self.get_parameter('follow_waypoints_action').value,
        )

        xs = self.get_parameter('waypoints_x').value
        ys = self.get_parameter('waypoints_y').value
        yaws = self.get_parameter('waypoints_yaw_deg').value
        if not (len(xs) == len(ys) == len(yaws) and len(xs) > 0):
            raise ValueError('waypoints_x, waypoints_y, and waypoints_yaw_deg must be non-empty and equal length.')
        self._waypoints = build_waypoints(self.get_parameter('global_frame').value, xs, ys, yaws)

        self._state = 'idle'
        self._fire_detected = False
        self._latest_frame = None
        self._video_writer: Optional[cv2.VideoWriter] = None
        self._record_path: Optional[Path] = None
        self._spray_deadline = None
        self._cooldown_deadline = None
        self._goal_handle = None
        self._current_waypoint_index = 0
        self._active_waypoint_offset = 0
        self._pending_cancel_for_fire = False
        self._waiting_for_server_logged = False

        heartbeat_hz = max(float(self.get_parameter('heartbeat_hz').value), 1.0)
        record_fps = max(float(self.get_parameter('record_fps').value), 1.0)
        self.create_timer(1.0 / heartbeat_hz, self._heartbeat_tick)
        self.create_timer(1.0 / record_fps, self._record_tick)
        self.create_timer(0.2, self._state_machine_tick)

        self._publish_pump(False)
        self._set_state('idle')

    def _image_callback(self, msg: Image):
        self._latest_frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')

    def _fire_callback(self, msg: Bool):
        expected_state = bool(self.get_parameter('required_fire_state').value)
        self._fire_detected = (msg.data == expected_state)
        if self._fire_detected and self._state in ('idle', 'patrolling'):
            self._pending_cancel_for_fire = True
            self._cancel_patrol_goal()

    def _heartbeat_tick(self):
        self.inspection_state_publisher.publish(String(data=self._state))
        if self._state == 'spraying':
            self._publish_pump(True)

    def _state_machine_tick(self):
        now = self.get_clock().now()

        if self._state == 'idle' and not self._fire_detected:
            self._start_patrol_if_possible()
            return

        if self._state == 'spraying':
            if self._spray_deadline is not None and (now >= self._spray_deadline or not self._fire_detected):
                self._stop_spraying()
                cooldown_sec = float(self.get_parameter('cooldown_sec').value)
                self._cooldown_deadline = now + Duration(seconds=cooldown_sec)
                self._set_state('cooldown')
        elif self._state == 'cooldown':
            if self._cooldown_deadline is not None and now >= self._cooldown_deadline:
                if self._fire_detected:
                    self._start_spraying()
                else:
                    self._start_patrol_if_possible()

    def _record_tick(self):
        if self._state != 'spraying' or self._latest_frame is None:
            return
        if self._video_writer is None:
            self._open_video_writer(self._latest_frame)
        if self._video_writer is not None:
            self._video_writer.write(self._latest_frame)

    def _start_patrol_if_possible(self):
        if self._fire_detected:
            return
        if not self.follow_waypoints_client.wait_for_server(timeout_sec=0.1):
            if not self._waiting_for_server_logged:
                self.get_logger().warning('Waiting for FollowWaypoints action server.')
                self._waiting_for_server_logged = True
            return
        self._waiting_for_server_logged = False
        self._send_patrol_goal(self._current_waypoint_index)

    def _send_patrol_goal(self, start_index: int):
        goal = FollowWaypoints.Goal()
        self._active_waypoint_offset = start_index
        goal.poses = self._waypoints[start_index:] or self._waypoints
        if not self._waypoints[start_index:]:
            self._active_waypoint_offset = 0
            self._current_waypoint_index = 0
        stamp = self.get_clock().now().to_msg()
        for pose in goal.poses:
            pose.header.stamp = stamp
        self._set_state('patrolling')
        future = self.follow_waypoints_client.send_goal_async(goal, feedback_callback=self._feedback_callback)
        future.add_done_callback(self._goal_response_callback)

    def _goal_response_callback(self, future: Future):
        goal_handle = future.result()
        if goal_handle is None or not goal_handle.accepted:
            self.get_logger().error('FollowWaypoints goal rejected.')
            self._set_state('idle')
            return
        self._goal_handle = goal_handle
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self._goal_result_callback)

    def _goal_result_callback(self, future: Future):
        result = future.result()
        self._goal_handle = None
        if result is None:
            self._set_state('idle')
            return

        status = result.status
        if status == GoalStatus.STATUS_SUCCEEDED:
            self._current_waypoint_index = 0
            if self._state == 'patrolling' and not self._fire_detected:
                self._send_patrol_goal(0)
        elif status == GoalStatus.STATUS_CANCELED:
            self.get_logger().info('Patrol goal canceled.')
        else:
            self.get_logger().warning(f'Patrol goal finished with status {status}.')
            self._set_state('idle')

    def _feedback_callback(self, feedback_msg):
        self._current_waypoint_index = self._active_waypoint_offset + int(feedback_msg.feedback.current_waypoint)

    def _cancel_patrol_goal(self):
        if self._goal_handle is None:
            self._pending_cancel_for_fire = False
            self._publish_stop()
            self._start_spraying()
            return
        future = self._goal_handle.cancel_goal_async()
        future.add_done_callback(self._cancel_done_callback)

    def _cancel_done_callback(self, _future: Future):
        self._goal_handle = None
        if self._pending_cancel_for_fire:
            self._publish_stop()
            self._start_spraying()
            self._pending_cancel_for_fire = False

    def _start_spraying(self):
        if self._state == 'spraying':
            return
        spray_duration = float(self.get_parameter('spray_duration_sec').value)
        self._spray_deadline = self.get_clock().now() + Duration(seconds=spray_duration)
        self._cooldown_deadline = None
        self._publish_stop()
        self._publish_pump(True)
        self._set_state('spraying')

    def _stop_spraying(self):
        self._publish_pump(False)
        self._publish_stop()
        self._close_video_writer()

    def _publish_stop(self):
        stop_count = int(self.get_parameter('stop_publish_count').value)
        stop = Twist()
        for _ in range(stop_count):
            self.cmd_vel_publisher.publish(stop)

    def _publish_pump(self, enabled: bool):
        self.pump_publisher.publish(Bool(data=enabled))

    def _set_state(self, state: str):
        self._state = state
        self.inspection_state_publisher.publish(String(data=state))

    def _open_video_writer(self, frame):
        directory = ensure_directory(self.get_parameter('record_directory').value)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self._record_path = directory / f'fire_event_{timestamp}.avi'
        height, width = frame.shape[:2]
        fps = max(float(self.get_parameter('record_fps').value), 1.0)
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        self._video_writer = cv2.VideoWriter(str(self._record_path), fourcc, fps, (width, height))

    def _close_video_writer(self):
        if self._video_writer is not None:
            self._video_writer.release()
            self._video_writer = None
        self._record_path = None

    def destroy_node(self):
        self._publish_pump(False)
        self._publish_stop()
        self._close_video_writer()
        return super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = MissionManagerNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
