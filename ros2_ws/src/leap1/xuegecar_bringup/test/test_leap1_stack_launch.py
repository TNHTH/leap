import importlib.util
import os
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "launch" / "leap1_stack.launch.py"
SPEC = importlib.util.spec_from_file_location("leap1_stack_launch", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def _write_map_yaml(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "image: map.pgm\nresolution: 0.05\norigin: [0.0, 0.0, 0.0]\n",
        encoding="utf-8",
    )


def test_default_runtime_profiles():
    assert MODULE._default_mapping_backend() == "slam_toolbox"
    assert MODULE._default_nav_profile() == "stable"


def test_resolve_runtime_map_yaml_prefers_explicit_path(tmp_path: Path):
    explicit_map = tmp_path / "explicit" / "map.yaml"
    _write_map_yaml(explicit_map)

    resolved = MODULE._resolve_runtime_map_yaml(str(tmp_path), str(explicit_map))

    assert resolved == str(explicit_map)


def test_resolve_runtime_map_yaml_uses_latest_runtime_map(tmp_path: Path):
    runtime_root = tmp_path / "runtime"
    old_map = runtime_root / "maps" / "2026-04-01-old" / "map.yaml"
    new_map = runtime_root / "maps" / "2026-04-02-new" / "map.yaml"
    _write_map_yaml(old_map)
    _write_map_yaml(new_map)
    os.utime(old_map, (1_000_000_000, 1_000_000_000))
    os.utime(new_map, (1_000_000_100, 1_000_000_100))

    resolved = MODULE._resolve_runtime_map_yaml(str(runtime_root), "")

    assert resolved == str(new_map)


def test_resolve_runtime_map_yaml_returns_empty_when_unavailable(tmp_path: Path):
    resolved = MODULE._resolve_runtime_map_yaml(str(tmp_path / "missing"), "")

    assert resolved == ""
