"""
AI 观察室 — 登录/注册页面
纯 Vanilla JS，独立 HTML。
"""
from pathlib import Path
from src.engine.utils import ROOT_DIR
from .frontend_styles import THEME_VARS, ANIMATION_CSS, RESPONSIVE_CSS


def generate_auth_page(lang: str = "zh") -> Path:
    html = _build_html(lang)
    output = ROOT_DIR / "reports" / "auth.html"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")
    return output


def _build_html(lang: str = "zh") -> str:
    T = {
        "zh": {"login": "登录", "register": "注册", "username": "用户名",
               "password": "密码", "email": "邮箱（选填）",
               "btn_login": "登录", "btn_register": "注册",
               "switch_login": "已有账号？登录", "switch_register": "没有账号？注册",
               "title": "AI 观察室"},
        "en": {"login": "Sign In", "register": "Sign Up", "username": "Username",
               "password": "Password", "email": "Email (optional)",
               "btn_login": "Sign In", "btn_register": "Sign Up",
               "switch_login": "Have an account? Sign In",
               "switch_register": "No account? Sign Up",
               "title": "AI Observatory"},
    }
    t = T.get(lang, T["zh"])
    return f'''<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{t["title"]} — {t["login"]}</title>
<style>
{THEME_VARS}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:var(--font-sans);background:var(--bg-primary);color:var(--text-primary);min-height:100vh;display:flex;align-items:center;justify-content:center}}
.auth-card{{width:100%;max-width:400px;padding:40px 32px;background:var(--bg-card);border:1px solid var(--border);border-radius:12px}}
.auth-card h1{{font-family:var(--font-display);font-size:28px;font-weight:650;text-align:center;margin-bottom:28px;letter-spacing:-.02em}}
.form-group{{margin-bottom:16px}}
.form-group label{{display:block;font-size:12px;color:var(--text-secondary);margin-bottom:6px;font-weight:600}}
.form-group input{{width:100%;padding:10px 12px;border:1px solid var(--border);border-radius:6px;background:var(--bg-primary);color:var(--text-primary);font:inherit;font-size:14px;transition:border-color .15s}}
.form-group input:focus{{outline:none;border-color:var(--accent)}}
.btn-primary{{width:100%;padding:11px;margin-top:8px;border:none;border-radius:6px;background:var(--accent);color:#fff;font:inherit;font-size:14px;font-weight:650;cursor:pointer;transition:filter .15s}}
.btn-primary:hover{{filter:brightness(1.12)}}
.btn-primary:disabled{{opacity:.6;cursor:not-allowed}}
.auth-error{{margin-top:12px;padding:8px 12px;border-radius:6px;background:var(--danger-subtle, #ff6b6b22);color:var(--danger);font-size:12px;display:none}}
.auth-error.show{{display:block}}
.switch-text{{text-align:center;margin-top:20px;font-size:13px;color:var(--text-secondary)}}
.switch-text a{{color:var(--accent);text-decoration:none;cursor:pointer}}
.switch-text a:hover{{text-decoration:underline}}
.auth-tabs{{display:flex;margin-bottom:24px;border-bottom:1px solid var(--border)}}
.auth-tab{{flex:1;padding:10px;text-align:center;font-size:14px;font-weight:600;color:var(--text-secondary);cursor:pointer;border-bottom:2px solid transparent;background:none;border-top:none;border-left:none;border-right:none;transition:color .15s,border-color .15s}}
.auth-tab.active{{color:var(--accent);border-bottom-color:var(--accent)}}
.back-link{{text-align:center;margin-top:16px;font-size:12px}}
.back-link a{{color:var(--text-muted);text-decoration:none}}
.back-link a:hover{{color:var(--accent)}}
{ANIMATION_CSS}
{RESPONSIVE_CSS}
</style>
</head>
<body>
<div class="auth-card">
<h1>{t["title"]}</h1>
<div class="auth-tabs">
<button class="auth-tab active" onclick="switchTab('login')">{t["login"]}</button>
<button class="auth-tab" onclick="switchTab('register')">{t["register"]}</button>
</div>
<div class="auth-error" id="error"></div>

<form id="login-form" onsubmit="handleLogin(event)">
<div class="form-group"><label>{t["username"]}</label><input id="login-username" autocomplete="username" required></div>
<div class="form-group"><label>{t["password"]}</label><input id="login-password" type="password" autocomplete="current-password" required></div>
<button type="submit" class="btn-primary">{t["btn_login"]}</button>
</form>

<form id="register-form" onsubmit="handleRegister(event)" style="display:none">
<div class="form-group"><label>{t["username"]}</label><input id="reg-username" autocomplete="username" required minlength="2"></div>
<div class="form-group"><label>{t["email"]}</label><input id="reg-email" type="email" autocomplete="email"></div>
<div class="form-group"><label>{t["password"]}</label><input id="reg-password" type="password" autocomplete="new-password" required minlength="6"></div>
<button type="submit" class="btn-primary">{t["btn_register"]}</button>
</form>

<div class="back-link"><a href="/">{t["title"]} 首页</a></div>
</div>

<script>
const API = "/api/auth";
let activeTab = "login";

function switchTab(tab) {{
  activeTab = tab;
  document.querySelectorAll(".auth-tab").forEach(function(el) {{
    el.classList.toggle("active", el.textContent === (tab === "login" ? "{t["login"]}" : "{t["register"]}"));
  }});
  document.getElementById("login-form").style.display = tab === "login" ? "" : "none";
  document.getElementById("register-form").style.display = tab === "register" ? "" : "none";
  hideError();
}}

function showError(msg) {{
  var el = document.getElementById("error");
  el.textContent = msg;
  el.classList.add("show");
}}

function hideError() {{
  var el = document.getElementById("error");
  el.classList.remove("show");
}}

async function handleLogin(e) {{
  e.preventDefault();
  hideError();
  var btn = e.target.querySelector("button");
  btn.disabled = true;
  try {{
    var resp = await fetch(API + "/login", {{
      method: "POST",
      headers: {{"Content-Type": "application/json"}},
      body: JSON.stringify({{
        username: document.getElementById("login-username").value,
        password: document.getElementById("login-password").value,
      }}),
    }});
    var data = await resp.json();
    if (!resp.ok) {{
      var err = data.error || data;
      throw new Error(err.message || err.detail || "Login failed");
    }}
    localStorage.setItem("ai_obs_token", data.access_token);
    localStorage.setItem("ai_obs_user", JSON.stringify(data.user));
    window.location.href = "/";
  }} catch(err) {{
    showError(err.message);
  }} finally {{
    btn.disabled = false;
  }}
}}

async function handleRegister(e) {{
  e.preventDefault();
  hideError();
  var btn = e.target.querySelector("button");
  btn.disabled = true;
  try {{
    var resp = await fetch(API + "/register", {{
      method: "POST",
      headers: {{"Content-Type": "application/json"}},
      body: JSON.stringify({{
        username: document.getElementById("reg-username").value,
        password: document.getElementById("reg-password").value,
        email: document.getElementById("reg-email").value,
      }}),
    }});
    var data = await resp.json();
    if (!resp.ok) {{
      var err = data.error || data;
      throw new Error(err.message || err.detail || "Registration failed");
    }}
    localStorage.setItem("ai_obs_token", data.access_token);
    localStorage.setItem("ai_obs_user", JSON.stringify(data.user));
    window.location.href = "/";
  }} catch(err) {{
    showError(err.message);
  }} finally {{
    btn.disabled = false;
  }}
}}

// URL hash 决定默认 tab
if (window.location.hash === "#register" || window.location.pathname === "/register") {{
  switchTab("register");
}}
</script>
</body>
</html>'''