from setuptools import find_packages, setup


package_name = "leap1_a20"


setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/launch", ["launch/a20_vehicle.launch.py"]),
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
        ]
    },
)
