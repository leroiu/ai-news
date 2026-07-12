"""抓取前的配置级来源校验。

本模块只校验本地配置，不访问网络。微信公众号 RSSHub 路由依赖
`biz_id`，因此在发起请求前检查其格式和 URL 一致性，避免把配置错误
误报为来源网络故障。
"""

from __future__ import annotations

import base64
import binascii
import re
from collections.abc import Mapping
from urllib.parse import urlparse


_BIZ_ID_PATTERN = re.compile(r"[A-Za-z0-9+/]+={0,2}")


def validate_source(source: Mapping[str, object]) -> str | None:
    """返回配置错误说明；合法配置返回 ``None``。

    目前只有 ``type: wechat`` 需要额外的结构化校验。其他类型仍保持
    现有抓取行为，避免本次任务扩大为全量配置重构。
    """
    if source.get("type", "rss") != "wechat":
        return None
    return validate_wechat_source(source)


def validate_wechat_source(source: Mapping[str, object]) -> str | None:
    """校验 RSSHub 微信 profile 路由与公众号 ``biz_id``。"""
    biz_id = source.get("biz_id")
    if not isinstance(biz_id, str) or not biz_id.strip():
        return "缺少 biz_id"
    biz_id = biz_id.strip()

    if not _BIZ_ID_PATTERN.fullmatch(biz_id):
        return "biz_id 不是有效的 Base64 字符串"
    try:
        decoded = base64.b64decode(biz_id, validate=True)
    except (ValueError, binascii.Error):
        return "biz_id Base64 解码失败"
    if not decoded:
        return "biz_id 解码结果为空"

    url = source.get("url")
    if not isinstance(url, str) or not url.strip():
        return "缺少 RSSHub URL"
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        return "RSSHub URL 必须是完整 HTTPS 地址"

    expected_path = f"/wechat/mp/profile/{biz_id}"
    if parsed.path.rstrip("/") != expected_path:
        return "RSSHub URL 与 biz_id 不匹配"
    return None
