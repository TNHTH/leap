from pathlib import Path


def test_web_demo_showcase_mode_is_frontend_only() -> None:
    app_js = (
        Path(__file__).resolve().parents[1]
        / "leap1_a20"
        / "web"
        / "app.js"
    ).read_text(encoding="utf-8")

    assert "function isDemoMode()" in app_js
    assert "searchParams.get(\"demo\") === \"1\"" in app_js
    assert "window.location.hash.includes(\"demo\")" in app_js
    assert "function buildDemoStatus()" in app_js
    assert "function buildDemoMap()" in app_js
    assert "function buildDemoCameraFrame(kind)" in app_js
    assert "function demoPost(url, payload = {})" in app_js
    assert "if (isDemoMode()) {" in app_js
    assert "return demoPost(url, payload);" in app_js


def test_web_demo_showcase_contains_fire_dispatch_content() -> None:
    app_js = (
        Path(__file__).resolve().parents[1]
        / "leap1_a20"
        / "web"
        / "app.js"
    ).read_text(encoding="utf-8")
    index_html = (
        Path(__file__).resolve().parents[1]
        / "leap1_a20"
        / "web"
        / "index.html"
    ).read_text(encoding="utf-8")

    assert "地下车库 B2-14 车位火情" in app_js
    assert "LEAP-A20-FIRE-20260421-017" in app_js
    assert "广播中心话术" in app_js
    assert "车载前视" in app_js
    assert "固定监控" in app_js
    assert "Leap A20 消防巡检广播中心" in index_html


def test_web_demo_showcase_does_not_expose_fake_status_copy() -> None:
    app_js = (
        Path(__file__).resolve().parents[1]
        / "leap1_a20"
        / "web"
        / "app.js"
    ).read_text(encoding="utf-8")
    index_html = (
        Path(__file__).resolve().parents[1]
        / "leap1_a20"
        / "web"
        / "index.html"
    ).read_text(encoding="utf-8")

    public_copy = "\n".join([app_js, index_html])
    forbidden = [
        "虚拟演示",
        "无车连接",
        "数据模拟",
        "前端模拟",
        "演示模式",
        "当前还没有可用地图",
        "相机未就绪",
        "demo://Leap-A20",
        "demo_showcase",
        "leap-broadcast-demo",
        "已完成虚拟建模展示",
        "广播中心演示数据",
    ]
    for text in forbidden:
        assert text not in public_copy
