from glob import glob
from setuptools import find_packages, setup


package_name = "leap1_a20"


setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/launch", glob("launch/*.launch.py")),
        ("share/" + package_name + "/config", ["config/default_params.yaml"]),
        (
            "share/" + package_name + "/web",
            [
                "leap1_a20/web/index.html",
                "leap1_a20/web/app.js",
                "leap1_a20/web/styles.css",
            ],
        ),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="gwh",
    maintainer_email="gwh@local",
    description="Leap A20 computer-direct orchestration stack.",
    license="Apache-2.0",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "camera_bridge_node = leap1_a20.camera_bridge_node:main",
            "ground_camera_bridge_node = leap1_a20.ground_camera_bridge_node:main",
            "fire_event_placeholder_node = leap1_a20.fire_event_placeholder_node:main",
            "mission_manager_node = leap1_a20.mission_manager_node:main",
            "map_annotation_server = leap1_a20.map_annotation_server:main",
            "broadcast_center_server = leap1_a20.broadcast_center_server:main",
            "patrol_executor_node = leap1_a20.patrol_executor_node:main",
            "flame_detection_node = leap1_a20.flame_detection_node:main",
            "yolo_detection_node = leap1_a20.yolo_detection_node:main",
            "perception_bridge_node = leap1_a20.perception_bridge_node:main",
            "smoke_detection_placeholder_node = leap1_a20.perception_placeholder_nodes:smoke_main",
            "high_temp_detection_placeholder_node = leap1_a20.perception_placeholder_nodes:high_temp_main",
            "safety_guard_node = leap1_a20.safety_guard_node:main",
        ]
    },
)
