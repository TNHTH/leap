from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    runtime_root = LaunchConfiguration("runtime_root")
    panel_mode = LaunchConfiguration("panel_mode")
    expected_vehicle_camera = LaunchConfiguration("expected_vehicle_camera")
    with_ground_camera = LaunchConfiguration("with_ground_camera")
    with_ground_yolo_detector = LaunchConfiguration("with_ground_yolo_detector")
    ground_camera_device = LaunchConfiguration("ground_camera_device")
    web_bind_port = LaunchConfiguration("web_bind_port")
    ground_camera_port = LaunchConfiguration("ground_camera_port")
    yolo_model_path = LaunchConfiguration("yolo_model_path")
    ground_camera_response_route_id = LaunchConfiguration("ground_camera_response_route_id")

    broadcast_node = Node(
        package="leap1_a20",
        executable="broadcast_center_server",
        output="screen",
        parameters=[
            {
                "panel_mode": panel_mode,
                "runtime_root": runtime_root,
                "bind_port": ParameterValue(web_bind_port, value_type=int),
                "expected_vehicle_camera": ParameterValue(expected_vehicle_camera, value_type=bool),
                "expected_ground_camera": ParameterValue(with_ground_camera, value_type=bool),
            }
        ],
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

    ground_yolo_node = Node(
        package="leap1_a20",
        executable="yolo_detection_node",
        name="ground_yolo_detection_node",
        output="screen",
        parameters=[
            {
                "camera_id": "ground_camera",
                "model_path": yolo_model_path,
                "region_id": ground_camera_response_route_id,
            }
        ],
        condition=IfCondition(with_ground_yolo_detector),
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument("runtime_root", default_value="", description="A20 运行时根目录"),
            DeclareLaunchArgument("panel_mode", default_value="status_only", description="面板模式"),
            DeclareLaunchArgument("expected_vehicle_camera", default_value="true", description="是否期望车载相机在线"),
            DeclareLaunchArgument("with_ground_camera", default_value="true", description="是否启动固定摄像头"),
            DeclareLaunchArgument("with_ground_yolo_detector", default_value="true", description="是否对固定摄像头启用 YOLO 检测"),
            DeclareLaunchArgument("ground_camera_device", default_value="", description="固定摄像头设备路径"),
            DeclareLaunchArgument("web_bind_port", default_value="8090", description="广播中心 Web 端口"),
            DeclareLaunchArgument("ground_camera_port", default_value="8092", description="固定摄像头 MJPEG 端口"),
            DeclareLaunchArgument("yolo_model_path", default_value="", description="camera_runtime YOLO best.pt 路径"),
            DeclareLaunchArgument(
                "ground_camera_response_route_id",
                default_value="camera:ground_camera",
                description="固定监控报警后派车确认的 route 名、id 或 camera:<camera_id>",
            ),
            broadcast_node,
            ground_camera_node,
            ground_yolo_node,
        ]
    )
