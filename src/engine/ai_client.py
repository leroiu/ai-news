"""
AI News - 共享 AI 客户端

支持双后端（DeepSeek / Kimi），通过环境变量 AI_PROVIDER 切换。
含指数退避重试，防止单次网络波动丢弃整批文章。

环境变量:
  AI_PROVIDER         deepseek (默认) | kimi
  DEEPSEEK_API_KEY    DeepSeek API Key
  DEEPSEEK_MODEL      DeepSeek 模型名 (默认 deepseek-chat)
  MOONSHOT_API_KEY    Kimi/Moonshot API Key
  MOONSHOT_BASE_URL   Kimi API 地址 (默认 https://api.moonshot.cn/v1)
  MOONSHOT_MODEL      Kimi 模型名 (默认 moonshot-v1-8k)
"""

import json
import os
import re
import time
from typing import Optional

from openai import OpenAI, APIStatusError, APITimeoutError, APIConnectionError

from .utils import log

RETRY_MAX = 3
RETRY_BASE_DELAY = 1.5  # 秒，指数退避: 1.5, 3, 6


# ============================================================
# JSON 解析
# ============================================================

def _parse_json(text: str) -> Optional[list[dict]]:
    """从 AI 响应中提取 JSON 数组。"""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    return None


# ============================================================
# Embedding Provider 注册表（可插拔）
# ============================================================

# 每个 provider 定义: api_key_env, base_url, default_model
# 新增 provider 只需在此注册，embed_texts() 零改动
EMBEDDING_PROVIDERS: dict[str, dict] = {
    "siliconflow": {
        "api_key_env": "SILICONFLOW_API_KEY",
        "base_url": "https://api.siliconflow.cn/v1",
        "default_model": "BAAI/bge-large-zh-v1.5",
    },
    "openai": {
        "api_key_env": "OPENAI_API_KEY",
        "base_url": "https://api.openai.com/v1",
        "default_model": "text-embedding-3-small",
    },
    "kimi": {
        "api_key_env": "MOONSHOT_API_KEY",
        "base_url": "https://api.moonshot.cn/v1",
        "default_model": "moonshot-v1",
    },
    # local: 通过 sentence-transformers 本地运行，无需 API Key
    # 使用时需 pip install sentence-transformers
    "local": {
        "api_key_env": None,
        "base_url": None,
        "default_model": "all-MiniLM-L6-v2",
    },
}


def embed_texts(
    texts: list[str],
    model: str | None = None,
    provider: str | None = None,
) -> list[list[float]] | None:
    """
    调用 Embedding API（可插拔 Provider），返回浮点向量列表。

    Provider 优先级: 参数 > EMBEDDING_PROVIDER 环境变量 > config.yaml embeddings.provider > "siliconflow"
    新增 Provider 只需在 EMBEDDING_PROVIDERS 注册表中添加条目，无需修改此函数。

    local provider 使用 sentence-transformers 本地推理，无需 API 调用。
    """
    import yaml
    from pathlib import Path

    # 读取 config
    cfg: dict = {}
    cfg_path = Path(__file__).resolve().parent.parent.parent / "config.yaml"
    if cfg_path.exists():
        cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    emb_cfg = cfg.get("embeddings", {})

    # 确定 provider
    if provider is None:
        provider = os.getenv("EMBEDDING_PROVIDER", emb_cfg.get("provider", "siliconflow"))
    provider = provider.lower().strip()

    # 查找注册表
    provider_def = EMBEDDING_PROVIDERS.get(provider)
    if provider_def is None:
        log.error(f"未知的 Embedding Provider: {provider}，可用: {list(EMBEDDING_PROVIDERS)}")
        return None

    # ── local provider: sentence-transformers ──
    if provider == "local":
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            log.error("local provider 需要 sentence-transformers: pip install sentence-transformers")
            return None
        m = model or provider_def["default_model"]
        log.info(f"本地嵌入模型加载中: {m}")
        encoder = SentenceTransformer(m)
        vectors = encoder.encode(texts, normalize_embeddings=True).tolist()
        return vectors

    # ── 远程 API provider ──
    api_key_env = provider_def["api_key_env"]
    api_key = os.getenv(api_key_env)
    if not api_key:
        log.error(f"未设置 {api_key_env} 环境变量，Embedding Provider '{provider}' 不可用")
        return None

    base_url = provider_def["base_url"]
    if model is None:
        model = os.getenv("EMBEDDING_MODEL", provider_def["default_model"])

    client = OpenAI(api_key=api_key, base_url=base_url, timeout=120.0)
    last_error: Exception | None = None

    for attempt in range(1, RETRY_MAX + 1):
        try:
            resp = client.embeddings.create(model=model, input=texts)
            vectors = [d.embedding for d in resp.data]
            return vectors

        except Exception as e:
            last_error = e
            if _is_retryable(e) and attempt < RETRY_MAX:
                delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                log.warning(f"Embedding API ({provider}) 失败 (尝试 {attempt}/{RETRY_MAX}): {e}，{delay:.1f}s 后重试")
                time.sleep(delay)
            else:
                log.error(f"Embedding API ({provider}) 失败 (不可重试): {e}")
                break

    log.error(f"Embedding API ({provider}) 最终失败，已重试 {RETRY_MAX} 次: {last_error}")
    return None


# ============================================================
# 重试判断
# ============================================================

def _is_retryable(error: Exception) -> bool:
    """判断是否可重试的错误（网络/服务端问题，非认证/参数错误）。"""
    if isinstance(error, (APITimeoutError, APIConnectionError)):
        return True
    if isinstance(error, APIStatusError):
        return error.status_code >= 500 or error.status_code == 429
    for attr in ("status_code", "status"):
        code = getattr(error, attr, None)
        if code is not None and (code >= 500 or code == 429):
            return True
    return False


# ============================================================
# 主调用入口
# ============================================================

def call_ai(
    system_prompt: str,
    user_prompt: str,
    model: str | None = None,
    temperature: float = 0.1,
    max_tokens: int = 4096,
) -> Optional[list[dict]]:
    """
    调用 AI API（含重试 + 自动路由），返回解析后的 JSON 列表。

    根据 AI_PROVIDER 环境变量自动选择后端:
      - deepseek: DeepSeek API (OpenAI 兼容)
      - kimi:     Moonshot/Kimi API (OpenAI 兼容)
    """
    provider = os.getenv("AI_PROVIDER", "deepseek").lower().strip()

    if provider == "kimi":
        return _call_openai_compatible(
            system_prompt, user_prompt, model, temperature, max_tokens,
            api_key_env="MOONSHOT_API_KEY",
            base_url_env="MOONSHOT_BASE_URL",
            default_base="https://api.moonshot.cn/v1",
            model_env="MOONSHOT_MODEL",
            default_model="moonshot-v1-8k",
            label="Kimi",
        )
    else:
        # deepseek (默认)
        return _call_openai_compatible(
            system_prompt, user_prompt, model, temperature, max_tokens,
            api_key_env="DEEPSEEK_API_KEY",
            base_url_env="DEEPSEEK_BASE_URL",
            default_base="https://api.deepseek.com",
            model_env="DEEPSEEK_MODEL",
            default_model="deepseek-chat",
            label="DeepSeek",
        )


# ============================================================
# OpenAI 兼容后端通用调用
# ============================================================

def _call_openai_compatible(
    system_prompt: str,
    user_prompt: str,
    model: str | None,
    temperature: float,
    max_tokens: int,
    api_key_env: str,
    base_url_env: str,
    default_base: str,
    model_env: str,
    default_model: str,
    label: str,
) -> Optional[list[dict]]:
    """OpenAI 兼容 API 通用调用（含指数退避重试）。"""
    api_key = os.getenv(api_key_env)
    if not api_key:
        log.error(f"未设置 {api_key_env} 环境变量")
        return None

    if model is None:
        model = os.getenv(model_env, default_model)

    base_url = os.getenv(base_url_env, default_base)
    client = OpenAI(api_key=api_key, base_url=base_url, timeout=120.0)
    last_error: Optional[Exception] = None

    for attempt in range(1, RETRY_MAX + 1):
        try:
            resp = client.chat.completions.create(
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            text = resp.choices[0].message.content or ""
            result = _parse_json(text)
            if result is None:
                log.warning(f"{label} 返回无法解析 (尝试 {attempt}/{RETRY_MAX})")
                if attempt < RETRY_MAX:
                    time.sleep(RETRY_BASE_DELAY * (2 ** (attempt - 1)))
                    continue
            return result

        except Exception as e:
            last_error = e
            if _is_retryable(e) and attempt < RETRY_MAX:
                delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                log.warning(f"{label} 调用失败 (尝试 {attempt}/{RETRY_MAX}): {e}，{delay:.1f}s 后重试")
                time.sleep(delay)
            else:
                log.error(f"{label} 调用失败 (不可重试): {e}")
                break

    log.error(f"{label} 调用最终失败，已重试 {RETRY_MAX} 次: {last_error}")
    return None
