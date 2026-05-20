import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction, SetEnvironmentVariable
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.descriptions import ParameterFile
from nav2_common.launch import RewrittenYaml


def _profile_params_file(pkg_share: str, nav_profile: str) -> str:
    if nav_profile == "stable":
        return os.path.join(pkg_share, "param", "nav2_stable.yaml")
    return os.path.join(pkg_share, "param", "gmapping_nav2.yaml")


def _configured_params(
    source_file: str,
    use_sim_time: str,
    autostart: str,
    map_yaml: str,
) -> ParameterFile:
    rewrites = {
        "use_sim_time": use_sim_time,
        "autostart": autostart,
    }
    if map_yaml:
        rewrites["yaml_filename"] = map_yaml
    return ParameterFile(
        RewrittenYaml(
            source_file=source_file,
            param_rewrites=rewrites,
            convert_types=True,
        ),
        allow_substs=True,
    )


def _collision_params(pkg_share: str, use_sim_time: str) -> ParameterFile:
    return ParameterFile(
        RewrittenYaml(
            source_file=os.path.join(pkg_share, "param", "collision_monitor.yaml"),
            param_rewrites={"use_sim_time": use_sim_time},
            convert_types=True,
        ),
        allow_substs=True,
    )


def _launch_setup(context, *args):
    del args
    pkg_share = get_package_share_directory("xuegecar_navigation2")

    use_sim_time = LaunchConfiguration("use_sim_time").perform(context)
    nav_profile = LaunchConfiguration("nav_profile").perform(context) or "stable"
    nav2_params_file = LaunchConfiguration("nav2_params_file").perform(context)
    map_yaml = LaunchConfiguration("map_yaml").perform(context)
    autostart = LaunchConfiguration("autostart").perform(context)
    log_level = LaunchConfiguration("log_level").perform(context)
    with_keepout_filter = LaunchConfiguration("with_keepout_filter")
    keepout_mask_yaml = LaunchConfiguration("keepout_mask_yaml")

    if not nav2_params_file:
        nav2_params_file = _profile_params_file(pkg_share, nav_profile)

    configured_params = _configured_params(
        nav2_params_file,
        use_sim_time,
        autostart,
        map_yaml,
    )
    collision_params = _collision_params(pkg_share, use_sim_time)
    remappings = [("/tf", "tf"), ("/tf_static", "tf_static")]
    use_collision_monitor = nav_profile == "stable"
    use_map_localization = bool(map_yaml)
    lifecycle_nodes = [
        "controller_server",
        "smoother_server",
        "planner_server",
        "behavior_server",
        "bt_navigator",
        "waypoint_follower",
        "velocity_smoother",
    ]
    if use_map_localization:
        lifecycle_nodes = ["map_server", "amcl"] + lifecycle_nodes
    if use_collision_monitor:
        lifecycle_nodes.append("collision_monitor")

    keepout_lifecycle_nodes = [
        "keepout_filter_mask_server",
        "keepout_costmap_filter_info_server",
    ]

    velocity_output_topic = "cmd_vel_raw" if use_collision_monitor else "cmd_vel"

    actions = [
        SetEnvironmentVariable("RCUTILS_LOGGING_BUFFERED_STREAM", "1"),
        Node(
            package="nav2_map_server",
            executable="map_server",
            name="keepout_filter_mask_server",
            output="screen",
            parameters=[
                {
                    "use_sim_time": use_sim_time == "true",
                    "yaml_filename": keepout_mask_yaml,
                    "topic_name": "keepout_filter_mask",
                    "frame_id": "map",
                }
            ],
            arguments=["--ros-args", "--log-level", log_level],
            condition=IfCondition(with_keepout_filter),
        ),
        Node(
            package="nav2_map_server",
            executable="costmap_filter_info_server",
            name="keepout_costmap_filter_info_server",
            output="screen",
            parameters=[
                {
                    "use_sim_time": use_sim_time == "true",
                    "type": 0,
                    "filter_info_topic": "keepout_costmap_filter_info",
                    "mask_topic": "keepout_filter_mask",
                    "base": 0.0,
                    "multiplier": 1.0,
                }
            ],
            arguments=["--ros-args", "--log-level", log_level],
            condition=IfCondition(with_keepout_filter),
        ),
        Node(
            package="nav2_lifecycle_manager",
            executable="lifecycle_manager",
            name="lifecycle_manager_keepout",
            output="screen",
            arguments=["--ros-args", "--log-level", log_level],
            parameters=[
                {"use_sim_time": use_sim_time == "true"},
                {"autostart": autostart == "true"},
                {"node_names": keepout_lifecycle_nodes},
            ],
            condition=IfCondition(with_keepout_filter),
        ),
        Node(
            package="nav2_map_server",
            executable="map_server",
            name="map_server",
            output="screen",
            parameters=[configured_params],
            arguments=["--ros-args", "--log-level", log_level],
            condition=IfCondition(str(use_map_localization).lower()),
        ),
        Node(
            package="nav2_amcl",
            executable="amcl",
            name="amcl",
            output="screen",
            parameters=[configured_params],
            arguments=["--ros-args", "--log-level", log_level],
            condition=IfCondition(str(use_map_localization).lower()),
        ),
        Node(
            package="nav2_controller",
            executable="controller_server",
            name="controller_server",
            output="screen",
            parameters=[configured_params],
            arguments=["--ros-args", "--log-level", log_level],
            remappings=remappings + [("cmd_vel", "cmd_vel_nav")],
        ),
        Node(
            package="nav2_smoother",
            executable="smoother_server",
            name="smoother_server",
            output="screen",
            parameters=[configured_params],
            arguments=["--ros-args", "--log-level", log_level],
            remappings=remappings,
        ),
        Node(
            package="nav2_planner",
            executable="planner_server",
            name="planner_server",
            output="screen",
            parameters=[configured_params],
            arguments=["--ros-args", "--log-level", log_level],
            remappings=remappings,
        ),
        Node(
            package="nav2_behaviors",
            executable="behavior_server",
            name="behavior_server",
            output="screen",
            parameters=[configured_params],
            arguments=["--ros-args", "--log-level", log_level],
            remappings=remappings,
        ),
        Node(
            package="nav2_bt_navigator",
            executable="bt_navigator",
            name="bt_navigator",
            output="screen",
            parameters=[configured_params],
            arguments=["--ros-args", "--log-level", log_level],
            remappings=remappings,
        ),
        Node(
            package="nav2_waypoint_follower",
            executable="waypoint_follower",
            name="waypoint_follower",
            output="screen",
            parameters=[configured_params],
            arguments=["--ros-args", "--log-level", log_level],
            remappings=remappings,
        ),
        Node(
            package="nav2_velocity_smoother",
            executable="velocity_smoother",
            name="velocity_smoother",
            output="screen",
            parameters=[configured_params],
            arguments=["--ros-args", "--log-level", log_level],
            remappings=remappings
            + [("cmd_vel", "cmd_vel_nav"), ("cmd_vel_smoothed", velocity_output_topic)],
        ),
    ]

    if use_collision_monitor:
        actions.append(
            Node(
                package="nav2_collision_monitor",
                executable="collision_monitor",
                name="collision_monitor",
                output="screen",
                parameters=[collision_params],
                arguments=["--ros-args", "--log-level", log_level],
            )
        )

    actions.append(
        Node(
            package="nav2_lifecycle_manager",
            executable="lifecycle_manager",
            name="lifecycle_manager_navigation",
            output="screen",
            arguments=["--ros-args", "--log-level", log_level],
            parameters=[
                {"use_sim_time": use_sim_time == "true"},
                {"autostart": autostart == "true"},
                {"node_names": lifecycle_nodes},
            ],
        )
    )
    return actions


def generate_launch_description():
    return LaunchDescription(
        [
            DeclareLaunchArgument("use_sim_time", default_value="false"),
            DeclareLaunchArgument("nav_profile", default_value="stable"),
            DeclareLaunchArgument("nav2_params_file", default_value=""),
            DeclareLaunchArgument("map_yaml", default_value=""),
            DeclareLaunchArgument("autostart", default_value="true"),
            DeclareLaunchArgument("log_level", default_value="info"),
            DeclareLaunchArgument("with_keepout_filter", default_value="false"),
            DeclareLaunchArgument("keepout_mask_yaml", default_value=""),
            OpaqueFunction(function=_launch_setup),
        ]
    )
