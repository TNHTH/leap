from __future__ import annotations

import sys
from pathlib import Path


REPO_PKG_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_PKG_ROOT))

from leap1_a20.http_utils import ReusableThreadingHTTPServer, resolve_public_host


def test_resolve_public_host_prefers_configured_value() -> None:
    assert resolve_public_host("10.0.0.2") == "10.0.0.2"


def test_reusable_threading_http_server_keeps_existing_socket_flags() -> None:
    assert ReusableThreadingHTTPServer.daemon_threads is True
    assert ReusableThreadingHTTPServer.allow_reuse_address is True
