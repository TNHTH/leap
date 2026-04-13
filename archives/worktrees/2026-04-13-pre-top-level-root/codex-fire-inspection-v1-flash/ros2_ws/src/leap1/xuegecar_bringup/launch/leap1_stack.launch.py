import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.actions import EmitEvent
from launch.actions import ExecuteProcess
from launch.actions import IncludeLaunchDescription
from launch.actions import LogInfo
from launch.actions import RegisterEventHandler
from launch.actions import TimerAction
from launch.conditions import IfCondition
from launch.event_handlers import OnProcessExit
from launch.events import Shutdown
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch.substitutions import PythonExpression
from launch_ros.actions import Node


DOCKER_IMAGE = 'registry.cn-hangzhou.aliyuncs.com/fishros/micro-ros-agent:humble'


def generate_launch_description():
    with_mapping = LaunchConfiguration('with_mapping')
    with_rviz = LaunchConfiguration('with_rviz')
    agent_transport = LaunchConfiguration('agent_transport')
    agent_port = LaunchConfiguration('agent_port')
    serial_device = LaunchConfiguration('serial_device')
    serial_baud = LaunchConfiguration('serial_baud')
    agent_verbosity = LaunchConfiguration('agent_verbosity')
    lidar_udp_port = LaunchConfiguration('lidar_udp_port')
    lidar_link = LaunchConfiguration('lidar_link')

    xuegecar_bringup_dir = get_package_share_directory('xuegecar_bringup')
    ydlidar_dir = get_package_share_directory('ydlidar_ros2_driver')
    slam_gmapping_dir = get_package_share_directory('slam_gmapping')
    ydlidar_params = os.path.join(xuegecar_bringup_dir, 'config', 'ydlidar_udp_bridge.yaml')

    # Keep legacy UDP mode on Docker while allowing fire mode to switch to native serial.
    udp_agent_process = ExecuteProcess(
        cmd=[
            'bash',
            '-lc',
            [
                "sg docker -c 'docker run --rm -v /dev:/dev -v /dev/shm:/dev/shm --privileged --net=host ",
                DOCKER_IMAGE,
                ' udp4 --port ',
                agent_port,
                " -v6'",
            ],
        ],
        output='screen',
        condition=IfCondition(PythonExpression(["'", agent_transport, "' == 'udp4'"])),
    )

    serial_agent_process = ExecuteProcess(
        cmd=[
            'ros2',
            'run',
            'micro_ros_agent',
            'micro_ros_agent',
            'serial',
            '--dev',
            serial_device,
            '-b',
            serial_baud,
            '-v',
            agent_verbosity,
        ],
        output='screen',
        condition=IfCondition(PythonExpression(["'", agent_transport, "' == 'serial'"])),
    )

    lidar_bridge_process = ExecuteProcess(
        cmd=[
            'bash',
            '-lc',
            [
                'socat -d -d PTY,link=',
                lidar_link,
                ',raw,echo=0,mode=666 UDP4-LISTEN:',
                lidar_udp_port,
                ',reuseaddr,fork',
            ],
        ],
        output='screen',
    )

    bringup_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(xuegecar_bringup_dir, 'launch', 'xuegecar_bringup.launch.py'))
    )

    ydlidar_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(ydlidar_dir, 'launch', 'ydlidar_launch.py')),
        launch_arguments={'params_file': ydlidar_params}.items(),
    )

    slam_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(slam_gmapping_dir, 'launch', 'slam_gmapping.launch.py')),
        condition=IfCondition(with_mapping),
    )

    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='screen',
        condition=IfCondition(with_rviz),
    )

    critical_shutdown_actions = [
        RegisterEventHandler(
            OnProcessExit(
                target_action=udp_agent_process,
                on_exit=[
                    LogInfo(msg='micro-ROS UDP agent exited, shutting down launch.'),
                    EmitEvent(event=Shutdown(reason='micro-ROS UDP agent exited')),
                ],
            )
        ),
        RegisterEventHandler(
            OnProcessExit(
                target_action=serial_agent_process,
                on_exit=[
                    LogInfo(msg='micro-ROS serial agent exited, shutting down launch.'),
                    EmitEvent(event=Shutdown(reason='micro-ROS serial agent exited')),
                ],
            )
        ),
        RegisterEventHandler(
            OnProcessExit(
                target_action=lidar_bridge_process,
                on_exit=[
                    LogInfo(msg='lidar UDP bridge exited, shutting down launch.'),
                    EmitEvent(event=Shutdown(reason='lidar bridge exited')),
                ],
            )
        ),
    ]

    return LaunchDescription(
        [
            DeclareLaunchArgument('with_mapping', default_value='false', description='Launch gmapping if true'),
            DeclareLaunchArgument('with_rviz', default_value='false', description='Launch RViz2 if true'),
            DeclareLaunchArgument('agent_transport', default_value='udp4', description='micro-ROS agent transport: udp4 or serial'),
            DeclareLaunchArgument('agent_port', default_value='8888', description='UDP micro-ROS agent port'),
            DeclareLaunchArgument('serial_device', default_value='/dev/ttyACM0', description='USB serial device for the ESP32'),
            DeclareLaunchArgument('serial_baud', default_value='921600', description='micro-ROS serial baud rate'),
            DeclareLaunchArgument('agent_verbosity', default_value='6', description='micro-ROS agent verbosity'),
            DeclareLaunchArgument('lidar_udp_port', default_value='8889', description='UDP port forwarded from ESP32 lidar bridge'),
            DeclareLaunchArgument('lidar_link', default_value='/tmp/lidar', description='PTY path for lidar UDP bridge'),
            udp_agent_process,
            serial_agent_process,
            lidar_bridge_process,
            TimerAction(period=2.0, actions=[ydlidar_launch, bringup_launch]),
            TimerAction(period=4.0, actions=[slam_launch, rviz_node]),
            *critical_shutdown_actions,
        ]
    )
