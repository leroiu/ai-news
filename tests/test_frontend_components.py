"""轻量前端组件层测试。"""
from src.frontend.frontend_components import (
    COMPONENT_CSS, badge, button, card, empty_state, filter_bar,
    favorite_button, page_header, section, stat,
)
from src.frontend.frontend_interactions import COMPONENT_JS
from src.frontend.frontend_styles import SHARED_JS
from src.frontend.frontend_shell import PageShell, render_page


def test_components_escape_plain_text():
    html = page_header('<script>alert("x")</script>', summary="A&B")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "A&amp;B" in html


def test_button_variants_and_attributes():
    html = button("运行", variant="secondary", size="small", attrs={"aria_label": "运行任务", "disabled": True})
    assert "ui-button--secondary" in html
    assert "ui-button--small" in html
    assert 'aria-label="运行任务"' in html
    assert "disabled" in html


def test_component_composition():
    controls = button("清除", variant="ghost")
    content = filter_bar(controls, count_text="12 条")
    content += section("概览", card(stat(12, "实体"), title="统计"))
    content += empty_state("暂无数据", description="稍后再试", action_html=button("刷新"))
    content += badge("正常", tone="success")
    assert "ui-filter-bar" in content
    assert "ui-section" in content
    assert "ui-card" in content
    assert "ui-empty" in content
    assert "ui-favorite" in favorite_button("news", "abc", "标题")


def test_rejects_unknown_component_variants():
    try:
        button("错误", variant="unknown")
    except ValueError as exc:
        assert "unsupported" in str(exc)
    else:
        raise AssertionError("unknown variant should fail")


def test_css_uses_semantic_tokens_and_reduced_motion():
    assert "var(--bg-card)" in COMPONENT_CSS
    assert "var(--text-primary)" in COMPONENT_CSS
    assert "prefers-reduced-motion" in COMPONENT_CSS


def test_component_js_exposes_reusable_interactions():
    for name in ("uiSetBusy", "uiToggleDisclosure", "uiClearForm", "uiDebounce", "uiAnnounce", "uiToast"):
        assert f"function {name}" in COMPONENT_JS


def test_shared_js_exposes_favorite_store():
    for name in ("uiToggleFavorite", "uiFavoriteStore", "uiFavoriteKey"):
        assert f"function {name}" in SHARED_JS


def test_shell_composes_existing_design_system():
    html = render_page(PageShell(
        title_key="platform_title",
        current_page="dashboard",
        body_html=page_header("测试页面"),
        extra_css=".demo{color:var(--accent)}",
        extra_js="window.demoReady=true;",
    ))
    assert '<html lang="zh">' in html
    assert 'id="main-content"' in html
    assert "toggleTheme" in html
    assert "function T(" in html
    assert "uiSetBusy" in html
    assert "window.demoReady=true" in html
    assert "测试页面" in html


def test_new_modules_stay_under_line_limit():
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent / "src"
    for name in ("frontend_components.py", "frontend_interactions.py", "frontend_shell.py"):
        assert len((root / "frontend" / name).read_text(encoding="utf-8").splitlines()) < 300
