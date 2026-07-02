"""轻量 HTML 组件层。

组件只负责稳定的结构、语义和样式，不负责数据获取。传入 ``content``、
``actions`` 等 ``*_html`` 参数的内容必须由调用方保证可信；普通文字统一转义。
"""
from html import escape
from typing import Mapping, Optional


COMPONENT_CSS = """\
.ui-page-header{display:flex;justify-content:space-between;gap:24px;align-items:flex-end;margin:8px 0 24px}.ui-page-header__eyebrow{margin-bottom:6px;color:var(--accent);font-size:11px;font-weight:700;letter-spacing:.12em;text-transform:uppercase}.ui-page-header h1{color:var(--text-primary);font-size:28px;line-height:1.2}.ui-page-header__summary{max-width:680px;margin-top:8px;color:var(--text-secondary);font-size:14px;line-height:1.65}.ui-page-header__actions{display:flex;gap:8px;flex-wrap:wrap}
.ui-card{background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius);box-shadow:var(--shadow)}.ui-card__header{display:flex;justify-content:space-between;gap:12px;align-items:center;padding:16px 20px;border-bottom:1px solid var(--border)}.ui-card__title{font-size:15px;color:var(--text-primary)}.ui-card__body{padding:20px}.ui-card--interactive{transition:transform .18s,border-color .18s,box-shadow .18s}.ui-card--interactive:hover{transform:translateY(-2px);border-color:var(--accent);box-shadow:var(--shadow)}
.ui-button{display:inline-flex;min-height:34px;padding:7px 14px;align-items:center;justify-content:center;gap:6px;border:1px solid transparent;border-radius:var(--radius-sm);font:inherit;font-size:12px;font-weight:600;cursor:pointer;text-decoration:none;transition:background .15s,border-color .15s,transform .15s}.ui-button:hover{transform:translateY(-1px)}.ui-button:focus-visible{outline:2px solid var(--accent);outline-offset:2px}.ui-button:disabled{opacity:.5;cursor:not-allowed;transform:none}.ui-button--primary{background:var(--accent);color:#fff}.ui-button--secondary{background:var(--bg-elevated);border-color:var(--border);color:var(--text-primary)}.ui-button--ghost{background:transparent;border-color:var(--border);color:var(--text-secondary)}.ui-button--danger{background:var(--danger);color:#fff}.ui-button--small{min-height:28px;padding:4px 10px;font-size:11px}.ui-button--large{min-height:42px;padding:10px 18px;font-size:14px}
.ui-badge{display:inline-flex;padding:3px 8px;align-items:center;gap:5px;border-radius:999px;background:var(--bg-elevated);color:var(--text-secondary);font-size:11px;font-weight:600}.ui-badge--accent{background:var(--accent-subtle);color:var(--accent)}.ui-badge--success{color:var(--success)}.ui-badge--warning{color:var(--warning)}.ui-badge--danger{color:var(--danger)}
.ui-stat{min-width:120px}.ui-stat__value{display:block;color:var(--text-primary);font-size:26px;font-weight:750;line-height:1.15}.ui-stat__label{display:block;margin-top:4px;color:var(--text-secondary);font-size:11px}.ui-stat__context{display:block;margin-top:6px;color:var(--text-muted);font-size:10px}
.ui-filter-bar{display:flex;gap:10px;align-items:center;padding:12px;background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius)}.ui-filter-bar__controls{display:flex;flex:1;gap:10px;align-items:center;flex-wrap:wrap}.ui-filter-bar__count{color:var(--text-secondary);font-size:11px;white-space:nowrap}
.ui-empty{padding:56px 24px;text-align:center;color:var(--text-secondary)}.ui-empty__icon{margin-bottom:12px;font-size:32px}.ui-empty h3{margin-bottom:6px;color:var(--text-primary);font-size:16px}.ui-empty p{max-width:480px;margin:0 auto;line-height:1.6}.ui-empty__action{margin-top:18px}
.ui-section{margin-top:24px}.ui-section__header{display:flex;justify-content:space-between;gap:12px;align-items:center;margin-bottom:12px}.ui-section__title{font-size:16px;color:var(--text-primary)}.ui-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px}.ui-stack{display:flex;flex-direction:column;gap:16px}
.ui-toast-region{position:fixed;right:20px;bottom:20px;z-index:1000;display:flex;max-width:min(360px,calc(100vw - 40px));flex-direction:column;gap:8px}.ui-toast{padding:11px 14px;background:var(--bg-elevated);border:1px solid var(--border);border-left:3px solid var(--accent);border-radius:var(--radius-sm);box-shadow:var(--shadow);color:var(--text-primary);font-size:12px}.ui-toast--success{border-left-color:var(--success)}.ui-toast--warning{border-left-color:var(--warning)}.ui-toast--danger{border-left-color:var(--danger)}
.ui-favorite{border-color:var(--border);background:var(--bg-elevated);color:var(--text-secondary)}.ui-favorite.is-favorited,.ui-favorite[aria-pressed="true"]{border-color:var(--warning);background:#e3b34122;color:var(--warning)}
.intel-rating{display:inline-flex;align-items:center;gap:7px}.intel-rating__stars{color:var(--warning);letter-spacing:1px}.intel-rating__label{color:var(--text-secondary);font-size:10px}.intel-source{display:flex;align-items:center;gap:6px;flex-wrap:wrap;color:var(--text-muted);font-size:11px}.intel-source a{color:var(--accent);text-decoration:none}.intel-evidence{display:inline-flex;padding:2px 7px;border:1px solid var(--border);border-radius:999px;font-size:10px;font-weight:650}.intel-evidence--fact{color:var(--success)}.intel-evidence--analysis{color:var(--accent)}.intel-evidence--inference{color:var(--warning)}.intel-evidence--advice{color:var(--text-secondary)}.intel-topic{display:inline-flex;padding:3px 8px;border-radius:999px;background:var(--bg-elevated);color:var(--text-secondary);font-size:10px}.ui-state{padding:28px 20px;text-align:center;border:1px dashed var(--border);border-radius:var(--radius);color:var(--text-secondary)}.ui-state__icon{margin-bottom:8px;font-size:24px}.ui-state strong{display:block;margin-bottom:5px;color:var(--text-primary);font-size:14px}.ui-state p{max-width:520px;margin:auto;font-size:12px;line-height:1.6}.ui-state--pending{border-style:solid;border-left:3px solid var(--warning);text-align:left}.ui-state--error{border-color:var(--danger)}.ui-state--unavailable{opacity:.8}
@media(max-width:768px){.ui-page-header{align-items:flex-start;flex-direction:column}.ui-page-header__actions{width:100%}.ui-filter-bar{align-items:stretch;flex-direction:column}.ui-filter-bar__count{align-self:flex-start}.ui-grid{grid-template-columns:1fr}}
@media(prefers-reduced-motion:reduce){.ui-card--interactive,.ui-button{transition:none}.ui-card--interactive:hover,.ui-button:hover{transform:none}}
"""


def _text(value: object) -> str:
    return escape(str(value), quote=True)


def _attrs(values: Optional[Mapping[str, object]] = None) -> str:
    if not values:
        return ""
    parts = []
    for name, value in values.items():
        safe_name = name.replace("_", "-")
        if value is True:
            parts.append(safe_name)
        elif value not in (False, None):
            parts.append(f'{safe_name}="{_text(value)}"')
    return (" " + " ".join(parts)) if parts else ""


def button(label: str, *, variant: str = "primary", size: str = "medium",
           attrs: Optional[Mapping[str, object]] = None) -> str:
    """生成按钮；事件、ARIA 和 data 属性通过 ``attrs`` 传入。"""
    variants = {"primary", "secondary", "ghost", "danger"}
    sizes = {"small", "medium", "large"}
    if variant not in variants or size not in sizes:
        raise ValueError("unsupported button variant or size")
    classes = f"ui-button ui-button--{variant} ui-button--{size}"
    return f'<button class="{classes}"{_attrs(attrs)}>{_text(label)}</button>'


def bookmark_action(item_type: str, item_id: str, title: str = "", href: str = "") -> str:
    """生成统一收藏按钮；持久化逻辑由 ``uiToggleFavorite`` 处理。"""
    return (
        '<button class="ui-button ui-button--small ui-favorite" aria-pressed="false" '
        f'data-favorite-type="{_text(item_type)}" data-favorite-id="{_text(item_id)}" '
        f'data-favorite-title="{_text(title)}" data-favorite-href="{_text(href)}" '
        "onclick=\"uiToggleFavorite({type:this.dataset.favoriteType,id:this.dataset.favoriteId,title:this.dataset.favoriteTitle,href:this.dataset.favoriteHref}, this)\">收藏</button>"
    )


favorite_button = bookmark_action


def editorial_rating(value: int, *, explanation: str = "") -> str:
    """平台编辑评级；始终显式标注主体，避免被误解为用户评分。"""
    score = max(0, min(5, int(value or 0)))
    label = explanation or "平台重要性评级"
    return (f'<span class="intel-rating" aria-label="{_text(label)} {score}/5" title="{_text(label)}">'
            f'<span class="intel-rating__stars">{"★" * score}{"☆" * (5-score)}</span>'
            f'<span class="intel-rating__label">{_text(label)}</span></span>')


def source_meta(source: str, *, published: str = "", href: str = "") -> str:
    name = f'<a href="{_text(href)}" target="_blank" rel="noopener">{_text(source)}</a>' if href else _text(source)
    date = f'<time datetime="{_text(published)}">{_text(published)}</time>' if published else ""
    sep = '<span aria-hidden="true">·</span>' if name and date else ""
    return f'<div class="intel-source">{name}{sep}{date}</div>'


def evidence_label(kind: str, label: str = "") -> str:
    kinds = {"fact": "事实", "analysis": "分析", "inference": "推测", "advice": "建议"}
    if kind not in kinds:
        raise ValueError("unsupported evidence kind")
    return f'<span class="intel-evidence intel-evidence--{kind}">{_text(label or kinds[kind])}</span>'


def topic_tag(label: str) -> str:
    return f'<span class="intel-topic">{_text(label)}</span>'


def state_panel(state: str, title: str, *, description: str = "", icon: str = "") -> str:
    states = {"loading", "empty", "error", "processing", "pending", "unavailable"}
    if state not in states:
        raise ValueError("unsupported state")
    icons = {"loading":"◌", "empty":"◇", "error":"⚠", "processing":"◌", "pending":"◷", "unavailable":"—"}
    desc = f'<p>{_text(description)}</p>' if description else ""
    return f'<div class="ui-state ui-state--{state}" role="status"><div class="ui-state__icon" aria-hidden="true">{_text(icon or icons[state])}</div><strong>{_text(title)}</strong>{desc}</div>'


def badge(label: str, *, tone: str = "neutral", icon: str = "") -> str:
    tones = {"neutral", "accent", "success", "warning", "danger"}
    if tone not in tones:
        raise ValueError("unsupported badge tone")
    icon_html = f'<span aria-hidden="true">{_text(icon)}</span>' if icon else ""
    return f'<span class="ui-badge ui-badge--{tone}">{icon_html}<span>{_text(label)}</span></span>'


def card(content_html: str, *, title: str = "", actions_html: str = "",
         interactive: bool = False, attrs: Optional[Mapping[str, object]] = None,
         title_key: str = "") -> str:
    header = ""
    if title or actions_html:
        title_attr = _attrs({"data_i18n": title_key}) if title_key else ""
        header = f'<header class="ui-card__header"><h2 class="ui-card__title"{title_attr}>{_text(title)}</h2>{actions_html}</header>'
    modifier = " ui-card--interactive" if interactive else ""
    return f'<article class="ui-card{modifier}"{_attrs(attrs)}>{header}<div class="ui-card__body">{content_html}</div></article>'


def stat(value: object, label: str, *, context: str = "") -> str:
    extra = f'<span class="ui-stat__context">{_text(context)}</span>' if context else ""
    return f'<div class="ui-stat"><strong class="ui-stat__value">{_text(value)}</strong><span class="ui-stat__label">{_text(label)}</span>{extra}</div>'


def page_header(title: str, *, summary: str = "", eyebrow: str = "",
                actions_html: str = "", title_key: str = "",
                summary_key: str = "", eyebrow_key: str = "") -> str:
    eyebrow_attr = _attrs({"data_i18n": eyebrow_key}) if eyebrow_key else ""
    title_attr = _attrs({"data_i18n": title_key}) if title_key else ""
    summary_attr = _attrs({"data_i18n": summary_key}) if summary_key else ""
    eyebrow_html = f'<div class="ui-page-header__eyebrow"{eyebrow_attr}>{_text(eyebrow)}</div>' if eyebrow else ""
    summary_html = f'<p class="ui-page-header__summary"{summary_attr}>{_text(summary)}</p>' if summary else ""
    actions = f'<div class="ui-page-header__actions">{actions_html}</div>' if actions_html else ""
    return f'<header class="ui-page-header"><div>{eyebrow_html}<h1{title_attr}>{_text(title)}</h1>{summary_html}</div>{actions}</header>'


def filter_bar(controls_html: str, *, count_text: str = "") -> str:
    count = f'<span class="ui-filter-bar__count" aria-live="polite">{_text(count_text)}</span>' if count_text else ""
    return f'<div class="ui-filter-bar"><div class="ui-filter-bar__controls">{controls_html}</div>{count}</div>'


def empty_state(title: str, *, description: str = "", icon: str = "◇",
                action_html: str = "") -> str:
    desc = f'<p>{_text(description)}</p>' if description else ""
    action = f'<div class="ui-empty__action">{action_html}</div>' if action_html else ""
    return f'<div class="ui-empty" role="status"><div class="ui-empty__icon" aria-hidden="true">{_text(icon)}</div><h3>{_text(title)}</h3>{desc}{action}</div>'


def section(title: str, content_html: str, *, actions_html: str = "") -> str:
    return f'<section class="ui-section"><header class="ui-section__header"><h2 class="ui-section__title">{_text(title)}</h2>{actions_html}</header>{content_html}</section>'
