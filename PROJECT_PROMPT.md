# Codex 总提示词：完成校园多源消息智能聚合系统

你正在本项目仓库根目录工作。

请先完整阅读并遵守：
- `AGENTS.md`
- `docs/COURSE_REQUIREMENTS.md`
- `docs/ARCHITECTURE.md`
- `docs/AI_INTEGRATION.md`
- `docs/DATABASE.md`
- `docs/ROADMAP.md`
- `docs/ACCEPTANCE.md`
- `docs/API.md`
- `docs/PROGRESS.md`
- `docs/DECISIONS.md`

## 任务

把本仓库实现成可运行、可测试、可课堂演示的“校园多源消息智能聚合与信息管理系统”。

这是数据库课程设计，优先级是：
1. 数据库设计正确；
2. 主业务流程完整；
3. 统计功能清晰；
4. 健壮性；
5. UI 可用；
6. UI 美化。

不要把项目做成“套壳聊天机器人”。数据库必须是系统核心。

## 工作方式

按 `docs/ROADMAP.md` 的 Phase 顺序执行。

先检查当前仓库和 `docs/PROGRESS.md`，只从尚未完成的第一个 Phase 开始。

每个 Phase：
1. 检查现有代码，不重复造已有功能；
2. 给出简短实施计划；
3. 编写代码；
4. 创建/更新测试；
5. 运行本阶段要求的测试、build 和 migration；
6. 修复发现的问题；
7. 更新 `docs/PROGRESS.md`；
8. 如果有架构选择，记录到 `docs/DECISIONS.md`；
9. 总结本阶段修改、验证结果、已知风险。

如果当前会话长度或执行时间不适合继续下一个 Phase，就停在干净、可运行的阶段边界，并明确告诉我下一次应从哪个 Phase 继续。

## 硬性边界

- 单用户：不要创建 User/UserFeedback/认证系统；
- 不逆向 QQ/微信/钉钉；
- 不加入 Redis/Kafka/Celery/微服务，除非我以后明确要求；
- 不加入向量数据库/RAG；
- 不加入多 Agent；
- AI 必须使用真实 OpenAI-compatible API；运行时不得使用 MockAIProvider；
- 必须实现真实 AI 模型列表、手工模型 ID、模型选择和连接测试接口；
- API Key 只能保存在服务端环境变量，绝不返回前端或提交 Git；
- 自动化测试允许 mock HTTP transport，但产品正常路径和课堂演示必须真实调用 API；
- 不提交任何真实密钥或真实聊天数据；
- 不绕开数据库约束去“在代码里假装有约束”；
- 不擅自删除 Category、Tag、MessageInformation、Event 等核心设计。

## 最终目标

最终必须同时满足 `docs/COURSE_REQUIREMENTS.md` 和 `docs/ACCEPTANCE.md`，尤其保证：
- MySQL 从空库可迁移；
- 完整消息导入 -> AI 分析 -> 信息形成 -> 分类/标签 -> Event -> 前端展示流程；
- 至少 3 类统计；
- 合成演示数据足够；
- 后端测试通过；
- 前端 build 通过；
- README 可指导从 clean clone 启动。

现在开始：先检查仓库状态，阅读上述文件，然后执行尚未完成的第一个 Phase。
