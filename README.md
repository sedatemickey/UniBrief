# UniBrief

UniBrief（校园多源消息智能聚合与信息管理系统）是一个以 MySQL 为核心的数据库课程设计项目。系统将 QQ、微信、钉钉等多渠道原始消息统一接入，使用真实 OpenAI-compatible API 判断价值、摘要、分类和打标签，将有时间属性的信息转为 Event 与站内提醒，并保留从结构化信息回溯原始 Message/附件的证据链。

普通用户拥有独立的私有数据空间；管理员使用独立入口，只维护账号、注册开关和全局 Platform/Category，不读取用户私有消息、信息、标签或事项。

## 实现范围

- 16 张核心表、真实外键/复合外键、UNIQUE、CHECK、关键索引和 Alembic migration；
- HttpOnly Cookie、CSRF、Argon2id、普通/管理员独立会话和 session version 失效；
- JSON/CSV、模拟 Adapter、NapCat OneBot 11 Adapter/bridge（默认关闭）；
- 附件受控本地下载、校验、鉴权读取、失败重试与文件丢失检测；
- 真实 OpenAI-compatible Provider、模型列表/手工模型、连接测试、单条/批量 retry/compare；
- Information 聚合、Category、用户私有 Tag、Event、EventReminder、乐观锁；
- 4 个统计 View、1 个 Trigger、`sp_channel_statistics` Stored Procedure；
- React 中文 Web UI：Dashboard、消息、信息、来源、导入分析、AI 设置、统计、日历/议程、提醒、个人资料与管理端；
- 确定性 synthetic demo dataset：1006 Messages、34 InformationItems、238 条 Message-Information 关系。

## 技术栈

- Backend：Python 3.12、FastAPI、SQLAlchemy 2.x、Alembic、PyMySQL、Pydantic v2、pytest、ruff
- Database：MySQL 8.x、utf8mb4、UTC session
- Frontend：React、TypeScript strict、Vite、Ant Design、TanStack Query、ECharts、Vitest
- AI：真实 OpenAI-compatible Chat Completions API；产品运行时无 MockAIProvider

## 目录

```text
backend/       FastAPI、ORM、Alembic、服务与测试
frontend/      React/Vite 中文 Web UI
infra/         schema 与统计 SQL 导出（不含 Docker Compose）
docs/          架构、数据库、API、测试、展示和验收文档
pre/           课堂展示讲稿、PPT 与绘图材料
prompts/       分阶段开发提示
scripts/       数据库检查、demo reset/seed、AI/NapCat 联调脚本
sample_data/   合成演示数据说明
```

## 环境要求

1. Python 3.12+；
2. Node.js 20.19+ 或 22.12+；
3. 用户自行安装并启动 MySQL 8.x；
4. Windows PowerShell 是当前完整验证环境，其他 shell 可使用等价命令。

项目不提供 Docker Compose，不管理 MySQL 服务生命周期。

## Clean clone 启动

### 1. 配置

```powershell
Copy-Item .env.example .env
```

至少修改：

- `DATABASE_URL`：开发数据库；
- `TEST_DATABASE_URL`：独立测试数据库，pytest 禁止连接开发库；
- `USER_SESSION_SECRET`、`ADMIN_SESSION_SECRET`：两个不同的高强度随机值；
- 真实 AI 联调时填写 `AI_BASE_URL`、`AI_API_KEY`、`AI_DEFAULT_MODEL`。

`.env` 已被 Git 忽略。不要提交真实 API Key、Cookie、NapCat Token、数据库密码或真实聊天数据。

### 2. 后端依赖与 migration

```powershell
& 'C:\Users\ASUS\AppData\Local\Programs\Python\Python312\python.exe' -m venv backend\.venv
Push-Location backend
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install '.[dev]'
.\.venv\Scripts\python.exe -m alembic upgrade head
Pop-Location
```

上述 Python 绝对路径是当前开发机示例；其他机器使用自己的 Python 3.12 可执行文件。

安全检查数据库连接（不输出凭据）：

```powershell
backend\.venv\Scripts\python.exe scripts\check_database.py
```

### 3. 初始化管理员

管理员没有默认密码。首次启动前执行交互式初始化：

```powershell
Push-Location backend
.\.venv\Scripts\python.exe -m app.cli.admin init-password
Pop-Location
```

重置使用 `reset-password`；密码不会通过命令行参数传入。

### 4. 启动 FastAPI

```powershell
Push-Location backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

另开窗口验证：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

预期 `status` 为 `ok`。

### 5. 启动前端

```powershell
Push-Location frontend
npm ci
npm run dev
```

打开 `http://localhost:5173`。Vite 将 `/api` 和 `/health` 代理到 `http://127.0.0.1:8000`，浏览器只使用同源相对路径并携带 Cookie。

如果当前机器 npm wrapper 受用户级 prefix 影响，可临时使用：

```powershell
& 'C:\Program Files\nodejs\node.exe' 'C:\Program Files\nodejs\node_modules\npm\bin\npm-cli.js' ci
```

## 演示数据

> `reset_seed_demo.py --force` 会清空并重建 `DATABASE_URL` 指向的数据库，只能在确认的开发/演示库运行。

```powershell
backend\.venv\Scripts\python.exe scripts\reset_seed_demo.py --force
```

确定性数据量：

- 2 Users、3 Platforms、10 Channels、13 Senders；
- 1006 Messages、34 InformationItems；
- 238 MessageInformation；
- 24 Events、24 EventReminders、24 Attachments。

演示账号：

- `demo_student` / `DemoStudent2026!`
- `demo_observer` / `DemoObserver2026!`

完整 5–8 分钟操作顺序见 `docs/DEMO_SCRIPT.md`。

## 真实 AI 联调

在 `.env` 配置真实服务后运行：

```powershell
backend\.venv\Scripts\python.exe scripts\test_ai_connection.py
```

脚本不会打印 API Key。最终验收需要真实连接成功并分析至少一条消息；自动化测试中的 mock HTTP transport 和 demo seed 不能替代此项。

## 测试

```powershell
# Backend
Push-Location backend
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m alembic check
Pop-Location

# Frontend
Push-Location frontend
npm run build
npm test -- --run
Pop-Location

# Database
backend\.venv\Scripts\python.exe scripts\check_database.py
```

空库迁移、seed、clean clone 与手工验证细节见 `docs/TESTING.md`。

## 数据库材料

- 设计与约束：`docs/DATABASE.md`
- 数据字典：`docs/DATA_DICTIONARY.md`
- ER 对应清单：`docs/ER_MAPPING.md`
- API：`docs/API.md`
- 统计 SQL：`docs/STATISTICS_SQL.md`、`infra/statistics.sql`
- schema 导出：`infra/schema.sql`
- 截图清单：`docs/SCREENSHOT_CHECKLIST.md`
- 已知限制：`docs/KNOWN_LIMITATIONS.md`
- 验收状态：`docs/ACCEPTANCE.md`
- 开发进度：`docs/PROGRESS.md`

## 当前状态与外部阻塞

Phase 0–5 已实现，当前执行 Phase 6 最终文档和验证。真实 AI 成功联调依赖用户提供合法 Key/model；NapCat 真实联调依赖用户完成第三方框架搭建。未满足外部条件时，项目会展示真实失败分类和重试机制，而不会伪造成功。
