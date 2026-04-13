from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, EmitEvent, LogInfo, RegisterEventHandler
from launch.conditions import IfCondition
from launch.event_handlers import OnProcessExit
from launch.events import Shutdown
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    runtime_root = LaunchConfiguration("runtime_root")
    with_web_panel = LaunchConfiguration("with_web_panel")
    with_vehicle_camera = LaunchConfiguration("with_vehicle_camera")
    with_ground_camera = LaunchConfiguration("with_ground_camera")
    vehicle_camera_device = LaunchConfiguration("vehicle_camera_device")
    ground_camera_device = LaunchConfiguration("ground_camera_device")
    web_bind_port = LaunchConfiguration("web_bind_port")
    front_camera_port = LaunchConfiguration("front_camera_port")
    ground_camera_port = LaunchConfiguration("ground_camera_port")

    fire_node = Node(
        package="leap1_a20",
        executable="fire_event_placeholder_node",
        output="screen",
    )

    mission_node = Node(
        package="leap1_a20",
        executable="mission_manager_node",
        output="screen",
        parameters=[
            {
                "require_vehicle_camera": ParameterValue(
                    with_vehicle_camera,
                    value_type=bool,
                )
            }
        ],
    )

    map_annotation_node = Node(
        package="leap1_a20",
        executable="map_annotation_server",
        output="screen",
        parameters=[{"runtime_root": runtime_root}],
    )

    patrol_node = Node(
        package="leap1_a20",
        executable="patrol_executor_node",
        output="screen",
        parameters=[{"runtime_root": runtime_root}],
    )

    broadcast_node = Node(
        package="leap1_a20",
        executable="broadcast_center_server",
        output="screen",
        parameters=[
            {
                "runtime_root": runtime_root,
                "bind_port": ParameterValue(web_bind_port, value_type=int),
            }
        ],
        condition=IfCondition(with_web_panel),
    )

    vehicle_camera_node = Node(
        package="leap1_a20",
        executable="camera_bridge_node",
        output="screen",
        parameters=[
            {
                "device": vehicle_camera_device,
                "mjpeg_port": ParameterValue(front_camera_port, value_type=int),
            }
        ],
        condition=IfCondition(with_vehicle_camera),
    )

    ground_camera_node = Node(
        package="leap1_a20",
        executable="ground_camera_bridge_node",
        output="screen",
        parameters=[
            {
                "device": ground_camera_device,
                "mjpeg_port": ParameterValue(ground_camera_port, value_type=int),
            }
        ],
        condition=IfCondition(with_ground_camera),
    )

    mission_exit_shutdown = RegisterEventHandler(
        OnProcessExit(
            target_action=mission_node,
            on_exit=[
                LogInfo(msg="mission_manager_node 已退出，A20 栈整体关闭以确保停车。"),
                EmitEvent(event=Shutdown(reason="mission manager exited")),
            ],
        )
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument("runtime_root", default_value="", description="A20 运行时根目录"),
            DeclareLaunchArgument("with_web_panel", default_value="true", description="是否启用广播中心 Web 面板"),
            DeclareLaunchArgument("with_vehicle_camera", default_value="true", description="是否启动车载相机"),
            DeclareLaunchArgument("with_ground_camera", default_value="true", description="是否启动固定摄像头占位"),
            DeclareLaunchArgument(
                "vehicle_camera_device",
                default_value="/dev/video0",
                description="车载 C100 对应的视频设备",
            ),
            DeclareLaunchArgument(
                "ground_camera_device",
                default_value="",
                description="固定摄像头设备路径，留空则节点保持离线占位",
            ),
            DeclareLaunchArgument("web_bind_port", default_value="8090", description="广播中心 Web 端口"),
            DeclareLaunchArgument("front_camera_port", default_value="8091", description="车载相机 MJPEG 端口"),
            DeclareLaunchArgument("ground_camera_port", default_value="8092", description="固定摄像头 MJPEG 端口"),
            fire_node,
            mission_node,
            map_annotation_node,
            patrol_node,
            broadcast_node,
            vehicle_camera_node,
            ground_camera_node,
            mission_exit_shutdown,
        ]
    )
