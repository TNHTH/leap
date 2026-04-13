import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from std_msgs.msg import Bool, String


class PumpGuardNode(Node):
    def __init__(self):
        super().__init__('pump_guard_node')
        self.declare_parameter('pump_cmd_topic', '/pump_cmd')
        self.declare_parameter('inspection_state_topic', '/inspection_state')
        self.declare_parameter('cmd_vel_topic', '/cmd_vel')
        self.declare_parameter('manager_timeout_sec', 3.0)
        self.declare_parameter('guard_publish_period_sec', 0.5)

        self._manager_timeout_sec = float(self.get_parameter('manager_timeout_sec').value)
        self._last_heartbeat = self.get_clock().now()
        self.publisher = self.create_publisher(Bool, self.get_parameter('pump_cmd_topic').value, 10)
        self.cmd_vel_publisher = self.create_publisher(Twist, self.get_parameter('cmd_vel_topic').value, 10)
        self.create_subscription(
            String,
            self.get_parameter('inspection_state_topic').value,
            self._heartbeat_callback,
            10,
        )
        self.create_timer(float(self.get_parameter('guard_publish_period_sec').value), self._guard_tick)
        self._publish_off()

    def _heartbeat_callback(self, _msg: String):
        self._last_heartbeat = self.get_clock().now()

    def _guard_tick(self):
        elapsed = (self.get_clock().now() - self._last_heartbeat).nanoseconds / 1e9
        if elapsed >= self._manager_timeout_sec:
            self._publish_off()

    def _publish_off(self):
        self.publisher.publish(Bool(data=False))
        self.cmd_vel_publisher.publish(Twist())

    def destroy_node(self):
        self._publish_off()
        return super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = PumpGuardNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
