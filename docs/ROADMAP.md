# ROADMAP.md

# 推荐开发顺序

不要让 Codex 一次同时改数据库、AI、前端全部模块。按阶段推进并在每阶段运行验收。

## Phase 0 - 仓库初始化

目标：
- 创建 backend/frontend/infra/docs/scripts/sample_data
- 连接用户负责安装和启动的 MySQL 8.x
- `.env.example`
- Vite `/api`、`/health` 到 FastAPI 的开发代理
- README 启动说明
- 后端/前端最小可运行骨架
- health check

完成条件：
- 用户提供的 MySQL 8.x 可通过 `DATABASE_URL` 连接
- Backend `/health` 返回 OK
- Frontend 可打开
- docs/PROGRESS.md 更新

## Phase 1 - 数据库与基础后端

目标：
- 实现 16 张表 ORM，包括 user、system_setting 和 event_reminder
- InformationItem 增加 version 乐观锁；AIAnalysis 同时记录 SUCCEEDED/FAILED、错误码、耗时和脱敏原始响应
- Alembic 初始 migration
- 用户归属复合外键、唯一约束和用户级索引
- Argon2id、普通用户/管理员 HttpOnly Cookie 与 CSRF
- system_setting 白名单、注册开关、管理员命令行初始化
- 用户登录/退出/改密，管理员创建/启停/重置用户
- seed Category
- 管理员维护 Platform/Category，用户维护私有 Channel
- Platform/Channel/Sender/Message 的 repository/service/API
- JSON 批量消息导入且幂等
- CSV Adapter 与 NapCat OneBot 11 Adapter/桥接调用方法；运行时默认 `NAPCAT_ENABLED=false`，NapCat 只转换消息并调用统一导入 API，不发送消息或自动回复
- 导入后自动下载受控 HTTP/HTTPS 附件到本地存储，维护校验值和下载状态
- 附件鉴权下载与失败重试 API；在 `.env.example` 登记存储目录、20 MiB 上限、30 秒超时和 2 次最大重试配置
- Message 列表分页/过滤

完成条件：
- 空库可 alembic upgrade
- 注册默认关闭，开关启用后注册接口可用
- 用户 A 无法访问用户 B 的任何业务数据
- 同一批消息导入两次不会重复
- 附件下载失败不影响 Message 入库，成功文件可鉴权读取，失败附件可重试
- 用户 A 无法下载用户 B 的附件，本地绝对路径不通过 API 暴露
- NapCat bridge 的接口、事件映射、重连和导入调用代码完成，但本阶段不要求连接真实 NapCat 框架
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
- 单条/批量支持 `mode=retry|compare`；retry 写正式业务，compare 只追加 AIAnalysis
- 手工单条与手工批量分析；自动 20 条/5 分钟窗口在 Phase 3 实现
- AI 结果 Pydantic schema
- 顶层只保留 useful；每个 item 独立包含 importance/confidence/action/target_information_id/relation_type；批量响应使用 results[] 并按 Message 独立短事务
- 保存 AIAnalysis，必须记录真实 `model_name`
- 创建/支持/更新/更正 InformationItem
- MessageInformation
- Category/Tag 归一化
- Event 生成
- 带 Deadline 的 Event 在同一短事务中生成默认提前 24 小时的 EventReminder
- Deadline 更新时保护用户自定义或关闭的提醒
- UniBrief 会话 401、Provider AUTH_ERROR 502、MODEL_NOT_FOUND 502、429、504 timeout、invalid JSON/schema 502 错误处理
- 提供 `scripts/test_ai_connection.py` 做真实联调

完成条件：
- 使用真实配置的 OpenAI-compatible API 成功分析至少一条消息
- 能从 `/models` 获取模型，或在不支持时手工指定 model
- 前端后续可通过 API 获得模型列表
- 闲聊消息不会生成 InformationItem
- 有效消息可以形成完整关系链
- AI 失败后 Message 可重试
- AI 候选、批次和结果不会跨用户
- Event 与默认提醒要么同时写入成功，要么整体回滚
- InformationItem 乐观锁冲突不会静默覆盖，最多重新调用 AI 一次
- 单元测试可以 mock HTTP，但项目运行时没有 MockAIProvider

## Phase 3 - 数据库高级对象和统计

目标：
- 关键索引核对
- 3 个以上 View/统计查询
- 1 个 Trigger/自动更新时间机制
- 必须实现 Stored Procedure：`sp_channel_statistics(p_user_id, p_start, p_end)`
- Statistics API
- 同进程周期任务默认每 60 秒幂等扫描到期提醒，将 PENDING 转为 DUE
- 每 30 秒扫描同一用户/Channel 的 PENDING Message，达到 20 条或最早等待 5 分钟时自动分析；原子抢占并恢复超过 10 分钟的 PROCESSING
- 周期任务维护 Event 的 UPCOMING/ONGOING/EXPIRED；COMPLETED/CANCELLED 由用户操作
- EventReminder `(reminder_status, remind_at)` 索引及跨用户查询隔离核对

完成条件：
- 至少 3 个课堂可展示统计
- SQL/迁移文件可解释
- 查询有合理索引支持
- 重复扫描不会重复触发提醒，完成/取消/过期事项不产生新提醒

## Phase 4 - 前端核心页面

目标：
- 普通用户登录、可选注册、修改密码
- 独立管理员登录和账号/注册开关/全局字典面板
- Dashboard
- Information 列表，支持分类、多个标签、重要度、状态、信息时间、事项时间和关键词组合筛选
- 多标签按任一匹配，不同筛选维度按 AND 组合；筛选、排序和分页写入 URL
- Information 详情与原始来源
- Message 列表与附件下载状态、下载、失败重试
- Sources 管理
- AI Settings（真实模型列表、手工 model、测试连接）
- Import & Analyze（可选择本次模型）
- Statistics
- Calendar 月历与议程时间线双视图
- 站内提醒中心，每 60 秒刷新，支持修改时间、关闭和标记已读
- Event 编辑、完成、取消和恢复操作，使用 InformationItem version 防并发覆盖

完成条件：
- 主流程无需 Swagger 即可从 UI 演示
- 所有列表支持 loading/error/empty 状态
- 月历与议程使用同一时间范围查询且事项一致，刷新页面后 Information 筛选条件保持
- npm run build 通过

## Phase 5 - 演示数据与健壮性

目标：
- 生成 >= 1000 条 synthetic messages
- >= 30 条有效 InformationItem
- >= 200 条关联记录
- 正常/异常/重复导入/AI失败测试
- 附件成功、重复、超时、超限、无效 URL、文件丢失、失败重试和越权测试
- 默认提醒、临近 Deadline、幂等扫描、自定义、关闭、已读及 Deadline 更新测试
- Information 单条件/组合筛选、多标签 OR、分页稳定、用户隔离和空结果测试
- 月历/议程范围切换、提醒中心刷新、附件状态和筛选持久化前端测试
- 登录失效、注册开关、停用用户和跨用户越权测试
- 在用户完成 NapCat 框架搭建后，再执行 NapCat 合成事件测试和真实手工联调：事件转换、字符串外部 ID、重复事件幂等、断线重连后的重复导入
- 准备固定 demo dataset
- 一键 reset + seed 脚本

完成条件：
- 课堂演示可重复
- 至少覆盖：重复消息、无用闲聊、AI失败、同一信息多消息支持、附件本地保存与失败重试、带 Deadline 的 Event 和站内提醒、组合筛选、月历与议程

## Phase 6 - 收尾

目标：
- 完整 README
- API 文档
- 数据字典
- ER 图字段与代码一致
- 同步 `pre/` 中需求、用例、业务流程、ER、模型图、演讲与 PPT 材料的附件和提醒口径
- 导出数据库 schema
- 记录统计 SQL
- 报告素材截图清单
- 最终测试

完成条件：
- `docs/ACCEPTANCE.md` 全部勾选
- 后端测试通过
- 前端 build 通过
- clean clone 后按 README 可启动
