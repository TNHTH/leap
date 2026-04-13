from .camera_bridge_node import run_camera_bridge


def main() -> None:
    run_camera_bridge(
        node_name="ground_camera_bridge_node",
        default_camera_name="ground_camera",
        default_device="",
        default_frame_id="ground_camera_link",
        default_mjpeg_port=8092,
    )
