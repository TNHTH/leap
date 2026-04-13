import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

def generate_launch_description():
    default_params = os.path.join(get_package_share_directory("slam_gmapping"), "params", "slam_gmapping.yaml")
    use_sim_time = LaunchConfiguration("use_sim_time")
    slam_params_file = LaunchConfiguration("slam_params_file")

    return LaunchDescription([
        DeclareLaunchArgument("use_sim_time", default_value="false"),
        DeclareLaunchArgument("slam_params_file", default_value=default_params),
        Node(
            package="slam_gmapping",
            executable="slam_gmapping",
            output="screen",
            parameters=[slam_params_file, {"use_sim_time": use_sim_time}],
        ),
    ])
