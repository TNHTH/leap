from pathlib import Path

from ament_index_python.packages import get_package_share_directory


def repo_root() -> Path:
    return Path(__file__).resolve().parents[5]


def runtime_root(configured: str = "") -> Path:
    if configured:
        return Path(configured).expanduser().resolve()
    return repo_root() / "runtime" / "a20"


def ensure_runtime_layout(configured: str = "") -> Path:
    root = runtime_root(configured)
    (root / "maps").mkdir(parents=True, exist_ok=True)
    (root / "logs").mkdir(parents=True, exist_ok=True)
    return root


def package_share(package_name: str = "leap1_a20") -> Path:
    return Path(get_package_share_directory(package_name))
