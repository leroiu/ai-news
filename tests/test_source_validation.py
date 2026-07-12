"""数据源配置校验测试。"""

import asyncio

from src.engine import fetcher
from src.engine.source_validation import validate_source, validate_wechat_source
from src.engine.utils import load_config


VALID_BIZ_ID = "MzA3NTI1MjYwOQ=="
VALID_URL = f"https://rsshub.app/wechat/mp/profile/{VALID_BIZ_ID}"


def test_valid_wechat_source_passes_validation():
    source = {"type": "wechat", "biz_id": VALID_BIZ_ID, "url": VALID_URL}
    assert validate_wechat_source(source) is None


def test_wechat_source_rejects_missing_biz_id():
    source = {"type": "wechat", "url": VALID_URL}
    assert validate_wechat_source(source) == "缺少 biz_id"


def test_wechat_source_rejects_invalid_biz_id():
    source = {"type": "wechat", "biz_id": "not a base64 id", "url": VALID_URL}
    assert validate_wechat_source(source) == "biz_id 不是有效的 Base64 字符串"


def test_wechat_source_rejects_bad_base64_padding():
    source = {"type": "wechat", "biz_id": "abc", "url": "https://rsshub.app/wechat/mp/profile/abc"}
    assert validate_wechat_source(source) == "biz_id Base64 解码失败"


def test_wechat_source_rejects_url_biz_id_mismatch():
    source = {"type": "wechat", "biz_id": VALID_BIZ_ID, "url": "https://rsshub.app/wechat/mp/profile/other"}
    assert validate_source(source) == "RSSHub URL 与 biz_id 不匹配"


def test_existing_wechat_config_is_structurally_valid():
    config = load_config()
    wechat_sources = [source for source in config["sources"] if source.get("type") == "wechat"]
    assert len(wechat_sources) == 4
    assert all(validate_source(source) is None for source in wechat_sources)


def test_fetch_all_skips_invalid_wechat_config_without_network(monkeypatch):
    health = {}
    monkeypatch.setattr(fetcher, "_update_source_health", health.update)
    config = {
        "sources": [
            {
                "name": "Invalid WeChat",
                "type": "wechat",
                "biz_id": "invalid*",
                "url": "https://rsshub.app/wechat/mp/profile/invalid*",
                "enabled": True,
            }
        ]
    }

    assert asyncio.run(fetcher.fetch_all(config)) == []
    assert health["Invalid WeChat"][0] is False
    assert "配置无效" in health["Invalid WeChat"][1]
