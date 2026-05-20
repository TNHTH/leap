import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    package_name = 'xuegecar_description'
    urdf_name = "xuegecar.urdf"
    use_joint_state_publisher = LaunchConfiguration('use_joint_state_publisher')
    use_sim_time = LaunchConfiguration('use_sim_time')

    ld = LaunchDescription()
    pkg_share = FindPackageShare(package=package_name).find(package_name)
    urdf_model_path = os.path.join(pkg_share, f'urdf/{urdf_name}')

    ld.add_action(DeclareLaunchArgument('use_joint_state_publisher', default_value='false'))
    ld.add_action(DeclareLaunchArgument('use_sim_time', default_value='false'))

    robot_state_publisher_node = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        arguments=[urdf_model_path],
        parameters=[{'use_sim_time': use_sim_time}],
        output='screen',
    )

    joint_state_publisher_node = Node(
        package='joint_state_publisher',
        executable='joint_state_publisher',
        name='joint_state_publisher',
        arguments=[urdf_model_path],
        output='screen',
        parameters=[{'use_sim_time': use_sim_time}],
        condition=IfCondition(use_joint_state_publisher),
    )

    xuegecar_bringup = Node(
        package='xuegecar_bringup',
        executable='xuegecar_bringup',
        name='xuegecar_bringup',
        output='screen',
        parameters=[{'use_sim_time': use_sim_time}],
    )

    ld.add_action(joint_state_publisher_node)
    ld.add_action(robot_state_publisher_node)
    ld.add_action(xuegecar_bringup)

    return ld
