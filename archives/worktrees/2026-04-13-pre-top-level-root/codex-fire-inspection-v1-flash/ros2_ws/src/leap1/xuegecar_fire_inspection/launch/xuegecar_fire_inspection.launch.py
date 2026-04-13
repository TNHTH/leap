import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.actions import EmitEvent
from launch.actions import LogInfo
from launch.actions import RegisterEventHandler
from launch.event_handlers import OnProcessExit
from launch.events import Shutdown
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    package_dir = get_package_share_directory('xuegecar_fire_inspection')
    default_config = os.path.join(package_dir, 'config', 'fire_inspection.yaml')

    params_file = LaunchConfiguration('params_file')

    camera_node = Node(
        package='xuegecar_fire_inspection',
        executable='camera_node',
        name='camera_node',
        output='screen',
        parameters=[params_file],
    )
    fire_detector_node = Node(
        package='xuegecar_fire_inspection',
        executable='fire_detector_node',
        name='fire_detector_node',
        output='screen',
        parameters=[params_file],
    )
    mission_manager_node = Node(
        package='xuegecar_fire_inspection',
        executable='mission_manager_node',
        name='mission_manager_node',
        output='screen',
        parameters=[params_file],
    )
    pump_guard_node = Node(
        package='xuegecar_fire_inspection',
        executable='pump_guard_node',
        name='pump_guard_node',
        output='screen',
        parameters=[params_file],
    )

    critical_handlers = []
    for action, label in [
        (camera_node, 'camera_node'),
        (fire_detector_node, 'fire_detector_node'),
        (mission_manager_node, 'mission_manager_node'),
        (pump_guard_node, 'pump_guard_node'),
    ]:
        critical_handlers.append(
            RegisterEventHandler(
                OnProcessExit(
                    target_action=action,
                    on_exit=[
                        LogInfo(msg=f'{label} exited, shutting down fire inspection stack.'),
                        EmitEvent(event=Shutdown(reason=f'{label} exited')),
                    ],
                )
            )
        )

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                'params_file',
                default_value=default_config,
                description='Path to the fire inspection parameter file.',
            ),
            camera_node,
            fire_detector_node,
            mission_manager_node,
            pump_guard_node,
            *critical_handlers,
        ]
    )
