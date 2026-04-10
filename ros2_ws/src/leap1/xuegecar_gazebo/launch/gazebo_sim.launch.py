import os

from ament_index_python.packages import get_package_prefix, get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, TimerAction
from launch.conditions import IfCondition, UnlessCondition
from launch.substitutions import Command, LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    pkg_share = get_package_share_directory("xuegecar_gazebo")
    gazebo_ros_prefix = get_package_prefix("gazebo_ros")

    world = LaunchConfiguration("world")
    gui = LaunchConfiguration("gui")
    use_sim_time = LaunchConfiguration("use_sim_time")

    default_world = os.path.join(pkg_share, "worlds", "leap1_room.world")
    urdf_path = os.path.join(pkg_share, "urdf", "xuegecar_gazebo.urdf.xacro")
    spawn_entity_script = os.path.join(gazebo_ros_prefix, "lib", "gazebo_ros", "spawn_entity.py")
    robot_description = ParameterValue(Command(["xacro", " ", urdf_path]), value_type=str)

    gazebo_server = ExecuteProcess(
        condition=UnlessCondition(gui),
        cmd=[
            "gzserver",
            "--verbose",
            world,
            "-s",
            "libgazebo_ros_init.so",
            "-s",
            "libgazebo_ros_factory.so",
        ],
        output="screen",
    )

    gazebo_gui = ExecuteProcess(
        condition=IfCondition(gui),
        cmd=[
            "gazebo",
            "--verbose",
            world,
            "-s",
            "libgazebo_ros_init.so",
            "-s",
            "libgazebo_ros_factory.so",
        ],
        output="screen",
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument("world", default_value=default_world),
            DeclareLaunchArgument("gui", default_value="false"),
            DeclareLaunchArgument("use_sim_time", default_value="true"),
            gazebo_server,
            gazebo_gui,
            Node(
                package="robot_state_publisher",
                executable="robot_state_publisher",
                name="robot_state_publisher",
                output="screen",
                parameters=[{"use_sim_time": use_sim_time, "robot_description": robot_description}],
            ),
            TimerAction(
                period=2.0,
                actions=[
                    ExecuteProcess(
                        cmd=[
                            "/usr/bin/python3.10",
                            spawn_entity_script,
                            "-entity",
                            "leap1",
                            "-topic",
                            "robot_description",
                            "-x",
                            "0.0",
                            "-y",
                            "0.0",
                            "-z",
                            "0.08",
                        ],
                        output="screen",
                    ),
                ],
            ),
        ]
    )
