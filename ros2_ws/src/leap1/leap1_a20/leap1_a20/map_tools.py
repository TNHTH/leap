from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Dict, List, Tuple

import cv2
import numpy as np
import yaml


DEFAULT_ANNOTATIONS: Dict[str, Any] = {
    "map_id": "",
    "updated_at": "",
    "zones": [],
    "waypoints": [],
    "fixed_cameras": [],
    "routes": [],
}


def sanitize_map_id(map_id: str) -> str:
    safe = "".join(ch for ch in map_id if ch.isalnum() or ch in ("-", "_"))
    return safe or "map_default"


def map_dir(runtime_root: Path, map_id: str) -> Path:
    return runtime_root / "maps" / sanitize_map_id(map_id)


def map_yaml_path(runtime_root: Path, map_id: str) -> Path:
    return map_dir(runtime_root, map_id) / "map.yaml"


def map_image_path(runtime_root: Path, map_id: str) -> Path:
    return map_dir(runtime_root, map_id) / "map.pgm"


def annotations_path(runtime_root: Path, map_id: str) -> Path:
    return map_dir(runtime_root, map_id) / "annotations.json"


def keepout_mask_path(runtime_root: Path, map_id: str) -> Path:
    return map_dir(runtime_root, map_id) / "keepout_mask.pgm"


def keepout_yaml_path(runtime_root: Path, map_id: str) -> Path:
    return map_dir(runtime_root, map_id) / "keepout_mask.yaml"


def _encode_png(image_path: Path) -> bytes:
    image = cv2.imread(str(image_path), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise RuntimeError(f"无法读取图像: {image_path}")
    ok, encoded = cv2.imencode(".png", image)
    if not ok:
        raise RuntimeError(f"无法编码 PNG: {image_path}")
    return encoded.tobytes()


def map_png_bytes(runtime_root: Path, map_id: str) -> bytes:
    return _encode_png(map_image_path(runtime_root, map_id))


def keepout_png_bytes(runtime_root: Path, map_id: str) -> bytes:
    return _encode_png(keepout_mask_path(runtime_root, map_id))


def load_yaml(path: Path) -> Dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def list_maps(runtime_root: Path) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    maps_root = runtime_root / "maps"
    maps_root.mkdir(parents=True, exist_ok=True)
    for child in sorted(maps_root.iterdir()):
        if not child.is_dir():
            continue
        map_yaml = child / "map.yaml"
        if not map_yaml.exists():
            continue
        annotations = load_annotations(runtime_root, child.name)
        results.append(
            {
                "map_id": child.name,
                "map_yaml": str(map_yaml),
                "has_keepout": keepout_yaml_path(runtime_root, child.name).exists(),
                "zone_count": len(annotations.get("zones", [])),
                "waypoint_count": len(annotations.get("waypoints", [])),
                "fixed_camera_count": len(annotations.get("fixed_cameras", [])),
                "route_count": len(annotations.get("routes", [])),
            }
        )
    return results


def load_annotations(runtime_root: Path, map_id: str) -> Dict[str, Any]:
    path = annotations_path(runtime_root, map_id)
    if not path.exists():
        payload = copy.deepcopy(DEFAULT_ANNOTATIONS)
        payload["map_id"] = sanitize_map_id(map_id)
        return payload
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def save_annotations(runtime_root: Path, map_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    payload = copy.deepcopy(payload)
    payload.setdefault("zones", [])
    payload.setdefault("waypoints", [])
    payload.setdefault("fixed_cameras", [])
    payload.setdefault("routes", [])
    payload["map_id"] = sanitize_map_id(map_id)
    path = annotations_path(runtime_root, map_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return payload


def load_map_meta(runtime_root: Path, map_id: str) -> Dict[str, Any]:
    yaml_path = map_yaml_path(runtime_root, map_id)
    if not yaml_path.exists():
        raise FileNotFoundError(f"未找到地图配置: {yaml_path}")
    meta = load_yaml(yaml_path)
    image_path = (yaml_path.parent / meta["image"]).resolve()
    image = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(f"无法读取地图图像: {image_path}")
    meta["image_path"] = str(image_path)
    meta["width"] = int(image.shape[1])
    meta["height"] = int(image.shape[0])
    return meta


def pixel_to_world(meta: Dict[str, Any], pixel_x: float, pixel_y: float) -> Tuple[float, float]:
    resolution = float(meta["resolution"])
    origin_x = float(meta["origin"][0])
    origin_y = float(meta["origin"][1])
    image_height = float(meta["height"])
    world_x = origin_x + pixel_x * resolution
    world_y = origin_y + (image_height - pixel_y) * resolution
    return world_x, world_y


def draw_keepout_mask(runtime_root: Path, map_id: str, annotations: Dict[str, Any]) -> Dict[str, Any]:
    meta = load_map_meta(runtime_root, map_id)
    image = cv2.imread(meta["image_path"], cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError("无法生成 keepout mask，底图读取失败。")

    mask = np.full_like(image, 254)
    for zone in annotations.get("zones", []):
        if zone.get("kind") != "keepout_zone":
            continue
        points = zone.get("points", [])
        if len(points) < 3:
            continue
        polygon = np.array(
            [[int(point["x"]), int(point["y"])] for point in points],
            dtype=np.int32,
        )
        cv2.fillPoly(mask, [polygon], 0)

    mask_file = keepout_mask_path(runtime_root, map_id)
    yaml_file = keepout_yaml_path(runtime_root, map_id)
    mask_file.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(mask_file), mask)
    yaml_payload = {
        "image": mask_file.name,
        "mode": meta.get("mode", "trinary"),
        "resolution": float(meta["resolution"]),
        "origin": [float(value) for value in meta["origin"]],
        "negate": int(meta.get("negate", 0)),
        "occupied_thresh": float(meta.get("occupied_thresh", 0.65)),
        "free_thresh": float(meta.get("free_thresh", 0.196)),
    }
    yaml_file.write_text(yaml.safe_dump(yaml_payload, sort_keys=False), encoding="utf-8")
    return {
        "keepout_mask": str(mask_file),
        "keepout_yaml": str(yaml_file),
        "width": int(mask.shape[1]),
        "height": int(mask.shape[0]),
    }
