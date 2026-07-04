"""统一页面外壳，将设计系统、导航、i18n 和共享交互组合为独立 HTML。"""
from dataclasses import dataclass

from .frontend_components import COMPONENT_CSS
from .frontend_interactions import COMPONENT_JS
from .frontend_styles import BASE_CSS, SHARED_JS
from .frontend_templates import PAGE_KINDS, TEMPLATE_CSS
from src.interfaces.i18n import i18n_js, nav_html, t


@dataclass(frozen=True)
class PageShell:
    """页面外壳配置；``body_html``、CSS 和 JS 均视为可信项目代码。"""

    title_key: str
    current_page: str
    body_html: str
    lang: str = "zh"
    extra_css: str = ""
    extra_js: str = ""
    body_class: str = ""
    wide: bool = False
    page_kind: str = "collection"


SHELL_CSS = """\
.skip-link{position:fixed;top:8px;left:8px;z-index:2000;padding:8px 12px;background:var(--accent);color:#fff;border-radius:var(--radius-sm);transform:translateY(-150%)}.skip-link:focus{transform:translateY(0)}
.app-shell{width:min(100%,var(--content-max));margin:0 auto;padding:24px}.app-shell--wide{width:min(100%,var(--content-max))}.app-shell__nav{position:relative;z-index:10;min-height:58px}.app-shell__main:focus{outline:none}
@media(max-width:768px){.app-shell{padding:16px}}@media(max-width:480px){.app-shell{padding:12px}}
"""


def render_page(shell: PageShell) -> str:
    """生成完整、自包含的 HTML 文档。"""
    if shell.page_kind not in PAGE_KINDS:
        raise ValueError(f"unsupported page kind: {shell.page_kind}")
    title = t(shell.title_key, shell.lang)
    width_class = " app-shell--wide" if shell.wide else ""
    body_class = f' class="{shell.body_class}"' if shell.body_class else ""
    return f'''<!DOCTYPE html>
<html lang="{shell.lang}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{title}</title>
<style>{BASE_CSS}{COMPONENT_CSS}{TEMPLATE_CSS}{SHELL_CSS}{shell.extra_css}</style>
</head>
<body{body_class}>
<a class="skip-link" href="#main-content">{t("skip_to_content", shell.lang)}</a>
<div class="app-shell{width_class}">
  <header class="app-shell__nav">{nav_html(shell.current_page)}</header>
  <main id="main-content" class="app-shell__main" data-page-kind="{shell.page_kind}" data-page-template="{shell.page_kind}" tabindex="-1">{shell.body_html}</main>
</div>
<script>{SHARED_JS}{i18n_js()}{COMPONENT_JS}{shell.extra_js}</script>
</body>
</html>'''
