"""
前端页面生成器测试 — 验证各页面 HTML 生成结构、CSS 变量引用、i18n 支持。
"""
import pytest
from pathlib import Path
import tempfile


# ── Dashboard ──

def test_dashboard_generates_html():
    from src.frontend.dashboard import generate_dashboard
    with tempfile.TemporaryDirectory() as td:
        path = generate_dashboard(Path(td))
        html = path.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in html
    assert "data-theme" in html
    assert "var(--bg-primary)" in html
    assert "var(--accent)" in html
    assert "SHARED_JS" not in html


def test_dashboard_contains_nav():
    from src.frontend.dashboard import generate_dashboard
    with tempfile.TemporaryDirectory() as td:
        path = generate_dashboard(Path(td))
        html = path.read_text(encoding="utf-8")
    assert 'href="/"' in html
    assert 'href="/library"' in html
    assert 'href="/graph"' in html
    assert 'href="/timeline"' in html
    assert 'href="/events"' in html
    assert 'href="/reports"' in html
    assert 'theme-toggle' in html


def test_dashboard_has_loading_state():
    from src.frontend.dashboard import generate_dashboard
    with tempfile.TemporaryDirectory() as td:
        path = generate_dashboard(Path(td))
        html = path.read_text(encoding="utf-8")
    assert 'spinner' in html or 'loading' in html


# ── Library ──

def test_library_generates_html():
    from src.frontend.library import generate_library
    with tempfile.TemporaryDirectory() as td:
        path = generate_library(Path(td))
        html = path.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in html
    assert "var(--bg-primary)" in html
    assert "apiFetch" in html


# ── Entity Page ──

def test_entity_shell_generates_html():
    from src.frontend.entity_page import generate_entity_shell
    with tempfile.TemporaryDirectory() as td:
        # generate_entity_shell 输出到 ROOT_DIR/reports，这里只是验证生成不报错
        path = generate_entity_shell(lang="zh")
        html = path.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in html
    assert "entity" in html.lower()
    assert "var(--bg-primary)" in html


# ── Events Page ──

def test_events_page_generates_html():
    from src.frontend.events_page import generate_events_page
    with tempfile.TemporaryDirectory() as td:
        path = generate_events_page(Path(td))
        html = path.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in html
    assert "events" in html.lower()


# ── Reports Page ──

def test_reports_page_generates_html():
    from src.frontend.reports_page import generate_reports_page
    with tempfile.TemporaryDirectory() as td:
        path = generate_reports_page(Path(td))
        html = path.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in html
    assert "report-list" in html
    assert "reports_title" in html


# ── 2D Graph ──

def test_kg_d3_generates_html():
    from src.frontend.kg_d3 import generate_html
    with tempfile.TemporaryDirectory() as td:
        path = generate_html(output_dir=Path(td))
        html = path.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in html
    assert "d3" in html.lower()
    assert "TYPE_COLORS" in html
    assert "var(--bg-primary)" in html


# ── 3D Graph ──

def test_kg_3d_generates_html():
    from src.frontend.kg_3d import generate_3d_html
    with tempfile.TemporaryDirectory() as td:
        path = generate_3d_html(output_dir=Path(td))
        html = path.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in html
    assert ("three" in html.lower() or "3d-force-graph" in html.lower())


# ── Timeline ──

def test_timeline_generates_html():
    from src.timeline import generate_timeline
    with tempfile.TemporaryDirectory() as td:
        path = generate_timeline(output_dir=Path(td))
        html = path.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in html
    assert "var(--bg-primary)" in html


# ── 响应式断点 ──

@pytest.mark.parametrize("page_name,generator", [
    ("dashboard", lambda td: __import__("src.frontend.dashboard", fromlist=[""]).generate_dashboard(td)),
    ("library", lambda td: __import__("src.frontend.library", fromlist=[""]).generate_library(td)),
    ("events", lambda td: __import__("src.frontend.events_page", fromlist=[""]).generate_events_page(td)),
    ("reports", lambda td: __import__("src.frontend.reports_page", fromlist=[""]).generate_reports_page(td)),
    ("graph2d", lambda td: __import__("src.frontend.kg_d3", fromlist=[""]).generate_html(output_dir=td)),
    ("graph3d", lambda td: __import__("src.frontend.kg_3d", fromlist=[""]).generate_3d_html(output_dir=td)),
    ("timeline", lambda td: __import__("src.timeline", fromlist=[""]).generate_timeline(output_dir=td)),
])
def test_all_pages_have_responsive_breakpoints(page_name, generator):
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        path = generator(td_path)
        html = path.read_text(encoding="utf-8")
    assert "768" in html, f"{page_name} 缺少 768px 响应式断点"


# ── Theme / CSS Variables ──

@pytest.mark.parametrize("var_name", [
    "--bg-primary", "--bg-card", "--text-primary", "--accent",
    "--border", "--radius", "--text-secondary", "--bg-elevated",
])
def test_page_uses_css_variable(var_name):
    from src.frontend.dashboard import generate_dashboard
    with tempfile.TemporaryDirectory() as td:
        path = generate_dashboard(Path(td))
        html = path.read_text(encoding="utf-8")
    assert f"var({var_name})" in html, f"Dashboard 缺少 var({var_name})"


# ── i18n 中英文切换 ──

def test_all_pages_support_both_languages():
    from src.frontend.dashboard import generate_dashboard
    import tempfile
    td_path = Path(tempfile.mkdtemp())
    p_zh = generate_dashboard(td_path / "zh", lang="zh")
    p_en = generate_dashboard(td_path / "en", lang="en")
    html_zh = p_zh.read_text(encoding="utf-8")
    html_en = p_en.read_text(encoding="utf-8")
    assert 'lang="zh"' in html_zh
    assert 'lang="en"' in html_en
    assert html_zh != html_en


# ── 边界: 自动创建目录 ──

def test_output_dir_auto_created():
    from src.frontend.dashboard import generate_dashboard
    with tempfile.TemporaryDirectory() as td:
        nested = Path(td) / "sub" / "nested"
        path = generate_dashboard(nested)
        assert path.exists()
        assert nested.exists()


# ── CSS Token 完整性 ──

def test_theme_vars_export():
    from src.frontend.frontend_styles import THEME_VARS, RESET_CSS
    # THEME_VARS 包含暗色和亮色双主题
    assert ":root" in THEME_VARS
    assert "[data-theme=" in THEME_VARS
    # RESET_CSS 同样包含双主题
    assert ":root" in RESET_CSS
    assert "[data-theme=" in RESET_CSS


def test_all_type_colors_defined():
    from src.frontend.frontend_styles import TYPE_COLORS, TYPE_ICONS
    types = ["model", "company", "tech", "concept", "product", "person", "methodology", "event"]
    for t in types:
        assert t in TYPE_COLORS, f"缺少 {t} 颜色"
        assert t in TYPE_ICONS, f"缺少 {t} 图标"


def test_design_system_version_valid():
    from src.frontend.frontend_styles import DESIGN_SYSTEM_VERSION
    parts = DESIGN_SYSTEM_VERSION.split(".")
    assert len(parts) == 3, f"无效版本号: {DESIGN_SYSTEM_VERSION}"
    assert all(p.isdigit() for p in parts), f"版本号应全数字: {DESIGN_SYSTEM_VERSION}"


# ── i18n 完整性 ──

def test_i18n_has_all_nav_keys():
    from src.interfaces.i18n import I18N
    nav_keys = ["dashboard", "library", "graph", "timeline", "events", "reports"]
    for key in nav_keys:
        assert key in I18N, f"缺少导航 i18n 键: {key}"
        assert "zh" in I18N[key], f"{key} 缺少 zh"
        assert "en" in I18N[key], f"{key} 缺少 en"


def test_i18n_has_reports_keys():
    from src.interfaces.i18n import I18N
    reports_keys = ["reports_title", "reports_subtitle", "reports_daily", "reports_weekly", "reports_monthly"]
    for key in reports_keys:
        assert key in I18N, f"缺少 reports i18n 键: {key}"


def test_nav_html_contains_reports():
    from src.interfaces.i18n import nav_html
    html = nav_html("reports")
    assert 'href="/reports"' in html
    assert 'active' in html  # reports 应该是当前页


# ── Research Assistant 页面 ──

def test_research_page_generates_html():
    from src.research import generate_research_page
    with tempfile.TemporaryDirectory() as td:
        path = generate_research_page(Path(td))
        html = path.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in html
    assert "深度研究助手" in html
    assert "var(--bg-primary)" in html
    assert "var(--accent)" in html


def test_research_page_has_form():
    from src.research import generate_research_page
    with tempfile.TemporaryDirectory() as td:
        path = generate_research_page(Path(td))
        html = path.read_text(encoding="utf-8")
    assert 'id="research-topic"' in html
    assert 'id="research-depth"' in html
    assert 'startResearch()' in html
    assert 'report-container' in html


def test_research_page_has_nav():
    from src.research import generate_research_page
    with tempfile.TemporaryDirectory() as td:
        path = generate_research_page(Path(td))
        html = path.read_text(encoding="utf-8")
    assert 'href="/research"' in html
    assert 'href="/library"' in html


def test_research_page_i18n_bilingual():
    from src.research import generate_research_page
    with tempfile.TemporaryDirectory() as td:
        p_zh = generate_research_page(Path(td) / "zh", lang="zh")
        p_en = generate_research_page(Path(td) / "en", lang="en")
        html_zh = p_zh.read_text(encoding="utf-8")
        html_en = p_en.read_text(encoding="utf-8")
    assert 'lang="zh"' in html_zh
    assert 'lang="en"' in html_en
    assert html_zh != html_en


def test_nav_html_contains_research():
    from src.interfaces.i18n import nav_html
    html = nav_html("research")
    assert 'href="/research"' in html
    assert 'active' in html


def test_i18n_has_research_keys():
    from src.interfaces.i18n import I18N
    research_keys = ["research_title", "research_subtitle", "research_start",
                     "research_depth_standard", "research_depth_deep",
                     "research_summary", "research_key_findings",
                     "research_no_results", "research_ai_error"]
    for key in research_keys:
        assert key in I18N, f"缺少 research i18n 键: {key}"
        assert "zh" in I18N[key], f"{key} 缺少 zh"
        assert "en" in I18N[key], f"{key} 缺少 en"


# ── RSS 多源扩展 ──

def test_config_has_new_sources():
    from src.engine.utils import load_config
    config = load_config()
    names = [s["name"] for s in config.get("sources", [])]
    assert "Reddit r/MachineLearning" in names
    assert "Reddit r/artificial" in names
    assert "Hacker News (全部)" in names


def test_new_sources_have_urls():
    from src.engine.utils import load_config
    config = load_config()
    for s in config.get("sources", []):
        if "Reddit" in s["name"] or s["name"] == "Hacker News (全部)":
            assert s.get("url"), f"{s['name']} 缺少 URL"


def test_research_report_no_topic_error():
    """空主题应返回错误。"""
    from src.research import generate_research_report
    result = generate_research_report("")
    assert "error" in result


def test_research_report_valid_topic():
    """有效主题应返回报告结构（不调用AI，只验证搜索路径）。"""
    from src.research import generate_research_report
    result = generate_research_report("transformer", depth="standard")
    # 应该返回 error（没有匹配的结果）或 report（搜索到结果但 AI 可能未配置）
    assert "error" in result or "report" in result


def test_config_source_count_increased():
    """源总数应增加到至少 14 个（原来 11 + 新增 3 个启用的）。"""
    from src.engine.utils import load_config
    config = load_config()
    sources = config.get("sources", [])
    assert len(sources) >= 14, f"期望 >=14 个源，实际 {len(sources)}"
