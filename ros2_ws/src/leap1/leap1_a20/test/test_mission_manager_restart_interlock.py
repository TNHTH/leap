from __future__ import annotations

import ast
from pathlib import Path


MISSION_MANAGER_PATH = Path("/home/gwh/leap/ros2_ws/src/leap1/leap1_a20/leap1_a20/mission_manager_node.py")


def _load_restart_interlock_function():
    source = MISSION_MANAGER_PATH.read_text(encoding="utf-8")
    module = ast.parse(source, filename=str(MISSION_MANAGER_PATH))
    selected = []
    for node in module.body:
        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == "RESTART_INTERLOCK_STATES" for target in node.targets):
                selected.append(node)
        if isinstance(node, ast.FunctionDef) and node.name == "should_trip_restart_interlock":
            selected.append(node)
    mini_module = ast.Module(body=selected, type_ignores=[])
    namespace = {"Dict": dict}
    exec(compile(mini_module, str(MISSION_MANAGER_PATH), "exec"), namespace)
    return namespace["should_trip_restart_interlock"]


def test_restart_interlock_trips_for_unclean_dangerous_state() -> None:
    should_trip_restart_interlock = _load_restart_interlock_function()
    assert should_trip_restart_interlock({"clean_shutdown": False, "state": "PATROLLING"}) is True
    assert should_trip_restart_interlock({"clean_shutdown": False, "state": "SPRAYING"}) is True


def test_restart_interlock_skips_clean_or_idle_state() -> None:
    should_trip_restart_interlock = _load_restart_interlock_function()
    assert should_trip_restart_interlock({"clean_shutdown": True, "state": "PATROLLING"}) is False
    assert should_trip_restart_interlock({"clean_shutdown": False, "state": "IDLE"}) is False
    assert should_trip_restart_interlock({}) is False
