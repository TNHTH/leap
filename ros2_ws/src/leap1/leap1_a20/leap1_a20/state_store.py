import json
import threading
from pathlib import Path
from typing import Any, Dict


class JsonStateStore:
    """简单的线程安全 JSON 状态存储。"""

    def __init__(self, path: Path):
        self._path = path
        self._lock = threading.Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self._path

    def load(self, default: Dict[str, Any] | None = None) -> Dict[str, Any]:
        with self._lock:
            if not self._path.exists():
                return dict(default or {})
            try:
                return json.loads(self._path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return dict(default or {})

    def save(self, payload: Dict[str, Any]) -> None:
        with self._lock:
            self._path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )
