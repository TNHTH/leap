from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_vehicle_runtime_exports_flame_detector_disabled() -> None:
    script = (REPO_ROOT / "tools" / "run_leap1_vehicle_runtime.sh").read_text(encoding="utf-8")

    assert 'LEAP1_WITH_FLAME_DETECTOR="${LEAP1_WITH_FLAME_DETECTOR:-false}"' in script


def test_run_stack_forwards_with_flame_detector_argument() -> None:
    script = (REPO_ROOT / "tools" / "run_leap1_stack.sh").read_text(encoding="utf-8")

    assert '[[ -n "${LEAP1_WITH_FLAME_DETECTOR:-}" ]] && DEFAULT_ARGS+=("with_flame_detector:=${LEAP1_WITH_FLAME_DETECTOR}")' in script
