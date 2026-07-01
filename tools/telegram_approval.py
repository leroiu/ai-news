#!/usr/bin/env python3
"""
Telegram Approval Service — 轻量审批网关

PreToolUse Hook → Telegram Bot → 手机按钮 → 决策返回 → Hook 继续/暂停

独立于 AI News，通过环境变量配置，未来其他 Agent 可复用。

环境变量:
  TG_BOT_TOKEN      Telegram Bot Token (@BotFather 创建)
  TG_CHAT_ID        接收消息的 Chat ID
  TG_TIMEOUT        等待超时秒数 (默认 120)

用法:
  python telegram_approval.py --tool Bash --title "AI News" \\
       --task "生成日报" --details "写入 reports/2026-06-29.md"
"""

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime
from pathlib import Path
from typing import Optional

# ── Config ──

def _load_env():
    """加载环境变量，优先 .env 文件"""
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if env_file.exists():
        with open(env_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    if k.strip() not in os.environ:
                        os.environ[k.strip()] = v.strip()

_load_env()

BOT_TOKEN = os.getenv("TG_BOT_TOKEN", "")
CHAT_ID = os.getenv("TG_CHAT_ID", "")
TIMEOUT = int(os.getenv("TG_TIMEOUT", "120"))
TG_PROXY = os.getenv("TG_PROXY", "")
API = f"https://api.telegram.org/bot{BOT_TOKEN}"


def _proxy_handler() -> Optional[urllib.request.ProxyHandler]:
    if TG_PROXY:
        return urllib.request.ProxyHandler({"https": TG_PROXY, "http": TG_PROXY})
    return None


# ── Telegram API helpers ──

def _api(method: str, data: dict) -> dict:
    """调用 Telegram Bot API，返回 JSON。"""
    url = f"{API}/{method}"
    payload = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    opener = urllib.request.build_opener(_proxy_handler() or urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        return {"ok": False, "error": f"HTTP {e.code}: {body[:200]}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def send_message(text: str, buttons: list[list[tuple[str, str]]]) -> Optional[int]:
    """发送带 inline keyboard 的消息。返回 message_id。"""
    keyboard = [
        [{"text": label, "callback_data": cb_data} for label, cb_data in row]
        for row in buttons
    ]
    data = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "reply_markup": {"inline_keyboard": keyboard},
    }
    result = _api("sendMessage", data)
    if result.get("ok"):
        return result["result"]["message_id"]
    print(f"[TG] sendMessage failed: {result.get('error')}", file=sys.stderr)
    return None


def delete_message(msg_id: int):
    _api("deleteMessage", {"chat_id": CHAT_ID, "message_id": msg_id})


def answer_callback(query_id: str, text: str = ""):
    _api("answerCallbackQuery", {"callback_query_id": query_id, "text": text})


# ── Polling ──

def wait_for_callback(timeout: int = 120) -> Optional[dict]:
    """
    长轮询等待用户点击按钮。
    返回 callback_query 字典，超时返回 None。
    """
    last_update_id = 0
    deadline = time.time() + timeout

    while time.time() < deadline:
        remaining = max(1, int(deadline - time.time()))
        data = {
            "offset": last_update_id + 1,
            "timeout": min(30, remaining),
            "allowed_updates": ["callback_query"],
        }
        result = _api("getUpdates", data)

        if not result.get("ok"):
            time.sleep(2)
            continue

        for update in result.get("result", []):
            last_update_id = max(last_update_id, update["update_id"])
            if "callback_query" in update:
                return update["callback_query"]

        time.sleep(0.5)

    return None


# ── Main ──

CALLBACK_DECISIONS = {
    "continue":  ("allow", "User approved via Telegram"),
    "pause":     ("deny",  "User paused via Telegram"),
    "stop":      ("deny",  "User stopped via Telegram"),
    "explain":   ("deny",  "User wants explanation first — explain what you will do and why, then ask again"),
}


def main():
    parser = argparse.ArgumentParser(description="Telegram Approval Service")
    parser.add_argument("--tool", required=True, help="Tool name (Bash, Write, etc.)")
    parser.add_argument("--title", default="AI Workspace", help="Project name")
    parser.add_argument("--task", default="(unknown)", help="Current task")
    parser.add_argument("--details", default="", help="What Claude is trying to do")
    parser.add_argument("--timeout", type=int, default=TIMEOUT, help="Wait timeout in seconds")
    parser.add_argument("--outfile", default="", help="Write output JSON to this file (for gateway coordination)")
    parser.add_argument("--donefile", default="", help="Touch this file when done (for gateway coordination)")
    args = parser.parse_args()

    if not BOT_TOKEN or not CHAT_ID:
        # Fallback: no Telegram configured → auto-allow
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
            }
        }))
        return 0

    # ── Build message ──
    now = datetime.now().strftime("%H:%M")
    msg = (
        f"<b>Claude Code</b> 需要确认  <i>{now}</i>\n"
        f"\n"
        f"项目: <b>{args.title}</b>\n"
        f"操作: <code>{args.tool}</code>\n"
    )
    if args.task:
        msg += f"任务: {args.task}\n"
    if args.details:
        detail = args.details[:200]
        msg += f"\n<pre>{detail}</pre>"

    buttons = [
        [("▶ Continue", "continue"), ("⏸ Pause", "pause")],
        [("❌ Stop", "stop"), ("📄 Explain", "explain")],
    ]

    # ── Send ──
    msg_id = send_message(msg, buttons)
    # Signal gateway: msg_id available
    if args.outfile:
        with open(args.outfile, "w", encoding="utf-8") as f:
            json.dump({"msg_id": msg_id}, f)

    if msg_id is None:
        # Failed to send → auto-allow (don't block the tool)
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
            }
        }))
        return 0

    # ── Wait for response ──
    print(f"[TG] Waiting for response (timeout={args.timeout}s)...", file=sys.stderr)
    callback = wait_for_callback(timeout=args.timeout)

    if callback is None:
        # Timeout → pause (deny)
        try: delete_message(msg_id)
        except: pass
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": "Telegram approval timeout — user did not respond",
            }
        }))
        return 0

    # ── Parse decision ──
    cb_data = callback.get("data", "pause")
    decision, reason = CALLBACK_DECISIONS.get(cb_data, ("deny", f"Unknown callback: {cb_data}"))

    # Signal gateway: decision made
    if args.donefile:
        Path(args.donefile).touch()

    # Update message to show decision
    decision_labels = {
        "continue": "✅ 已通过", "pause": "⏸ 已暂停",
        "stop": "❌ 已停止", "explain": "📄 请解释",
    }
    label = decision_labels.get(cb_data, "已处理")
    try:
        _api("editMessageText", {
            "chat_id": CHAT_ID,
            "message_id": msg_id,
            "text": f"<s>{msg}</s>\n\n<b>{label}</b>",
            "parse_mode": "HTML",
        })
    except:
        try: delete_message(msg_id)
        except: pass

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
