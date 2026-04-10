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
from launch_ros.actions import Node


DOCKER_IMAGE = 'registry.cn-hangzhou.aliyuncs.com/fishros/micro-ros-agent:humble'
MICRO_ROS_PORT = '8888'
LIDAR_UDP_PORT = '8889'
DEFAULT_LIDAR_LINK = '/tmp/lidar'


def _prepare_ydlidar_params(template_path: str, lidar_link: str) -> str:
    generated_dir = os.path.join('/tmp', 'leap1')
    generated_path = os.path.join(generated_dir, 'ydlidar_udp_bridge.generated.yaml')

    os.makedirs(generated_dir, exist_ok=True)
    with open(template_path, 'r', encoding='utf-8') as src_file:
        content = src_file.read()
    with open(generated_path, 'w', encoding='utf-8') as dst_file:
        dst_file.write(content.replace(f'port: {DEFAULT_LIDAR_LINK}', f'port: {lidar_link}', 1))

    return generated_path


def generate_launch_description():
    with_mapping = LaunchConfiguration('with_mapping')
    with_rviz = LaunchConfiguration('with_rviz')

    xuegecar_bringup_dir = get_package_share_directory('xuegecar_bringup')
    ydlidar_dir = get_package_share_directory('ydlidar_ros2_driver')
    slam_gmapping_dir = get_package_share_directory('slam_gmapping')
    lidar_link = os.environ.get('LEAP1_LIDAR_LINK', DEFAULT_LIDAR_LINK)
    ydlidar_params = _prepare_ydlidar_params(
        os.path.join(xuegecar_bringup_dir, 'config', 'ydlidar_udp_bridge.yaml'),
        lidar_link,
    )

    agent_process = ExecuteProcess(
        cmd=[
            'bash',
            '-lc',
            "sg docker -c 'docker run --rm -v /dev:/dev -v /dev/shm:/dev/shm --privileged --net=host "
            + DOCKER_IMAGE
            + " udp4 --port "
            + MICRO_ROS_PORT
            + " -v6'",
        ],
        output='screen',
    )

    lidar_bridge_process = ExecuteProcess(
        cmd=[
            'bash',
            '-lc',
            'socat -d -d PTY,link='
            + lidar_link
            + ',raw,echo=0,mode=666 UDP4-LISTEN:'
            + LIDAR_UDP_PORT
            + ',reuseaddr,fork',
        ],
        output='screen',
    )

    bringup_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(xuegecar_bringup_dir, 'launch', 'xuegecar_bringup.launch.py')
        )
    )

    ydlidar_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(ydlidar_dir, 'launch', 'ydlidar_launch.py')
        ),
        launch_arguments={'params_file': ydlidar_params}.items(),
    )

    slam_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(slam_gmapping_dir, 'launch', 'slam_gmapping.launch.py')
        ),
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
                target_action=agent_process,
                on_exit=[
                    LogInfo(msg='micro-ROS Agent 已退出，正在关闭整套 Launch。'),
                    EmitEvent(event=Shutdown(reason='micro-ROS Agent exited')),
                ],
            )
        ),
        RegisterEventHandler(
            OnProcessExit(
                target_action=lidar_bridge_process,
                on_exit=[
                    LogInfo(msg='雷达桥接已退出，正在关闭整套 Launch。'),
                    EmitEvent(event=Shutdown(reason='lidar bridge exited')),
                ],
            )
        ),
    ]

    return LaunchDescription([
        DeclareLaunchArgument('with_mapping', default_value='false', description='是否同时启动 gmapping'),
        DeclareLaunchArgument('with_rviz', default_value='false', description='是否同时启动 RViz2'),
        agent_process,
        lidar_bridge_process,
        TimerAction(period=2.0, actions=[ydlidar_launch, bringup_launch]),
        TimerAction(period=4.0, actions=[slam_launch, rviz_node]),
        *critical_shutdown_actions,
    ])
