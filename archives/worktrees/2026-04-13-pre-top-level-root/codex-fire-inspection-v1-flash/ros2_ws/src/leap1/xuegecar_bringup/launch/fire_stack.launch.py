import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.actions import IncludeLaunchDescription
from launch.actions import TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    bringup_dir = get_package_share_directory('xuegecar_bringup')
    navigation_dir = get_package_share_directory('xuegecar_navigation2')
    fire_dir = get_package_share_directory('xuegecar_fire_inspection')

    with_mapping = LaunchConfiguration('with_mapping')
    with_rviz = LaunchConfiguration('with_rviz')
    serial_device = LaunchConfiguration('serial_device')
    serial_baud = LaunchConfiguration('serial_baud')
    agent_verbosity = LaunchConfiguration('agent_verbosity')
    nav_map = LaunchConfiguration('map')
    nav_params = LaunchConfiguration('nav2_params_file')
    fire_params = LaunchConfiguration('fire_params_file')

    default_map = os.path.join(navigation_dir, 'maps', 'room.yaml')
    default_nav_params = os.path.join(navigation_dir, 'param', 'xuegebot.yaml')
    default_fire_params = os.path.join(bringup_dir, 'config', 'fire_inspection.yaml')

    leap_stack_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(bringup_dir, 'launch', 'leap1_stack.launch.py')),
        launch_arguments={
            'with_mapping': with_mapping,
            'with_rviz': 'false',
            'agent_transport': 'serial',
            'serial_device': serial_device,
            'serial_baud': serial_baud,
            'agent_verbosity': agent_verbosity,
        }.items(),
    )

    navigation_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(navigation_dir, 'launch', 'navigation2.launch.py')),
        launch_arguments={
            'with_rviz': with_rviz,
            'map': nav_map,
            'params_file': nav_params,
        }.items(),
    )

    fire_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(fire_dir, 'launch', 'xuegecar_fire_inspection.launch.py')),
        launch_arguments={
            'params_file': fire_params,
        }.items(),
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument('with_mapping', default_value='false', description='Launch mapping alongside fire mode.'),
            DeclareLaunchArgument('with_rviz', default_value='false', description='Launch RViz for Nav2.'),
            DeclareLaunchArgument('serial_device', default_value='/dev/ttyACM0', description='USB serial device for the ESP32 base controller.'),
            DeclareLaunchArgument('serial_baud', default_value='921600', description='micro-ROS serial baud rate.'),
            DeclareLaunchArgument('agent_verbosity', default_value='6', description='micro-ROS agent verbosity.'),
            DeclareLaunchArgument('map', default_value=default_map, description='Nav2 map yaml path.'),
            DeclareLaunchArgument('nav2_params_file', default_value=default_nav_params, description='Nav2 parameter file.'),
            DeclareLaunchArgument(
                'fire_params_file',
                default_value=default_fire_params,
                description='Fire inspection parameter file.',
            ),
            leap_stack_launch,
            TimerAction(period=5.0, actions=[navigation_launch]),
            TimerAction(period=7.0, actions=[fire_launch]),
        ]
    )
