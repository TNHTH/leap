#include <cmath>
#include <functional>
#include <memory>
#include <string>

#include <geometry_msgs/msg/transform_stamped.hpp>
#include <nav_msgs/msg/odometry.hpp>
#include <rclcpp/rclcpp.hpp>
#include <tf2_ros/transform_broadcaster.h>

class OdomTfBroadcaster : public rclcpp::Node
{
public:
  OdomTfBroadcaster()
  : Node("leap1_odom_tf_broadcaster")
  {
    odom_topic_ = declare_parameter<std::string>("odom_topic", "odom");
    odom_frame_ = declare_parameter<std::string>("odom_frame", "odom");
    base_frame_ = declare_parameter<std::string>("base_frame", "base_footprint");
    publish_tf_ = declare_parameter<bool>("publish_tf", true);

    tf_broadcaster_ = std::make_unique<tf2_ros::TransformBroadcaster>(*this);
    odom_subscription_ = create_subscription<nav_msgs::msg::Odometry>(
      odom_topic_,
      rclcpp::SensorDataQoS(),
      std::bind(&OdomTfBroadcaster::odom_callback, this, std::placeholders::_1));
  }

private:
  void odom_callback(const nav_msgs::msg::Odometry::SharedPtr msg)
  {
    if (!publish_tf_) {
      return;
    }

    auto transform = to_transform(*msg);
    tf_broadcaster_->sendTransform(transform);
  }

  geometry_msgs::msg::TransformStamped to_transform(const nav_msgs::msg::Odometry & odom_msg)
  {
    geometry_msgs::msg::TransformStamped transform;
    transform.header.stamp = odom_msg.header.stamp;
    transform.header.frame_id = odom_frame_;
    transform.child_frame_id = base_frame_;
    transform.transform.translation.x = odom_msg.pose.pose.position.x;
    transform.transform.translation.y = odom_msg.pose.pose.position.y;
    transform.transform.translation.z = odom_msg.pose.pose.position.z;
    transform.transform.rotation = normalized_orientation(odom_msg);
    return transform;
  }

  geometry_msgs::msg::Quaternion normalized_orientation(const nav_msgs::msg::Odometry & odom_msg)
  {
    auto orientation = odom_msg.pose.pose.orientation;
    const double norm_squared =
      orientation.x * orientation.x +
      orientation.y * orientation.y +
      orientation.z * orientation.z +
      orientation.w * orientation.w;

    if (!std::isfinite(norm_squared) || norm_squared < 1e-12) {
      RCLCPP_WARN_THROTTLE(
        get_logger(), *get_clock(), 2000,
        "odom orientation is invalid; publish identity quaternion");
      orientation.x = 0.0;
      orientation.y = 0.0;
      orientation.z = 0.0;
      orientation.w = 1.0;
      return orientation;
    }

    const double norm = std::sqrt(norm_squared);
    orientation.x /= norm;
    orientation.y /= norm;
    orientation.z /= norm;
    orientation.w /= norm;
    return orientation;
  }

  std::string odom_topic_;
  std::string odom_frame_;
  std::string base_frame_;
  bool publish_tf_ = true;
  rclcpp::Subscription<nav_msgs::msg::Odometry>::SharedPtr odom_subscription_;
  std::unique_ptr<tf2_ros::TransformBroadcaster> tf_broadcaster_;
};

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<OdomTfBroadcaster>());
  rclcpp::shutdown();
  return 0;
}
