# AI 观察室 — 部署指南

> 公开版：不含 IP、密钥、账号等敏感信息。
> 私有部署状态见 `.private/DEPLOYMENT_STATUS.md`（不入 git）。

---

## 1. 技术栈

| 层 | 技术 |
|----|------|
| Web 服务器 | Nginx（反向代理 + 静态文件） |
| 应用服务 | Uvicorn (FastAPI) + systemd |
| 数据库 | SQLite（WAL 模式） |
| Python | 3.10+，虚拟环境 |
| 包管理 | uv（推荐）或 pip |
| AI | 多 LLM 提供商（OpenAI / Anthropic / SiliconFlow） |

---

## 2. 服务器最低要求

| 项 | 建议 | 最低 |
|----|------|------|
| CPU | 2 核 | 1 核 |
| 内存 | 2 GB | 1 GB |
| 磁盘 | 40 GB | 20 GB |
| 带宽 | 3 Mbps | 1 Mbps |
| 系统 | Ubuntu 22.04+ | Ubuntu 20.04+ |

---

## 3. 初始化服务器

```bash
# 更新系统
apt update && apt upgrade -y

# 安装依赖
apt install -y curl git build-essential python3-pip python3-venv nginx

# 创建应用用户（不要用 root）
useradd -m -s /bin/bash aiobserver
```

---

## 4. 部署应用

```bash
# 克隆代码
cd /home/aiobserver
git clone https://github.com/leroiu/ai-news.git app
cd app

# 创建虚拟环境 + 安装依赖
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 初始化数据库
.venv/bin/python -c "from src.engine.db_core import init_db; init_db()"

# 生成前端静态页面
.venv/bin/python -m src.frontend.generate_all

# 启动应用
.venv/bin/python -m uvicorn src.api.api:app --host 127.0.0.1 --port 8765
```

---

## 5. systemd 服务

创建 `/etc/systemd/system/ai-news.service`：

```ini
[Unit]
Description=AI Observatory API
After=network.target

[Service]
User=aiobserver
WorkingDirectory=/home/aiobserver/app
ExecStart=/home/aiobserver/app/.venv/bin/uvicorn src.api.api:app --host 127.0.0.1 --port 8765 --no-access-log
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl enable --now ai-news
```

---

## 6. Nginx 配置

```nginx
# /etc/nginx/sites-available/ai-news
server {
    listen 80;
    server_name your-domain.com;

    # 静态文件
    root /home/aiobserver/app/reports;
    index dashboard.html;

    # API 代理
    location /api/ {
        proxy_pass http://127.0.0.1:8765;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 120s;
    }

    # WebSocket (报告流式生成)
    location /ws/ {
        proxy_pass http://127.0.0.1:8765;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # 报告阅读器路由：/report/*.md → 统一 HTML shell
    location ~ ^/report/ {
        try_files /report-reader.html =404;
    }

    # 首页
    location = / {
        try_files /dashboard.html =404;
    }

    # 保护敏感文件
    location ~ /\. { deny all; }
    location ~ /data/ { deny all; }
}
```

```bash
ln -s /etc/nginx/sites-available/ai-news /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx
```

---

## 7. HTTPS（可选）

```bash
apt install -y certbot python3-certbot-nginx
certbot --nginx -d your-domain.com
# 自动续期: certbot renew --dry-run
```

---

## 8. 数据库备份

```bash
# 服务器上执行
cp /home/aiobserver/app/data/news.db "/home/aiobserver/backups/news_$(date +%Y%m%d).db"

# 或从本地拉取
scp admin@your-server:/home/aiobserver/app/data/news.db ./backup/
```

建议配合 cron 每日自动备份（见 `scripts/backup_db.sh`）。

---

## 9. 性能测试

```bash
# 轻压测（1 VU / 30s，不触发限流）
bash scripts/load_test.sh smoke-load

# 限流测试（专门测 429）
bash scripts/load_test.sh rate-limit-load

# 其他等级：normal-load / peak-load / spike-test / soak-test / limit-test
```

详见 `docs/PERFORMANCE_TEST_PLAN.md`。

---

## 10. 部署流程

| 触发词 | 操作 |
|--------|------|
| **体检** | `bash scripts/preflight.sh`（只读环境检查） |
| **执行后端部署** | `bash scripts/deploy_backend.sh`（需确认重启） |
| **执行前端部署** | `bash scripts/deploy_frontend.sh` |
| **验收** | `bash scripts/qa_smoke_test.sh`（冒烟测试） |
| **轻压测** | `bash scripts/load_test.sh smoke-load` |

完整 SOP 见 `.agents/` 目录。

---

## 11. 注意事项

- Knowledge Card (YAML) 是唯一写入点，所有模块只读
- 不使用 `rm -rf`、不覆盖 `.env` / `data/` / `.venv/`
- API 限流：120 req/min（可配置 `src/api/api.py`）
- 服务器 Python 统一用 `.venv/bin/python`，不要用 `uv`
- 部署后用 `qa_smoke_test.sh` 验证，用 `load_test.sh smoke-load` 验证性能
