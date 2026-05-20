from __future__ import annotations

from pathlib import Path

from leap1_a20.map_tools import load_annotations, save_annotations


def test_save_annotations_preserves_fixed_cameras(tmp_path: Path) -> None:
    payload = {
        "waypoints": [],
        "zones": [],
        "fixed_cameras": [
            {
                "id": "ground_camera",
                "camera_id": "ground_camera",
                "pixel": {"x": 120.0, "y": 80.0},
                "route_id": "camera:ground_camera",
            }
        ],
        "routes": [],
    }

    saved = save_annotations(tmp_path, "map_demo", payload)
    loaded = load_annotations(tmp_path, "map_demo")

    assert saved["fixed_cameras"][0]["camera_id"] == "ground_camera"
    assert loaded["fixed_cameras"][0]["route_id"] == "camera:ground_camera"
