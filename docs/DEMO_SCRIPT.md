# 课堂演示操作脚本（5–8 分钟）

## 0. 展示前准备（不计时）

1. MySQL 8 已启动，开发库已执行 `alembic upgrade head`。
2. 执行 `backend\.venv\Scripts\python.exe scripts\reset_seed_demo.py --force`。
3. 启动 FastAPI 与 Vite，确认 `/health` 返回 `status=ok`。
4. 若要展示真实 AI，必须提前在 `.env` 配置真实 `AI_BASE_URL`、`AI_API_KEY`、`AI_DEFAULT_MODEL`，并用 `scripts/test_ai_connection.py` 验证。
5. 准备两个浏览器配置文件或一个普通窗口 + 一个无痕窗口，避免 Cookie 相互覆盖。

演示账号：

- 主用户：`demo_student` / `DemoStudent2026!`
- 隔离用户：`demo_observer` / `DemoObserver2026!`

> 演示数据完全合成。真实 AI 未配置时，应明确说明外部条件未满足，只演示已持久化的合成分析记录和错误/重试机制，不能声称真实联调通过。

## 1. 0:00–0:50 管理与权限边界

1. 打开 `/admin/login`，展示独立管理员入口。
2. 展示用户列表、注册开关、Platform/Category 管理。
3. 强调管理员菜单中没有 Message、Information、Tag、Event 等用户私有内容入口。
4. 可快速启停一个临时用户，说明停用不删除历史数据，session version 使旧会话失效。

讲解点：普通用户是私有数据空间；管理员只维护账号和全局字典。

## 2. 0:50–1:40 数据量与隔离

1. 登录 `demo_student`，Dashboard 展示消息、信息、事项、提醒概览。
2. 打开有效信息列表，记住一个标题。
3. 用另一窗口登录 `demo_observer`，搜索同一标题，结果为空或 404。
4. 返回主窗口。

讲解点：隔离不只靠前端，Repository 过滤 + `message_information`/`information_tag` 复合外键双重保证。

## 3. 1:40–2:40 原始消息导入、去重与附件

1. 打开“导入分析”，选择 JSON 或 CSV 合成消息导入。
2. 连续导入同一份数据，展示第二次返回 `DUPLICATE`；若使用同外部 ID 修改正文，展示 `DUPLICATE_CONFLICT` 且原文未覆盖。
3. 打开“原始消息”，按渠道/状态筛选。
4. 进入一条带附件消息详情：展示 DOWNLOADED 附件可鉴权下载，以及 FAILED 附件可重试。

讲解点：Message 先可靠入库，附件失败不回滚 Message；数据库只保存相对存储键和校验值。

## 4. 2:40–3:50 真实 AI 或严格失败路径

### 已配置真实 AI 时

1. 打开“AI 设置”，加载模型列表；若供应商不支持 `/models`，手工输入 model ID。
2. 点击连接测试，展示 latency 和成功状态。
3. 在“导入分析”选择一条 PENDING/FAILED 消息和当前模型，执行 retry。
4. 打开消息详情，展示实际 `model_name`、AIAnalysis、处理状态。

### 未配置真实 AI 时

1. 展示 AI 设置中的 `has_api_key=false` 或连接错误分类。
2. 展示一条 seed 中的 FAILED AIAnalysis 和可重试状态。
3. 明确说明自动化测试只 mock HTTP transport，产品运行时不存在 MockAIProvider。

讲解点：AI 请求不放进长事务；结果先经 Pydantic 严格校验，再在短事务内落库，失败不丢原消息。

## 5. 3:50–5:10 信息聚合、追溯与事项提醒

1. 打开一条 Information 详情。
2. 展示 Category、Tag、重要度、摘要和 version。
3. 在“原始证据”中展示多条 Message 通过 CREATE/SUPPORT/UPDATE/CORRECTION 支持同一 InformationItem。
4. 展示 Event 与 Deadline 自动派生的 EventReminder。
5. 在提醒中心展示 PENDING/DUE/READ/DISABLED，演示修改提醒时间、关闭或标记已读。

讲解点：Message ↔ InformationItem 是 M:N；Event 和 Reminder 都是 1:0..1，且创建/更新遵守同一事务与乐观锁。

## 6. 5:10–6:20 组合筛选与双视图

1. 在 Information 页同时选择 Category、两个 Tag（OR）、重要度、状态、信息时间或事项时间。
2. 展示 URL 包含筛选、排序和分页参数；刷新后条件保持。
3. 打开“事项日历”，在月历和议程间切换，指出同一 Event 来自同一个 range API。
4. 可编辑 Event 时间或执行完成/取消/恢复，说明冲突会返回 409 而不是覆盖。

## 7. 6:20–7:20 至少三项统计

依次展示：

1. Channel 消息总数、有效消息数、有效率；
2. Category 信息分布；
3. Tag 热门度 Top N；
4. 如时间允许，展示未来 7 天 Event。

讲解点：统计只计算当前用户；Stored Procedure 使用 `[start,end)`，View 均包含或从关系推导 `user_id`。

## 8. 7:20–8:00 数据库收尾

1. 展示 ER 图/数据字典中的 16 张表。
2. 展示 4 个 View、1 个 Trigger、`sp_channel_statistics`。
3. 总结三条主线：原文有证据、信息有关系、用户有边界。

## 9. 演示失败的安全降级

- 真实 AI 不可用：展示明确错误分类和重试，不伪造成功。
- 附件远端 URL 失效：使用 seed 的本地成功/失败样例，说明受控存储规则。
- NapCat 未搭建：只展示 OneBot Adapter/bridge 代码与默认关闭配置，不声称真实联调。
- 浏览器会话失效：重新登录，不修改数据库或关闭 CSRF。
