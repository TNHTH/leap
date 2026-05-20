from pathlib import Path


def test_alarm_source_uses_fault_source_before_perception_source() -> None:
    app_js = (
        Path(__file__).resolve().parents[1]
        / "leap1_a20"
        / "web"
        / "app.js"
    ).read_text(encoding="utf-8")

    assert "const alarmSource = activeFault" in app_js
    assert "`fault:${activeFault}`" in app_js
    assert "dom.alarmSource.textContent = `来源：${alarmSource}`;" in app_js
