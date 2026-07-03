"""轻量前端组件层测试。"""
from src.frontend.frontend_components import (
    COMPONENT_CSS, badge, button, card, empty_state, filter_bar,
    favorite_button, page_header, section, stat, editorial_rating,
    source_meta, evidence_label, topic_tag, state_panel,
)
from src.frontend.frontend_interactions import COMPONENT_JS
from src.frontend.frontend_styles import SHARED_JS
from src.frontend.frontend_shell import PageShell, render_page
from src.frontend.frontend_templates import PAGE_KINDS, page_template


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
    for name in ("uiToggleFavorite", "uiFavoriteStore", "uiFavoriteKey", "uiPersonalMetaStore", "uiGetPersonalMeta", "uiUpdatePersonalMeta"):
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
    assert 'data-page-template="collection"' in html


def test_five_page_templates_have_stable_structure():
    assert PAGE_KINDS == {"overview", "collection", "detail", "narrative", "workbench"}
    for kind in PAGE_KINDS:
        html = page_template(kind, context_html="context", canvas_html="canvas", aside_html="aside")
        assert f'data-page-template="{kind}"' in html
        assert "page-template__context" in html
        assert "page-template__canvas" in html
        assert "page-template__aside" in html


def test_intelligence_components_are_semantic():
    assert "平台重要性评级" in editorial_rating(4)
    assert "★★★★☆" in editorial_rating(4)
    assert 'target="_blank"' in source_meta("Source", published="2026-07-02", href="https://example.com")
    assert "intel-evidence--fact" in evidence_label("fact")
    assert "intel-topic" in topic_tag("Agent")
    assert 'data-favorite-href="/entity/openai"' in favorite_button("entity", "openai", "OpenAI", "/entity/openai")


def test_all_six_states_have_standard_markup():
    for state in ("loading", "empty", "error", "processing", "pending", "unavailable"):
        html = state_panel(state, state, description="desc")
        assert f'data-ui-state="{state}"' in html
        assert f"ui-state--{state}" in html


def test_new_modules_stay_under_line_limit():
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent / "src"
    for name in ("frontend_components.py", "frontend_interactions.py", "frontend_shell.py"):
        assert len((root / "frontend" / name).read_text(encoding="utf-8").splitlines()) < 300
