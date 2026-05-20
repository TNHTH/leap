from __future__ import annotations

import os
import shutil
import socket
import time
from pathlib import Path
from typing import Any, Dict

from .common import utc_now_text


class SystemSnapshotBuilder:
    """采集广播中心面板需要的本机与信号状态。"""

    def __init__(
        self,
        *,
        runtime_root: Path,
        hostname: str,
        boot_time: float,
        expected_vehicle_camera: bool,
        expected_ground_camera: bool,
    ) -> None:
        self.runtime_root = runtime_root
        self.hostname = hostname
        self.boot_time = boot_time
        self.expected_vehicle_camera = expected_vehicle_camera
        self.expected_ground_camera = expected_ground_camera

    def build(
        self,
        *,
        panel_mode: str,
        cameras: Dict[str, Dict[str, Any]],
        camera_heartbeats: Dict[str, float],
        last_odom_monotonic: float | None,
        perception_heartbeat: float | None,
    ) -> Dict[str, Any]:
        meminfo = self._read_meminfo()
        memory_total_kib = int(meminfo.get("MemTotal", 0))
        memory_available_kib = int(meminfo.get("MemAvailable", 0))
        disk_usage = shutil.disk_usage(self.runtime_root)

        return {
            "panel_mode": panel_mode,
            "hostname": self.hostname,
            "ipv4": self._resolve_ipv4_addresses(),
            "uptime_sec": self._uptime_sec(),
            "loadavg": [round(value, 2) for value in os.getloadavg()],
            "cpu_count": os.cpu_count() or 0,
            "memory": self._memory_payload(memory_total_kib, memory_available_kib),
            "disk": self._disk_payload(disk_usage),
            "signals": self._signals_payload(
                cameras=cameras,
                camera_heartbeats=camera_heartbeats,
                last_odom_monotonic=last_odom_monotonic,
                perception_heartbeat=perception_heartbeat,
            ),
            "runtime_root": str(self.runtime_root),
            "updated_at": utc_now_text(),
        }

    def _read_meminfo(self) -> Dict[str, int]:
        result: Dict[str, int] = {}
        try:
            for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
                if ":" not in line:
                    continue
                key, value = line.split(":", 1)
                result[key] = int(value.strip().split()[0])
        except (FileNotFoundError, ValueError):
            return {}
        return result

    def _resolve_ipv4_addresses(self) -> list[str]:
        addresses: list[str] = []
        self._append_default_route_ip(addresses)
        self._append_hostname_ips(addresses)
        return addresses

    def _append_default_route_ip(self, addresses: list[str]) -> None:
        try:
            probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                probe.connect(("8.8.8.8", 80))
                self._append_public_ip(addresses, probe.getsockname()[0])
            finally:
                probe.close()
        except OSError:
            return

    def _append_hostname_ips(self, addresses: list[str]) -> None:
        try:
            infos = socket.getaddrinfo(self.hostname, None, socket.AF_INET)
        except socket.gaierror:
            return
        for _, _, _, _, sockaddr in infos:
            self._append_public_ip(addresses, sockaddr[0])

    def _append_public_ip(self, addresses: list[str], candidate: str) -> None:
        if candidate and not candidate.startswith("127.") and candidate not in addresses:
            addresses.append(candidate)

    def _uptime_sec(self) -> int:
        try:
            return int(float(Path("/proc/uptime").read_text(encoding="utf-8").split()[0]))
        except (FileNotFoundError, ValueError, IndexError):
            return max(0, int(time.time() - self.boot_time))

    def _memory_payload(self, total_kib: int, available_kib: int) -> Dict[str, Any]:
        used_kib = max(total_kib - available_kib, 0)
        used_percent = round((used_kib / total_kib) * 100.0, 1) if total_kib else 0.0
        return {
            "total_kib": total_kib,
            "available_kib": available_kib,
            "used_percent": used_percent,
        }

    def _disk_payload(self, disk_usage: Any) -> Dict[str, Any]:
        disk_used = disk_usage.total - disk_usage.free
        return {
            "total_bytes": disk_usage.total,
            "free_bytes": disk_usage.free,
            "used_percent": round((disk_used / max(disk_usage.total, 1)) * 100.0, 1),
        }

    def _signals_payload(
        self,
        *,
        cameras: Dict[str, Dict[str, Any]],
        camera_heartbeats: Dict[str, float],
        last_odom_monotonic: float | None,
        perception_heartbeat: float | None,
    ) -> Dict[str, Any]:
        odom_age_sec = self._age_sec(last_odom_monotonic)
        vehicle_camera_age_sec = self._age_sec(camera_heartbeats.get("vehicle_camera"))
        ground_camera_age_sec = self._age_sec(camera_heartbeats.get("ground_camera"))
        perception_age_sec = self._age_sec(perception_heartbeat)

        return {
            "odom_online": odom_age_sec is not None and odom_age_sec <= 1.5,
            "odom_age_sec": odom_age_sec,
            "vehicle_camera_expected": self.expected_vehicle_camera,
            "vehicle_camera_online": bool(cameras.get("vehicle_camera", {}).get("online", False)),
            "vehicle_camera_age_sec": vehicle_camera_age_sec,
            "ground_camera_expected": self.expected_ground_camera,
            "ground_camera_online": bool(cameras.get("ground_camera", {}).get("online", False)),
            "ground_camera_age_sec": ground_camera_age_sec,
            "perception_online": perception_age_sec is not None and perception_age_sec <= 1.5,
            "perception_age_sec": perception_age_sec,
        }

    def _age_sec(self, timestamp: float | None) -> float | None:
        if timestamp is None:
            return None
        return max(0.0, time.monotonic() - timestamp)
