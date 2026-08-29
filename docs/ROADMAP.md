# ROADMAP.md

# 推荐开发顺序

不要让 Codex 一次同时改数据库、AI、前端全部模块。按阶段推进并在每阶段运行验收。

## Phase 0 - 仓库初始化

目标：
- 创建 backend/frontend/infra/docs/scripts/sample_data
- Docker Compose MySQL
- `.env.example`
- README 启动说明
- 后端/前端最小可运行骨架
- health check

完成条件：
- MySQL 可启动
- Backend `/health` 返回 OK
- Frontend 可打开
- docs/PROGRESS.md 更新

## Phase 1 - 数据库与基础后端

目标：
- 实现 13 张表 ORM
- Alembic 初始 migration
- 约束/索引
- seed Category
- Platform/Channel/Sender/Message 的 repository/service/API
- JSON 批量消息导入且幂等
- Message 列表分页/过滤

完成条件：
- 空库可 alembic upgrade
- 同一批消息导入两次不会重复
- pytest 通过

## Phase 2 - 真实 AI 分析与有效信息

目标：
- 实现真实 `OpenAICompatibleProvider`
- 使用 OpenAI-compatible Chat Completions
- 环境变量配置 base URL / key / default model
- `GET /ai/config`
- `GET /ai/models`
- `POST /ai/test`
- 模型列表失败时支持手工 model ID
- 单条/批量 Analyze API 支持 model 参数
- AI 结果 Pydantic schema
- 保存 AIAnalysis，必须记录真实 `model_name`
- 创建/支持/更新 InformationItem
- MessageInformation
- Category/Tag 归一化
- Event 生成
- 401 / 404 model / 429 / timeout / invalid JSON / schema invalid 错误处理
- 提供 `scripts/test_ai_connection.py` 做真实联调

完成条件：
- 使用真实配置的 OpenAI-compatible API 成功分析至少一条消息
- 能从 `/models` 获取模型，或在不支持时手工指定 model
- 前端后续可通过 API 获得模型列表
- 闲聊消息不会生成 InformationItem
- 有效消息可以形成完整关系链
- AI 失败后 Message 可重试
- 单元测试可以 mock HTTP，但项目运行时没有 MockAIProvider

## Phase 3 - 数据库高级对象和统计

目标：
- 关键索引核对
- 3 个以上 View/统计查询
- 1 个 Trigger/自动更新时间机制
- 可选 Stored Procedure
- Statistics API

完成条件：
- 至少 3 个课堂可展示统计
- SQL/迁移文件可解释
- 查询有合理索引支持

## Phase 4 - 前端核心页面

目标：
- Dashboard
- Information 列表
- Information 详情与原始来源
- Message 列表
- Sources 管理
- AI Settings（真实模型列表、手工 model、测试连接）
- Import & Analyze（可选择本次模型）
- Statistics

完成条件：
- 主流程无需 Swagger 即可从 UI 演示
- 所有列表支持 loading/error/empty 状态
- npm run build 通过

## Phase 5 - 演示数据与健壮性

目标：
- 生成 >= 1000 条 synthetic messages
- >= 30 条有效 InformationItem
- >= 200 条关联记录
- 正常/异常/重复导入/AI失败测试
- 准备固定 demo dataset
- 一键 reset + seed 脚本

完成条件：
- 课堂演示可重复
- 至少覆盖：重复消息、无用闲聊、AI失败、同一信息多消息支持、带 deadline 的 Event

## Phase 6 - 收尾

目标：
- 完整 README
- API 文档
- 数据字典
- ER 图字段与代码一致
- 导出数据库 schema
- 记录统计 SQL
- 报告素材截图清单
- 最终测试

完成条件：
- `docs/ACCEPTANCE.md` 全部勾选
- 后端测试通过
- 前端 build 通过
- clean clone 后按 README 可启动
