# 已知限制与外部依赖

截至 2026-09-01，以下内容是课程设计 MVP 的明确边界或尚需外部条件验证的项目。

## 1. 真实 AI 配置

- 产品代码已实现真实 OpenAI-compatible Provider、模型列表、手工 model ID、连接测试和单条/批量分析。
- 当前仓库不包含 API Key，自动化测试使用 mock HTTP transport，不能证明某个真实供应商在当前网络与账号下可用。
- 最终真实验收必须由用户提供合法 `AI_BASE_URL`、`AI_API_KEY`、`AI_DEFAULT_MODEL`，运行 `scripts/test_ai_connection.py` 并分析至少一条消息。
- 真实供应商可能不支持 `/models` 或 JSON mode；系统会明确报告并允许手工 model ID，但仍依赖其 Chat Completions 兼容程度。

## 2. NapCat/QQ

- 仓库只实现 OneBot 11 Adapter 与独立 bridge 调用方法，默认 `NAPCAT_ENABLED=false`。
- NapCat 是第三方协议端，安装、QQ 登录、Token 和网络可用性不由 UniBrief 管理。
- 未完成第三方框架搭建前，不声称真实 QQ 联调通过；项目不逆向协议、不自动回复。

## 3. 部署范围

- MySQL 8 的安装、服务启动、账号和数据库创建由用户负责；项目不提供 Docker Compose。
- 当前 README 以 Windows PowerShell 为主要验证环境，其他系统需等价调整路径和命令。
- MVP 使用单 FastAPI 进程内周期 loop，不引入 Redis、消息队列或独立 Worker；多实例部署需要额外的分布式抢占/调度设计。
- 附件保存在单机受控目录；多机共享存储、对象存储和备份策略不在 MVP 内。

## 4. 功能边界

- 不做多级 RBAC、团队共享、用户间数据共享或 UserFeedback。
- 不做 RAG、向量数据库、多 Agent、自动回复、移动端 App 或复杂 OCR。
- 信息去重采用近期候选 + 简单关键词 + AI 在候选中决定 create/link/update，不是语义向量全库检索。
- UI 不提供复杂的“一条消息人工拆分多个事项”编辑器，但数据库与 service 支持一条 Message 关联多个 InformationItem。

## 5. 测试与依赖风险

- FastAPI/Starlette 当前测试组合会产生上游 TestClient 弃用 warning，测试结果仍有效；未来升级依赖时需要复核。
- 前端自动化测试只覆盖关键工具函数；完整页面交互仍需按 `docs/SCREENSHOT_CHECKLIST.md` 人工走查。
- clean clone、真实 AI、真实 NapCat 都必须保留独立验证记录，不能用当前工作区或 seed 结果代替。
