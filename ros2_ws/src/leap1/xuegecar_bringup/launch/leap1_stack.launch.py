import os
from pathlib import Path

from ament_index_python.packages import PackageNotFoundError, get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.actions import EmitEvent
from launch.actions import ExecuteProcess
from launch.actions import IncludeLaunchDescription
from launch.actions import LogInfo
from launch.actions import OpaqueFunction
from launch.actions import RegisterEventHandler
from launch.actions import TimerAction
from launch.conditions import IfCondition
from launch.event_handlers import OnProcessExit
from launch.events import Shutdown
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch_ros.actions import Node


DOCKER_IMAGE = "registry.cn-hangzhou.aliyuncs.com/fishros/micro-ros-agent:humble"
MICRO_ROS_PORT = "8888"
LIDAR_UDP_PORT = "8889"
DEFAULT_LIDAR_LINK = "/tmp/lidar"


def _generated_root() -> str:
    return "/dev/shm" if os.path.isdir("/dev/shm") else "/tmp"


def _default_mapping_backend() -> str:
    return "slam_toolbox"


def _default_nav_profile() -> str:
    return "stable"


def _default_lidar_backend() -> str:
    return "ydlidar"


def _latest_runtime_map_yaml(runtime_root: str) -> str:
    if not runtime_root:
        return ""

    maps_root = Path(runtime_root) / "maps"
    if not maps_root.is_dir():
        return ""

    map_candidates = []
    for map_yaml in maps_root.glob("*/map.yaml"):
        if map_yaml.is_file():
            map_candidates.append(map_yaml)

    if not map_candidates:
        return ""

    latest_map = max(map_candidates, key=lambda path: path.stat().st_mtime)
    return str(latest_map)


def _resolve_runtime_map_yaml(runtime_root: str, explicit_map_yaml: str) -> str:
    if explicit_map_yaml:
        explicit_path = Path(explicit_map_yaml)
        if explicit_path.is_file():
            return str(explicit_path)
        return ""
    return _latest_runtime_map_yaml(runtime_root)


def _prepare_ydlidar_params(template_path: str, lidar_link: str) -> str:
    generated_dir = os.path.join(_generated_root(), "leap1")
    generated_path = os.path.join(generated_dir, "ydlidar_udp_bridge.generated.yaml")

    os.makedirs(generated_dir, exist_ok=True)
    with open(template_path, "r", encoding="utf-8") as src_file:
        content = src_file.read()
    with open(generated_path, "w", encoding="utf-8") as dst_file:
        dst_file.write(content.replace(f"port: {DEFAULT_LIDAR_LINK}", f"port: {lidar_link}", 1))

    return generated_path


def _prepare_ldlidar_params(template_path: str, lidar_link: str) -> str:
    generated_dir = os.path.join(_generated_root(), "leap1")
    generated_path = os.path.join(generated_dir, "ldlidar_ld19_udp_bridge.generated.yaml")

    os.makedirs(generated_dir, exist_ok=True)
    with open(template_path, "r", encoding="utf-8") as src_file:
        content = src_file.read()
    with open(generated_path, "w", encoding="utf-8") as dst_file:
        dst_file.write(
            content.replace(
                f"port_name: {DEFAULT_LIDAR_LINK}",
                f"port_name: {lidar_link}",
                1,
            )
        )

    return generated_path


def _optional_package_share(package_name: str) -> str:
    try:
        return get_package_share_directory(package_name)
    except PackageNotFoundError:
        return ""


def _dynamic_navigation_actions(context):
    backend = LaunchConfiguration("backend").perform(context)
    with_mapping = LaunchConfiguration("with_mapping").perform(context) == "true"
    with_navigation = LaunchConfiguration("with_navigation").perform(context) == "true"
    mapping_backend = (
        LaunchConfiguration("mapping_backend").perform(context)
        or _default_mapping_backend()
    )
    nav_profile = LaunchConfiguration("nav_profile").perform(context) or _default_nav_profile()
    lidar_backend = (
        LaunchConfiguration("lidar_backend").perform(context)
        or _default_lidar_backend()
    )
    map_yaml = LaunchConfiguration("map_yaml").perform(context)
    with_keepout_filter = LaunchConfiguration("with_keepout_filter")
    keepout_mask_yaml = LaunchConfiguration("keepout_mask_yaml")

    use_sim_time_text = "true" if backend == "sim" else "false"
    actions = []

    xuegecar_bringup_dir = get_package_share_directory("xuegecar_bringup")
    xuegecar_navigation_dir = get_package_share_directory("xuegecar_navigation2")
    ydlidar_dir = get_package_share_directory("ydlidar_ros2_driver")
    slam_gmapping_dir = get_package_share_directory("slam_gmapping")
    lidar_link = os.environ.get("LEAP1_LIDAR_LINK", DEFAULT_LIDAR_LINK)

    lidar_actions = []
    if backend == "real":
        if lidar_backend == "ldlidar_ld19":
            ldlidar_params = _prepare_ldlidar_params(
                os.path.join(xuegecar_bringup_dir, "config", "ldlidar_ld19_udp_bridge.yaml"),
                lidar_link,
            )
            lidar_actions.append(
                Node(
                    package="ldlidar_stl_ros2",
                    executable="ldlidar_stl_ros2_node",
                    name="ldlidar_ld19",
                    output="screen",
                    parameters=[ldlidar_params],
                )
            )
        else:
            ydlidar_params = _prepare_ydlidar_params(
                os.path.join(xuegecar_bringup_dir, "config", "ydlidar_x2_udp_bridge.yaml"),
                lidar_link,
            )
            lidar_actions.append(
                IncludeLaunchDescription(
                    PythonLaunchDescriptionSource(
                        os.path.join(ydlidar_dir, "launch", "ydlidar_launch.py")
                    ),
                    launch_arguments={"params_file": ydlidar_params}.items(),
                )
            )

    slam_actions = []
    needs_live_slam = with_mapping or (with_navigation and not map_yaml)
    if needs_live_slam:
        if mapping_backend == "gmapping":
            slam_actions.append(
                IncludeLaunchDescription(
                    PythonLaunchDescriptionSource(
                        os.path.join(slam_gmapping_dir, "launch", "slam_gmapping.launch.py")
                    ),
                    launch_arguments={"use_sim_time": use_sim_time_text}.items(),
                )
            )
        else:
            slam_params = os.path.join(xuegecar_bringup_dir, "config", "slam_toolbox_mapping.yaml")
            slam_executable = "async_slam_toolbox_node"
            if (not with_mapping) and with_navigation and not map_yaml:
                actions.append(
                    LogInfo(msg="未提供 map_yaml，slam_toolbox 导航回退为在线建图模式。")
                )

            slam_actions.append(
                Node(
                    package="slam_toolbox",
                    executable=slam_executable,
                    name="slam_toolbox",
                    output="screen",
                    parameters=[slam_params, {"use_sim_time": backend == "sim"}],
                )
            )

    navigation_actions = []
    if with_navigation:
        navigation_actions.append(
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    os.path.join(
                        xuegecar_navigation_dir,
                        "launch",
                        "gmapping_navigation.launch.py",
                    )
                ),
                launch_arguments={
                    "use_sim_time": use_sim_time_text,
                    "with_keepout_filter": with_keepout_filter,
                    "keepout_mask_yaml": keepout_mask_yaml,
                    "nav_profile": nav_profile,
                    "map_yaml": map_yaml,
                }.items(),
            )
        )

    if with_navigation and map_yaml:
        actions.append(LogInfo(msg="检测到静态地图，导航定位改走 map_server + AMCL。"))

    if lidar_actions:
        actions.append(TimerAction(period=2.0, actions=lidar_actions))
    if slam_actions or navigation_actions:
        actions.append(TimerAction(period=4.0, actions=slam_actions + navigation_actions))
    return actions


def generate_launch_description():
    backend = LaunchConfiguration("backend")
    agent_transport = LaunchConfiguration("agent_transport")
    agent_serial_dev = LaunchConfiguration("agent_serial_dev")
    agent_serial_baud = LaunchConfiguration("agent_serial_baud")
    with_rviz = LaunchConfiguration("with_rviz")
    with_vehicle_web_teleop = LaunchConfiguration("with_vehicle_web_teleop")
    with_a20_stack = LaunchConfiguration("with_a20_stack")
    with_vehicle_camera = LaunchConfiguration("with_vehicle_camera")
    with_ground_camera = LaunchConfiguration("with_ground_camera")
    with_manual_fire_tools = LaunchConfiguration("with_manual_fire_tools")
    with_aux_detection_placeholders = LaunchConfiguration("with_aux_detection_placeholders")
    vehicle_camera_device = LaunchConfiguration("vehicle_camera_device")
    ground_camera_device = LaunchConfiguration("ground_camera_device")
    a20_runtime_root = LaunchConfiguration("a20_runtime_root")
    a20_web_port = LaunchConfiguration("a20_web_port")
    front_camera_port = LaunchConfiguration("front_camera_port")
    ground_camera_port = LaunchConfiguration("ground_camera_port")
    center_panel_mode = LaunchConfiguration("center_panel_mode")
    gui = LaunchConfiguration("gui")
    world = LaunchConfiguration("world")
    use_sim_time = PythonExpression(["'", backend, "' == 'sim'"])
    center_console_enabled = PythonExpression(
        ["'", with_vehicle_web_teleop, "' == 'true' or '", with_ground_camera, "' == 'true'"]
    )

    xuegecar_bringup_dir = get_package_share_directory("xuegecar_bringup")
    leap1_a20_dir = get_package_share_directory("leap1_a20")
    xuegecar_navigation_dir = get_package_share_directory("xuegecar_navigation2")
    xuegecar_gazebo_dir = _optional_package_share("xuegecar_gazebo")
    nav2_rviz = os.path.join(xuegecar_navigation_dir, "rviz", "fishbot_navigation2.rviz")
    default_world = (
        os.path.join(xuegecar_gazebo_dir, "worlds", "leap1_room.world")
        if xuegecar_gazebo_dir
        else ""
    )
    default_map_yaml = _resolve_runtime_map_yaml(
        os.environ.get("LEAP1_A20_RUNTIME_ROOT", ""),
        os.environ.get("LEAP1_MAP_YAML", ""),
    )

    udp_agent_process = ExecuteProcess(
        condition=IfCondition(
            PythonExpression(["'", backend, "' == 'real' and '", agent_transport, "' == 'udp'"])
        ),
        cmd=[
            "bash",
            "-lc",
            (
                "sg docker -c 'docker run --rm -v /dev:/dev -v /dev/shm:/dev/shm "
                "--privileged --net=host "
                + DOCKER_IMAGE
                + " udp4 --port "
                + MICRO_ROS_PORT
                + " -v6'"
            ),
        ],
        output="screen",
    )

    serial_agent_process = ExecuteProcess(
        condition=IfCondition(
            PythonExpression(["'", backend, "' == 'real' and '", agent_transport, "' == 'serial'"])
        ),
        cmd=[
            "bash",
            "-lc",
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
        output="screen",
    )

    lidar_bridge_process = ExecuteProcess(
        condition=IfCondition(PythonExpression(["'", backend, "' == 'real'"])),
        cmd=[
            "bash",
            "-lc",
            "socat -u UDP4-RECV:"
            + LIDAR_UDP_PORT
            + ",reuseaddr PTY,link="
            + os.environ.get("LEAP1_LIDAR_LINK", DEFAULT_LIDAR_LINK)
            + ",raw,echo=0,mode=666",
        ],
        output="screen",
    )

    real_bringup_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(xuegecar_bringup_dir, "launch", "xuegecar_bringup.launch.py")
        ),
        condition=IfCondition(PythonExpression(["'", backend, "' == 'real'"])),
        launch_arguments={
            "use_joint_state_publisher": "false",
            "use_sim_time": "false",
        }.items(),
    )

    sim_tf_broadcaster = Node(
        package="xuegecar_bringup",
        executable="xuegecar_bringup",
        name="xuegecar_bringup",
        output="screen",
        condition=IfCondition(PythonExpression(["'", backend, "' == 'sim'"])),
        parameters=[{"use_sim_time": True}],
    )

    gazebo_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(xuegecar_gazebo_dir, "launch", "gazebo_sim.launch.py")
        ),
        condition=IfCondition(PythonExpression(["'", backend, "' == 'sim'"])),
        launch_arguments={
            "world": world,
            "gui": gui,
            "use_sim_time": use_sim_time,
        }.items(),
    )

    a20_vehicle_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(leap1_a20_dir, "launch", "a20_vehicle.launch.py")
        ),
        condition=IfCondition(with_a20_stack),
        launch_arguments={
            "runtime_root": a20_runtime_root,
            "with_vehicle_camera": with_vehicle_camera,
            "with_manual_fire_tools": with_manual_fire_tools,
            "with_aux_detection_placeholders": with_aux_detection_placeholders,
            "vehicle_camera_device": vehicle_camera_device,
            "front_camera_port": front_camera_port,
        }.items(),
    )

    a20_center_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(leap1_a20_dir, "launch", "a20_center.launch.py")
        ),
        condition=IfCondition(center_console_enabled),
        launch_arguments={
            "runtime_root": a20_runtime_root,
            "panel_mode": center_panel_mode,
            "expected_vehicle_camera": with_vehicle_camera,
            "with_ground_camera": with_ground_camera,
            "ground_camera_device": ground_camera_device,
            "web_bind_port": a20_web_port,
            "ground_camera_port": ground_camera_port,
        }.items(),
    )

    rviz_node = Node(
        package="rviz2",
        executable="rviz2",
        name="rviz2",
        arguments=["-d", nav2_rviz],
        output="screen",
        parameters=[{"use_sim_time": use_sim_time}],
        condition=IfCondition(with_rviz),
    )

    critical_shutdown_actions = [
        RegisterEventHandler(
            OnProcessExit(
                target_action=udp_agent_process,
                on_exit=[
                    LogInfo(msg="micro-ROS Agent 已退出，正在关闭整套 Launch。"),
                    EmitEvent(event=Shutdown(reason="micro-ROS Agent exited")),
                ],
            )
        ),
        RegisterEventHandler(
            OnProcessExit(
                target_action=serial_agent_process,
                on_exit=[
                    LogInfo(msg="serial micro-ROS Agent 已退出，正在关闭整套 Launch。"),
                    EmitEvent(event=Shutdown(reason="serial micro-ROS Agent exited")),
                ],
            )
        ),
        RegisterEventHandler(
            OnProcessExit(
                target_action=lidar_bridge_process,
                on_exit=[
                    LogInfo(msg="雷达桥接已退出，正在关闭整套 Launch。"),
                    EmitEvent(event=Shutdown(reason="lidar bridge exited")),
                ],
            )
        ),
    ]

    return LaunchDescription(
        [
            DeclareLaunchArgument("backend", default_value="real", description="sim 或 real"),
            DeclareLaunchArgument(
                "agent_transport",
                default_value="udp",
                description="udp、serial、external_serial 或 none",
            ),
            DeclareLaunchArgument(
                "agent_serial_dev",
                default_value="/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0",
                description="serial micro-ROS 设备路径",
            ),
            DeclareLaunchArgument(
                "agent_serial_baud",
                default_value="921600",
                description="serial micro-ROS 波特率",
            ),
            DeclareLaunchArgument(
                "with_mapping",
                default_value="false",
                description="是否同时启动建图后端",
            ),
            DeclareLaunchArgument(
                "with_navigation",
                default_value="false",
                description="是否同时启动 Nav2 在线导航",
            ),
            DeclareLaunchArgument(
                "mapping_backend",
                default_value=_default_mapping_backend(),
                description="建图/定位后端: gmapping 或 slam_toolbox",
            ),
            DeclareLaunchArgument(
                "nav_profile",
                default_value=_default_nav_profile(),
                description="导航参数 profile: stable 或 legacy",
            ),
            DeclareLaunchArgument(
                "lidar_backend",
                default_value=_default_lidar_backend(),
                description="雷达驱动后端: ydlidar 或 ldlidar_ld19",
            ),
            DeclareLaunchArgument(
                "map_yaml",
                default_value=default_map_yaml,
                description="静态地图导航使用的 map yaml；为空时自动回退到最新 runtime 地图",
            ),
            DeclareLaunchArgument("with_rviz", default_value="false", description="是否同时启动 RViz2"),
            DeclareLaunchArgument(
                "with_keepout_filter",
                default_value="false",
                description="是否启用 Nav2 keepout filter",
            ),
            DeclareLaunchArgument(
                "keepout_mask_yaml",
                default_value="",
                description="keepout mask yaml 路径",
            ),
            DeclareLaunchArgument(
                "with_vehicle_web_teleop",
                default_value="false",
                description="是否启用中心端控制台",
            ),
            DeclareLaunchArgument(
                "with_a20_stack",
                default_value="false",
                description="是否启用 A20 状态机与地图标注栈",
            ),
            DeclareLaunchArgument(
                "with_vehicle_camera",
                default_value="false",
                description="是否启动车载相机节点",
            ),
            DeclareLaunchArgument(
                "with_manual_fire_tools",
                default_value="false",
                description="是否启用手动火情工具",
            ),
            DeclareLaunchArgument(
                "with_aux_detection_placeholders",
                default_value="true",
                description="是否启用烟雾/高温占位检测节点",
            ),
            DeclareLaunchArgument(
                "with_ground_camera",
                default_value="false",
                description="是否启用固定摄像头节点",
            ),
            DeclareLaunchArgument(
                "vehicle_camera_device",
                default_value="/dev/video0",
                description="车载相机设备路径",
            ),
            DeclareLaunchArgument(
                "ground_camera_device",
                default_value="",
                description="固定摄像头设备路径",
            ),
            DeclareLaunchArgument("a20_runtime_root", default_value="", description="A20 运行时目录"),
            DeclareLaunchArgument("a20_web_port", default_value="8090", description="A20 Web 端口"),
            DeclareLaunchArgument(
                "center_panel_mode",
                default_value="full_stack",
                description="中心端面板模式",
            ),
            DeclareLaunchArgument(
                "front_camera_port",
                default_value="8091",
                description="车载相机 MJPEG 端口",
            ),
            DeclareLaunchArgument(
                "ground_camera_port",
                default_value="8092",
                description="固定摄像头 MJPEG 端口",
            ),
            DeclareLaunchArgument(
                "gui",
                default_value="false",
                description="仿真模式是否启动 Gazebo GUI",
            ),
            DeclareLaunchArgument(
                "world",
                default_value=default_world,
                description="Gazebo Classic world 路径",
            ),
            udp_agent_process,
            serial_agent_process,
            lidar_bridge_process,
            gazebo_launch,
            TimerAction(period=2.0, actions=[real_bringup_launch, sim_tf_broadcaster]),
            OpaqueFunction(function=_dynamic_navigation_actions),
            TimerAction(period=4.0, actions=[rviz_node]),
            TimerAction(period=5.0, actions=[a20_vehicle_launch, a20_center_launch]),
            LogInfo(
                condition=IfCondition(
                    PythonExpression(
                        [
                            "'",
                            backend,
                            "' == 'real' and '",
                            agent_transport,
                            "' == 'external_serial'",
                        ]
                    )
                ),
                msg="当前使用外部 serial micro-ROS agent，由 systemd 或独立进程托管。",
            ),
            *critical_shutdown_actions,
        ]
    )
