# 测试与最终验收说明

## 1. 测试数据库安全规则

- Alembic 开发迁移只读 `DATABASE_URL`。
- pytest 只允许 `TEST_DATABASE_URL`，`backend/tests/conftest.py` 会拒绝测试连接开发库。
- 两个 URL 都使用 TCP `127.0.0.1`；SQLAlchemy 建连后执行 `SET time_zone = '+00:00'`。
- 空库迁移和 seed 会清空目标库，只能在确认的测试/开发数据库执行。

## 2. 后端自动化检查

```powershell
Push-Location backend
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m alembic check
Pop-Location
```

当前测试覆盖：认证/CSRF/session version、管理员隔离、系统设置白名单、数据库约束、消息去重/冲突、CSV、附件成功/失败/鉴权、AI Provider 错误映射、严格 JSON、retry/compare、批量部分成功、乐观锁、Event/Reminder、组合筛选、统计 View/Procedure/Trigger、周期任务和跨用户 404。

## 3. 空库迁移验证

仅在专用 `unibrief_test` 上执行：

```powershell
Push-Location backend
.\.venv\Scripts\python.exe -m alembic downgrade base
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m alembic check
Pop-Location
```

随后运行 `pytest`，验证 16 表、关键索引、CHECK、UNIQUE、复合外键、4 View、Trigger 和 Stored Procedure。

## 4. 开发数据库与演示数据

```powershell
backend\.venv\Scripts\python.exe scripts\check_database.py
backend\.venv\Scripts\python.exe scripts\reset_seed_demo.py --force
```

期望确定性数量：2 Users、3 Platforms、10 Channels、13 Senders、1006 Messages、34 InformationItems、238 MessageInformation、24 Events、24 EventReminders、24 Attachments。

## 5. 前端检查

```powershell
Push-Location frontend
npm ci
npm run build
npm test -- --run
Pop-Location
```

`npm ci` 用于 clean clone；日常已有 `node_modules` 时可直接 build/test。关键自动化测试覆盖数组查询参数序列化和 Asia/Shanghai 时间显示；其余页面按 `docs/SCREENSHOT_CHECKLIST.md` 做人工走查。

## 6. 真实 AI 联调

自动化测试不会消耗真实 Token。真实联调必须显式配置：

```text
AI_BASE_URL=...
AI_API_KEY=...
AI_DEFAULT_MODEL=...
```

然后运行：

```powershell
backend\.venv\Scripts\python.exe scripts\test_ai_connection.py
```

通过标准：真实请求成功、返回实际 model ID/latency，并至少通过 UI 或 Analyze API 处理一条消息，数据库中生成真实 `AIAnalysis`。不得用 seed 或 mock 结果替代此验收。

## 7. NapCat 手工联调

按 `docs/NAPCAT_INTEGRATION.md` 搭建第三方 NapCat 后，验证字符串 ID、文本/附件段、重复事件幂等、断线重连和 UniBrief 登录恢复。`NAPCAT_ENABLED=false` 是默认安全配置；未搭建第三方框架时只验收 Adapter/bridge 代码，不勾选真实联调条目。

## 8. Clean clone 启动检查

在新的目录中按 README 完整执行：

1. 复制 `.env.example` 并填写非占位秘密；
2. 新建 Python 3.12 venv，`pip install '.[dev]'`；
3. `npm ci`；
4. 专用空库 `alembic upgrade head`；
5. 初始化管理员；
6. 后端 `/health`；
7. Vite 页面和登录；
8. pytest、ruff、alembic check、frontend build/test；
9. reset/seed 后执行 `docs/DEMO_SCRIPT.md`。

只有在新目录实际完成以上步骤后，才能勾选“clean clone 后按 README 可启动”。

## 9. 2026-09-01 clean clone 实测结果

已从 Git 提交 `89f224f` 新建独立 clone，并按本文件执行：全新 Python 3.12 venv 安装、`npm ci`、专用测试库空库迁移、44 项 pytest、ruff、Alembic check、frontend build/test，以及 FastAPI/Vite 实际启动。全部通过；真实 AI 与 NapCat 仍属于外部配置验收，不包含在 clean clone 的离线成功结论中。
