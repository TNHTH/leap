import os

from ament_index_python.packages import get_package_share_directory
from launch.conditions import IfCondition
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
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch_ros.actions import Node


DOCKER_IMAGE = 'registry.cn-hangzhou.aliyuncs.com/fishros/micro-ros-agent:humble'
MICRO_ROS_PORT = '8888'
LIDAR_UDP_PORT = '8889'
LIDAR_LINK = '/tmp/lidar'


def generate_launch_description():
    backend = LaunchConfiguration('backend')
    with_mapping = LaunchConfiguration('with_mapping')
    with_navigation = LaunchConfiguration('with_navigation')
    with_rviz = LaunchConfiguration('with_rviz')
    gui = LaunchConfiguration('gui')
    world = LaunchConfiguration('world')
    use_sim_time = PythonExpression(["'", backend, "' == 'sim'"])
    mapping_enabled = PythonExpression(["'", with_mapping, "' == 'true' or '", with_navigation, "' == 'true'"])

    xuegecar_bringup_dir = get_package_share_directory('xuegecar_bringup')
    xuegecar_navigation_dir = get_package_share_directory('xuegecar_navigation2')
    xuegecar_gazebo_dir = get_package_share_directory('xuegecar_gazebo')
    ydlidar_dir = get_package_share_directory('ydlidar_ros2_driver')
    slam_gmapping_dir = get_package_share_directory('slam_gmapping')
    ydlidar_params = os.path.join(xuegecar_bringup_dir, 'config', 'ydlidar_udp_bridge.yaml')
    nav2_rviz = os.path.join(xuegecar_navigation_dir, 'rviz', 'fishbot_navigation2.rviz')

    agent_process = ExecuteProcess(
        condition=IfCondition(PythonExpression(["'", backend, "' == 'real'"])),
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
        condition=IfCondition(PythonExpression(["'", backend, "' == 'real'"])),
        cmd=[
            'bash',
            '-lc',
            'socat -d -d PTY,link='
            + LIDAR_LINK
            + ',raw,echo=0,mode=666 UDP4-LISTEN:'
            + LIDAR_UDP_PORT
            + ',reuseaddr,fork',
        ],
        output='screen',
    )

    real_bringup_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(xuegecar_bringup_dir, 'launch', 'xuegecar_bringup.launch.py')
        ),
        condition=IfCondition(PythonExpression(["'", backend, "' == 'real'"])),
        launch_arguments={
            'use_joint_state_publisher': 'false',
            'use_sim_time': 'false',
        }.items(),
    )

    sim_tf_broadcaster = Node(
        package='xuegecar_bringup',
        executable='xuegecar_bringup',
        name='xuegecar_bringup',
        output='screen',
        condition=IfCondition(PythonExpression(["'", backend, "' == 'sim'"])),
        parameters=[{'use_sim_time': True}],
    )

    ydlidar_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(ydlidar_dir, 'launch', 'ydlidar_launch.py')
        ),
        condition=IfCondition(PythonExpression(["'", backend, "' == 'real'"])),
        launch_arguments={'params_file': ydlidar_params}.items(),
    )

    gazebo_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(xuegecar_gazebo_dir, 'launch', 'gazebo_sim.launch.py')
        ),
        condition=IfCondition(PythonExpression(["'", backend, "' == 'sim'"])),
        launch_arguments={
            'world': world,
            'gui': gui,
            'use_sim_time': use_sim_time,
        }.items(),
    )

    slam_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(slam_gmapping_dir, 'launch', 'slam_gmapping.launch.py')
        ),
        condition=IfCondition(mapping_enabled),
        launch_arguments={'use_sim_time': use_sim_time}.items(),
    )

    navigation_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(xuegecar_navigation_dir, 'launch', 'gmapping_navigation.launch.py')
        ),
        condition=IfCondition(with_navigation),
        launch_arguments={'use_sim_time': use_sim_time}.items(),
    )

    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        arguments=['-d', nav2_rviz],
        output='screen',
        parameters=[{'use_sim_time': use_sim_time}],
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
        DeclareLaunchArgument('backend', default_value='real', description='sim 或 real'),
        DeclareLaunchArgument('with_mapping', default_value='false', description='是否同时启动 gmapping'),
        DeclareLaunchArgument('with_navigation', default_value='false', description='是否同时启动 Nav2 在线导航'),
        DeclareLaunchArgument('with_rviz', default_value='false', description='是否同时启动 RViz2'),
        DeclareLaunchArgument('gui', default_value='false', description='仿真模式是否启动 Gazebo GUI'),
        DeclareLaunchArgument(
            'world',
            default_value=os.path.join(xuegecar_gazebo_dir, 'worlds', 'leap1_room.world'),
            description='Gazebo Classic world 路径',
        ),
        agent_process,
        lidar_bridge_process,
        gazebo_launch,
        TimerAction(period=2.0, actions=[ydlidar_launch, real_bringup_launch, sim_tf_broadcaster]),
        TimerAction(period=4.0, actions=[slam_launch, navigation_launch, rviz_node]),
        *critical_shutdown_actions,
    ])
