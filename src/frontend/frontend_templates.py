"""五类页面模板的稳定结构。

模板只规定信息层级，不负责页面专属内容：
总览 overview、集合 collection、详情 detail、叙事 narrative、工作台 workbench。
"""
from html import escape


PAGE_KINDS = {"overview", "collection", "detail", "narrative", "workbench"}


def _kind(kind: str) -> str:
    if kind not in PAGE_KINDS:
        raise ValueError(f"unsupported page kind: {kind}")
    return kind


def page_template(kind: str, *, context_html: str, canvas_html: str,
                  aside_html: str = "") -> str:
    """生成“页面上下文 + 内容画布 + 可选辅助栏”的固定骨架。"""
    kind = _kind(kind)
    aside = f'<aside class="page-template__aside">{aside_html}</aside>' if aside_html else ""
    return (
        f'<div class="page-template page-template--{escape(kind)}" data-page-template="{escape(kind)}">'
        f'<section class="page-template__context">{context_html}</section>'
        f'<div class="page-template__layout"><main class="page-template__canvas">{canvas_html}</main>{aside}</div>'
        '</div>'
    )


def overview_page(context_html: str, canvas_html: str, aside_html: str = "") -> str:
    return page_template("overview", context_html=context_html, canvas_html=canvas_html, aside_html=aside_html)


def collection_page(context_html: str, canvas_html: str, aside_html: str = "") -> str:
    return page_template("collection", context_html=context_html, canvas_html=canvas_html, aside_html=aside_html)


def detail_page(context_html: str, canvas_html: str, aside_html: str = "") -> str:
    return page_template("detail", context_html=context_html, canvas_html=canvas_html, aside_html=aside_html)


def narrative_page(context_html: str, canvas_html: str, aside_html: str = "") -> str:
    return page_template("narrative", context_html=context_html, canvas_html=canvas_html, aside_html=aside_html)


def workbench_page(context_html: str, canvas_html: str, aside_html: str = "") -> str:
    return page_template("workbench", context_html=context_html, canvas_html=canvas_html, aside_html=aside_html)


TEMPLATE_CSS = """\
.page-template__context{margin-bottom:24px}.page-template__layout{display:grid;grid-template-columns:minmax(0,1fr);gap:16px}.page-template__canvas{min-width:0}.page-template__aside{min-width:0}.page-template--overview .page-template__layout,.page-template--workbench .page-template__layout{grid-template-columns:minmax(0,1fr) minmax(280px,.34fr)}.page-template--detail .page-template__canvas{max-width:920px}.page-template--narrative .page-template__canvas{max-width:1040px;margin:0 auto}.page-template--collection .page-template__canvas{width:100%}
@media(max-width:900px){.page-template--overview .page-template__layout,.page-template--workbench .page-template__layout{grid-template-columns:1fr}}
"""
