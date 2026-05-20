from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, EmitEvent, ExecuteProcess, LogInfo, RegisterEventHandler
from launch.conditions import IfCondition
from launch.event_handlers import OnProcessExit
from launch.events import Shutdown
from launch.substitutions import FindExecutable, LaunchConfiguration, PythonExpression
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    runtime_root = LaunchConfiguration("runtime_root")
    require_odom = LaunchConfiguration("require_odom")
    require_vehicle_camera = LaunchConfiguration("require_vehicle_camera")
    with_vehicle_camera = LaunchConfiguration("with_vehicle_camera")
    with_manual_fire_tools = LaunchConfiguration("with_manual_fire_tools")
    with_aux_detection_placeholders = LaunchConfiguration("with_aux_detection_placeholders")
    with_flame_detector = LaunchConfiguration("with_flame_detector")
    with_yolo_detector = LaunchConfiguration("with_yolo_detector")
    vehicle_camera_device = LaunchConfiguration("vehicle_camera_device")
    front_camera_port = LaunchConfiguration("front_camera_port")
    yolo_model_path = LaunchConfiguration("yolo_model_path")

    fire_node = Node(
        package="leap1_a20",
        executable="fire_event_placeholder_node",
        output="screen",
        condition=IfCondition(with_manual_fire_tools),
    )

    mission_node = Node(
        package="leap1_a20",
        executable="mission_manager_node",
        output="screen",
        parameters=[
            {
                "runtime_root": runtime_root,
            },
            {
                "require_odom": ParameterValue(
                    require_odom,
                    value_type=bool,
                )
            },
            {
                "require_vehicle_camera": ParameterValue(
                    require_vehicle_camera,
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

    perception_bridge_node = Node(
        package="leap1_a20",
        executable="perception_bridge_node",
        output="screen",
    )

    yolo_detector_node = Node(
        package="leap1_a20",
        executable="yolo_detection_node",
        name="vehicle_yolo_detection_node",
        output="screen",
        parameters=[
            {
                "camera_id": "vehicle_camera",
                "model_path": yolo_model_path,
                "region_id": "",
            }
        ],
        condition=IfCondition(with_yolo_detector),
    )

    smoke_placeholder_node = Node(
        package="leap1_a20",
        executable="smoke_detection_placeholder_node",
        output="screen",
        condition=IfCondition(with_aux_detection_placeholders),
    )

    high_temp_placeholder_node = Node(
        package="leap1_a20",
        executable="high_temp_detection_placeholder_node",
        output="screen",
        condition=IfCondition(with_aux_detection_placeholders),
    )

    safety_guard_node = Node(
        package="leap1_a20",
        executable="safety_guard_node",
        output="screen",
    )

    flame_detector_node = ExecuteProcess(
        cmd=[
            FindExecutable(name="python3"),
            "-m",
            "leap1_a20.flame_detection_node",
        ],
        output="screen",
        condition=IfCondition(PythonExpression(["'", with_flame_detector, "' == 'true'"])),
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
            DeclareLaunchArgument("require_odom", default_value="true", description="是否要求里程计心跳，否则进入故障"),
            DeclareLaunchArgument("require_vehicle_camera", default_value="true", description="是否要求车载相机心跳，否则进入故障"),
            DeclareLaunchArgument("with_vehicle_camera", default_value="true", description="是否启动车载相机"),
            DeclareLaunchArgument("with_flame_detector", default_value="false", description="是否启用内置轻量火焰检测"),
            DeclareLaunchArgument("with_yolo_detector", default_value="true", description="是否启用 camera_runtime YOLO 检测"),
            DeclareLaunchArgument("with_manual_fire_tools", default_value="false", description="是否启用手动火情占位"),
            DeclareLaunchArgument("with_aux_detection_placeholders", default_value="false", description="是否启用烟雾/高温占位"),
            DeclareLaunchArgument(
                "vehicle_camera_device",
                default_value="/dev/video0",
                description="车载 C100 对应的视频设备",
            ),
            DeclareLaunchArgument("front_camera_port", default_value="8091", description="车载相机 MJPEG 端口"),
            DeclareLaunchArgument("yolo_model_path", default_value="", description="camera_runtime YOLO best.pt 路径"),
            fire_node,
            mission_node,
            map_annotation_node,
            patrol_node,
            perception_bridge_node,
            yolo_detector_node,
            smoke_placeholder_node,
            high_temp_placeholder_node,
            safety_guard_node,
            flame_detector_node,
            vehicle_camera_node,
            mission_exit_shutdown,
        ]
    )
