from pathlib import Path


def test_leap1_stack_launch_declares_and_forwards_with_flame_detector() -> None:
    launch_path = (
        Path(__file__).resolve().parents[2]
        / "xuegecar_bringup"
        / "launch"
        / "leap1_stack.launch.py"
    )
    source = launch_path.read_text(encoding="utf-8")

    assert 'LaunchConfiguration("with_flame_detector")' in source
    assert '"with_flame_detector": with_flame_detector' in source
    assert 'DeclareLaunchArgument(\n                "with_flame_detector"' in source
