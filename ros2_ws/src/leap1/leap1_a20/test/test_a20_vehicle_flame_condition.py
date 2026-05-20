from pathlib import Path


def test_a20_vehicle_launch_uses_explicit_true_condition_for_flame_detector() -> None:
    launch_path = (
        Path(__file__).resolve().parents[1]
        / "launch"
        / "a20_vehicle.launch.py"
    )
    source = launch_path.read_text(encoding="utf-8")

    assert "PythonExpression([\"'\", with_flame_detector, \"' == 'true'\"])" in source
