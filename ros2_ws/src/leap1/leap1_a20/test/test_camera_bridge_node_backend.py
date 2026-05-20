from pathlib import Path


def test_camera_bridge_prefers_v4l2_for_local_video_devices():
    source = (
        Path(__file__).resolve().parents[1]
        / "leap1_a20"
        / "camera_bridge_node.py"
    ).read_text(encoding="utf-8")

    assert 'self.device.startswith("/dev/video")' in source
    assert "cv2.CAP_V4L2" in source
