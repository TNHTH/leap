import os

from ament_index_python.packages import PackageNotFoundError, get_package_share_directory
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


def _optional_package_share(package_name: str) -> str:
    try:
        return get_package_share_directory(package_name)
    except PackageNotFoundError:
        return ""


def generate_launch_description():
    backend = LaunchConfiguration('backend')
    agent_transport = LaunchConfiguration('agent_transport')
    agent_serial_dev = LaunchConfiguration('agent_serial_dev')
    agent_serial_baud = LaunchConfiguration('agent_serial_baud')
    with_mapping = LaunchConfiguration('with_mapping')
    with_navigation = LaunchConfiguration('with_navigation')
    with_rviz = LaunchConfiguration('with_rviz')
    with_keepout_filter = LaunchConfiguration('with_keepout_filter')
    keepout_mask_yaml = LaunchConfiguration('keepout_mask_yaml')
    with_vehicle_web_teleop = LaunchConfiguration('with_vehicle_web_teleop')
    with_a20_stack = LaunchConfiguration('with_a20_stack')
    with_vehicle_camera = LaunchConfiguration('with_vehicle_camera')
    with_ground_camera = LaunchConfiguration('with_ground_camera')
    vehicle_camera_device = LaunchConfiguration('vehicle_camera_device')
    ground_camera_device = LaunchConfiguration('ground_camera_device')
    a20_runtime_root = LaunchConfiguration('a20_runtime_root')
    a20_web_port = LaunchConfiguration('a20_web_port')
    front_camera_port = LaunchConfiguration('front_camera_port')
    ground_camera_port = LaunchConfiguration('ground_camera_port')
    gui = LaunchConfiguration('gui')
    world = LaunchConfiguration('world')
    use_sim_time = PythonExpression(["'", backend, "' == 'sim'"])
    mapping_enabled = PythonExpression(
        ["'", with_mapping, "' == 'true' or '", with_navigation, "' == 'true'"]
    )
    a20_enabled = PythonExpression(
        [
            "'",
            with_a20_stack,
            "' == 'true' or '",
            with_vehicle_web_teleop,
            "' == 'true'",
        ]
    )

    xuegecar_bringup_dir = get_package_share_directory('xuegecar_bringup')
    leap1_a20_dir = get_package_share_directory('leap1_a20')
    xuegecar_navigation_dir = get_package_share_directory('xuegecar_navigation2')
    xuegecar_gazebo_dir = _optional_package_share('xuegecar_gazebo')
    ydlidar_dir = get_package_share_directory('ydlidar_ros2_driver')
    slam_gmapping_dir = get_package_share_directory('slam_gmapping')
    lidar_link = os.environ.get('LEAP1_LIDAR_LINK', DEFAULT_LIDAR_LINK)
    ydlidar_params = _prepare_ydlidar_params(
        os.path.join(xuegecar_bringup_dir, 'config', 'ydlidar_udp_bridge.yaml'),
        lidar_link,
    )
    nav2_rviz = os.path.join(xuegecar_navigation_dir, 'rviz', 'fishbot_navigation2.rviz')
    default_world = (
        os.path.join(xuegecar_gazebo_dir, 'worlds', 'leap1_room.world')
        if xuegecar_gazebo_dir
        else ''
    )

    udp_agent_process = ExecuteProcess(
        condition=IfCondition(
            PythonExpression(["'", backend, "' == 'real' and '", agent_transport, "' == 'udp'"])
        ),
        cmd=[
            'bash',
            '-lc',
            (
                "sg docker -c 'docker run --rm -v /dev:/dev -v /dev/shm:/dev/shm "
                "--privileged --net=host "
                + DOCKER_IMAGE
                + " udp4 --port "
                + MICRO_ROS_PORT
                + " -v6'"
            ),
        ],
        output='screen',
    )

    serial_agent_process = ExecuteProcess(
        condition=IfCondition(
            PythonExpression(["'", backend, "' == 'real' and '", agent_transport, "' == 'serial'"])
        ),
        cmd=[
            'bash',
            '-lc',
            [
                (
                    "sg docker -c 'docker run --rm -v /dev:/dev -v /dev/shm:/dev/shm "
                    "--privileged --net=host "
                ),
                DOCKER_IMAGE,
                " serial --dev ",
                agent_serial_dev,
                " -b ",
                agent_serial_baud,
                " -v6'",
            ],
        ],
        output='screen',
    )

    lidar_bridge_process = ExecuteProcess(
        condition=IfCondition(PythonExpression(["'", backend, "' == 'real'"])),
        cmd=[
            'bash',
            '-lc',
            'socat -u UDP4-RECV:'
            + LIDAR_UDP_PORT
            + ',reuseaddr PTY,link='
            + lidar_link
            + ',raw,echo=0,mode=666',
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
        launch_arguments={
            'use_sim_time': use_sim_time,
            'with_keepout_filter': with_keepout_filter,
            'keepout_mask_yaml': keepout_mask_yaml,
        }.items(),
    )

    a20_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(leap1_a20_dir, 'launch', 'a20_vehicle.launch.py')
        ),
        condition=IfCondition(a20_enabled),
        launch_arguments={
            'runtime_root': a20_runtime_root,
            'with_web_panel': with_vehicle_web_teleop,
            'with_vehicle_camera': with_vehicle_camera,
            'with_ground_camera': with_ground_camera,
            'vehicle_camera_device': vehicle_camera_device,
            'ground_camera_device': ground_camera_device,
            'web_bind_port': a20_web_port,
            'front_camera_port': front_camera_port,
            'ground_camera_port': ground_camera_port,
        }.items(),
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
                target_action=udp_agent_process,
                on_exit=[
                    LogInfo(msg='micro-ROS Agent 已退出，正在关闭整套 Launch。'),
                    EmitEvent(event=Shutdown(reason='micro-ROS Agent exited')),
                ],
            )
        ),
        RegisterEventHandler(
            OnProcessExit(
                target_action=serial_agent_process,
                on_exit=[
                    LogInfo(msg='serial micro-ROS Agent 已退出，正在关闭整套 Launch。'),
                    EmitEvent(event=Shutdown(reason='serial micro-ROS Agent exited')),
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
        DeclareLaunchArgument(
            'agent_transport',
            default_value='udp',
            description='udp、serial、external_serial 或 none',
        ),
        DeclareLaunchArgument(
            'agent_serial_dev',
            default_value='/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0',
            description='serial micro-ROS 设备路径',
        ),
        DeclareLaunchArgument(
            'agent_serial_baud',
            default_value='921600',
            description='serial micro-ROS 波特率',
        ),
        DeclareLaunchArgument(
            'with_mapping',
            default_value='false',
            description='是否同时启动 gmapping',
        ),
        DeclareLaunchArgument(
            'with_navigation',
            default_value='false',
            description='是否同时启动 Nav2 在线导航',
        ),
        DeclareLaunchArgument('with_rviz', default_value='false', description='是否同时启动 RViz2'),
        DeclareLaunchArgument(
            'with_keepout_filter',
            default_value='false',
            description='是否启用 Nav2 keepout filter',
        ),
        DeclareLaunchArgument(
            'keepout_mask_yaml',
            default_value='',
            description='keepout mask yaml 路径',
        ),
        DeclareLaunchArgument(
            'with_vehicle_web_teleop',
            default_value='false',
            description='是否启用 Web Teleop / 广播中心',
        ),
        DeclareLaunchArgument(
            'with_a20_stack',
            default_value='false',
            description='是否启用 A20 状态机与地图标注栈',
        ),
        DeclareLaunchArgument(
            'with_vehicle_camera',
            default_value='false',
            description='是否启动车载相机节点',
        ),
        DeclareLaunchArgument(
            'with_ground_camera',
            default_value='true',
            description='是否启用固定摄像头占位节点',
        ),
        DeclareLaunchArgument(
            'vehicle_camera_device',
            default_value='/dev/video0',
            description='车载相机设备路径',
        ),
        DeclareLaunchArgument('ground_camera_device', default_value='', description='固定摄像头设备路径'),
        DeclareLaunchArgument('a20_runtime_root', default_value='', description='A20 运行时目录'),
        DeclareLaunchArgument('a20_web_port', default_value='8090', description='A20 Web 端口'),
        DeclareLaunchArgument(
            'front_camera_port',
            default_value='8091',
            description='车载相机 MJPEG 端口',
        ),
        DeclareLaunchArgument(
            'ground_camera_port',
            default_value='8092',
            description='固定摄像头 MJPEG 端口',
        ),
        DeclareLaunchArgument('gui', default_value='false', description='仿真模式是否启动 Gazebo GUI'),
        DeclareLaunchArgument(
            'world',
            default_value=default_world,
            description='Gazebo Classic world 路径',
        ),
        udp_agent_process,
        serial_agent_process,
        lidar_bridge_process,
        gazebo_launch,
        TimerAction(period=2.0, actions=[ydlidar_launch, real_bringup_launch, sim_tf_broadcaster]),
        TimerAction(period=4.0, actions=[slam_launch, navigation_launch, rviz_node]),
        TimerAction(period=5.0, actions=[a20_launch]),
        LogInfo(
            condition=IfCondition(
                PythonExpression(
                    ["'", backend, "' == 'real' and '", agent_transport, "' == 'external_serial'"]
                )
            ),
            msg='当前使用外部 serial micro-ROS agent，由 systemd 或独立进程托管。',
        ),
        *critical_shutdown_actions,
    ])
