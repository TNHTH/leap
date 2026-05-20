from pathlib import Path


def test_alarm_overlay_hidden_attribute_overrides_grid_display():
    css_path = Path(__file__).resolve().parents[1] / "leap1_a20" / "web" / "styles.css"
    css = css_path.read_text(encoding="utf-8")

    assert ".alarm-overlay[hidden]" in css
    assert "display: none" in css


def test_web_index_cache_busts_stylesheet_for_alarm_fix():
    index_path = Path(__file__).resolve().parents[1] / "leap1_a20" / "web" / "index.html"
    html = index_path.read_text(encoding="utf-8")

    assert 'href="/styles.css?v=' in html
