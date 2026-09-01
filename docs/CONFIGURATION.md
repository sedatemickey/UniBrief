# 本地开发与环境变量契约

本文冻结 Phase 0 的运行环境和 `.env.example` 字段。实际 `.env` 不提交 Git；密码、API Key、Cookie、NapCat Token 不得写入文档、日志或示例数据。

## 1. 已确认的本机解释器

- 正式后端解释器：`C:\Users\ASUS\AppData\Local\Programs\Python\Python312\python.exe`
- 已复核版本：Python 3.12.5。
- 当前 Codex/MSYS2 命令解析还可能命中 `C:\Programs\msys64\mingw64\bin\python.exe`（Python 3.11.9），因此创建虚拟环境时必须使用上面的绝对路径，后续统一调用项目虚拟环境中的 Python。

推荐 Phase 0 命令：

```powershell
& 'C:\Users\ASUS\AppData\Local\Programs\Python\Python312\python.exe' -m venv backend\.venv
backend\.venv\Scripts\python.exe --version
```

## 2. MySQL

- 开发数据库使用 MySQL 8.x、`utf8mb4`、UTC 会话时区。
- MySQL 的安装、启动、端口、应用账号以及开发/测试数据库创建由用户全权负责；项目不创建 Docker Compose，也不管理 MySQL 服务生命周期。
- 后端只从 `DATABASE_URL` / `TEST_DATABASE_URL` 连接，Alembic 和 pytest 不得写死主机、端口或密码。
- 开发库和测试库必须分离，建议使用 `unibrief` 与 `unibrief_test`；测试不得连接生产/演示库。

手工安装 MySQL 后，Phase 0 至少验证：服务已启动、应用账号可连接、两个数据库存在、`SELECT VERSION()` 为 8.x、字符集为 `utf8mb4`、会话时区为 `+00:00`。

## 3. Vite 与 FastAPI 同源开发

- Vite 开发地址固定为 `http://localhost:5173`。
- FastAPI 开发地址固定为 `http://127.0.0.1:8000`。
- `vite.config.ts` 将 `/api` 和 `/health` 代理到 FastAPI；前端 API client 只请求相对路径并设置 `credentials: 'include'`。
- 正常开发流量经 Vite 代理后对浏览器表现为同源，不以放开通配 CORS 解决 Cookie 问题。
- 服务端仍校验 `Origin`；开发环境允许 `http://localhost:5173`。生产部署由反向代理提供同源 `/api`。

## 4. `.env.example` 完整字段

Phase 0 创建的 `.env.example` 至少包含以下字段；示例密码只作占位，不可直接用于部署：

```env
APP_ENV=development
APP_HOST=127.0.0.1
APP_PORT=8000
LOG_LEVEL=INFO
FRONTEND_ORIGIN=http://localhost:5173
TRUSTED_ORIGINS=http://localhost:5173

DATABASE_URL=mysql+pymysql://unibrief:change-me@127.0.0.1:3306/unibrief?charset=utf8mb4
TEST_DATABASE_URL=mysql+pymysql://unibrief:change-me@127.0.0.1:3306/unibrief_test?charset=utf8mb4

USER_SESSION_SECRET=replace-with-at-least-32-random-bytes
ADMIN_SESSION_SECRET=replace-with-a-different-random-secret
USER_SESSION_TTL_SECONDS=604800
ADMIN_SESSION_TTL_SECONDS=28800
COOKIE_SECURE=false
COOKIE_SAMESITE=lax

ATTACHMENT_STORAGE_DIR=./var/attachments
ATTACHMENT_MAX_BYTES=20971520
ATTACHMENT_TIMEOUT_SECONDS=30
ATTACHMENT_MAX_RETRIES=2
ATTACHMENT_MAX_REDIRECTS=3
ATTACHMENT_DOWNLOADING_STALE_SECONDS=600

REMINDER_SCAN_INTERVAL_SECONDS=60
EVENT_STATUS_SCAN_INTERVAL_SECONDS=60

AI_BASE_URL=https://api.openai.com/v1
AI_API_KEY=
AI_DEFAULT_MODEL=
AI_TIMEOUT_SECONDS=60
AI_MAX_RETRIES=2
AI_TEMPERATURE=0.1
AI_JSON_MODE=auto
AI_BATCH_POLL_SECONDS=30
AI_BATCH_SIZE_THRESHOLD=20
AI_BATCH_MAX_WAIT_SECONDS=300
AI_PROCESSING_STALE_SECONDS=600

NAPCAT_ENABLED=false
NAPCAT_WS_URL=ws://127.0.0.1:3001
NAPCAT_ACCESS_TOKEN=
NAPCAT_RECONNECT_MAX_SECONDS=30
NAPCAT_HEARTBEAT_TIMEOUT_SECONDS=90
NAPCAT_IMPORT_BATCH_SIZE=20
NAPCAT_IMPORT_FLUSH_SECONDS=5
UNIBRIEF_BASE_URL=http://127.0.0.1:8000
UNIBRIEF_USERNAME=
UNIBRIEF_PASSWORD=
```

规则：

- `USER_SESSION_SECRET` 与 `ADMIN_SESSION_SECRET` 必须不同；非 development 环境拒绝占位值。
- `COOKIE_SECURE=true` 用于 HTTPS 生产环境；开发环境因使用 HTTP 设为 false。
- `NAPCAT_ENABLED=false` 时不启动 bridge、不连接 WebSocket；代码和配置仍需存在。
- `UNIBRIEF_PASSWORD` 只允许部署 Secret 注入；交互启动优先提示输入。
- 配置缺失应在应用启动时给出字段名和安全提示，不得把秘密值回显到异常。
