# ACCEPTANCE.md

# 课程设计 MVP 验收清单

## 数据库
- [x] MySQL 8 可从空库通过 Alembic 创建全部表
- [x] 16 张核心表存在
- [x] information_item.version 乐观锁字段存在且并发更新不会静默覆盖
- [x] 主键/外键/唯一约束正确
- [x] user 与 system_setting 存在，system_setting 仅允许登记键
- [x] 跨用户 Message/InformationItem/Tag 关联被数据库拒绝
- [x] Event.information_id 为 UNIQUE
- [x] EventReminder.event_id 为 UNIQUE，且 `(reminder_status, remind_at)` 索引存在
- [x] Message 防重复导入
- [x] Message 的完全重复返回 DUPLICATE；同外部 ID 核心内容冲突返回 DUPLICATE_CONFLICT 且不覆盖原文
- [x] 关键索引存在
- [x] `(process_status, processing_started_at)` 支持陈旧 PROCESSING 恢复
- [x] 至少 3 个统计查询或 View
- [x] 至少 1 个数据库级自动维护机制
- [x] `sp_channel_statistics(p_user_id, p_start, p_end)` Stored Procedure 存在并通过当前用户调用测试
- [x] 演示数据中实体数据 >= 30
- [x] 演示数据中关系数据 >= 200

## 后端
- [x] /health
- [x] 普通用户登录/退出/改密
- [x] registration_enabled 默认关闭且能控制注册接口
- [x] 管理员命令行初始化/重置密码
- [x] 管理员未初始化时登录返回 503 ADMIN_NOT_INITIALIZED，不存在默认管理员密码
- [x] 独立管理员登录
- [x] 管理员创建、启停、重置普通用户
- [x] 管理员维护 Platform、Category 和注册开关
- [x] 敏感系统设置不通过 API 返回
- [x] HttpOnly Cookie、CSRF 和 session version 失效机制
- [x] Platform/Channel 基础管理
- [x] Message JSON 和 CSV 导入
- [x] 导入只使用管理员预置的 ACTIVE Platform，不隐式创建或更新 Platform
- [x] NapCat OneBot 11 bridge 调用方法已实现且默认 NAPCAT_ENABLED=false
- [ ] 用户完成 NapCat 框架搭建后，合成事件与真实手工联调通过：字符串 ID、重复事件、附件段、重连和登录恢复
- [x] Message 查询/分页/过滤
- [x] 附件自动下载到受控本地目录，数据库保存相对存储键、校验值和状态
- [x] 附件失败不回滚 Message，支持重试；下载鉴权且不暴露服务器绝对路径
- [x] 运行时无 MockAIProvider
- [x] 真实 OpenAI-compatible Provider
- [x] AI Base URL / API Key / default model 可通过环境变量配置
- [x] GET /ai/models 可从真实服务读取模型列表，或明确报告不支持
- [x] 可手工输入模型 ID
- [x] POST /ai/test 可真实测试所选模型
- [x] 单条/批量分析可指定模型
- [x] AIAnalysis.model_name 保存实际使用模型
- [x] 单条/批量 Analyze
- [x] AI 顶层只有 useful；每个 item 独立保存 importance/confidence/action/target/relation
- [x] action/target/relation 合法组合被严格校验
- [x] retry 只处理 PENDING/FAILED 并写业务；compare 只处理 PROCESSED/IGNORED 且不改业务
- [x] Provider AUTH_ERROR/MODEL_NOT_FOUND 返回 502，限流 429，超时 504；本站会话失败才返回 401
- [x] AIAnalysis 持久化
- [x] AIAnalysis 持久化 SUCCEEDED/FAILED、错误码、耗时和脱敏原始响应
- [x] InformationItem 创建/链接/更新
- [x] Category
- [x] Tag
- [x] Event
- [x] 带 Deadline 的 Event 原子生成默认提前 24 小时的 EventReminder
- [x] 提醒到期扫描幂等，支持修改时间、关闭和已读，且不覆盖用户自定义
- [x] 20 条/5 分钟自动分析窗口原子抢占，超过 10 分钟的 PROCESSING 可恢复
- [x] Event 状态扫描维护 UPCOMING/ONGOING/EXPIRED，用户可完成、取消和恢复
- [x] Event deadline 到点优先 EXPIRED，start_at 到点进入 ONGOING；恢复后按当前时间重新推导
- [x] PATCH 正确区分未传、显式 null 和空数组；时间范围按 `[start,end)` 处理
- [x] Information 分类/标签/重要度/状态/信息时间/事项时间/关键词组合筛选
- [x] 统计 API
- [x] 错误处理和日志
- [x] pytest 通过

## 前端
- [x] 普通用户登录、按开关显示注册、修改密码
- [x] 独立管理员登录和管理面板
- [x] Dashboard
- [x] Information 列表
- [x] Information 筛选条件与分页写入 URL，刷新后保持
- [x] Information 详情及原始来源
- [x] Message 列表展示附件状态并支持下载和失败重试
- [x] Sources
- [x] AI Settings / Model Selection
- [x] Import / Analyze
- [x] Statistics
- [x] Calendar 月历与议程时间线双视图
- [x] 站内提醒中心每 60 秒刷新，支持修改、关闭和已读
- [x] Event 编辑/完成/取消/恢复与乐观锁冲突提示
- [x] 中文 UI
- [x] npm run build 通过

## 业务演示
- [ ] 展示管理员创建用户或启用注册
- [ ] 展示两个用户的数据相互隔离
- [ ] 导入模拟消息
- [ ] 展示闲聊过滤
- [ ] 展示真实 API 模型选择和连接测试
- [ ] 展示真实 AIAnalysis
- [ ] 展示有效信息生成
- [ ] 展示多条 Message 支持同一 InformationItem
- [ ] 展示 Category
- [ ] 展示 Tag
- [ ] 展示 deadline -> Event
- [ ] 展示附件本地保存、鉴权下载及失败重试
- [ ] 展示 Deadline 自动生成提醒、到期显示和用户处理
- [ ] 展示标签/重要度/时间组合筛选及刷新保持
- [ ] 展示月历与议程中的同一事项
- [ ] 展示至少 3 项统计
- [ ] 展示错误/重复数据处理
- [ ] 展示管理员无法进入用户私有内容

## 文档
- [x] README
- [x] DATABASE.md
- [x] API.md
- [x] 数据字典
- [x] ER 图和真实表结构一致
- [x] 演示稿、用例图、业务流程图和 ER/模型图与 16 表设计一致
- [x] 演示步骤文档
- [x] 测试说明
- [x] `.env.example` 与 CONFIGURATION.md 字段一致，项目不包含 Docker Compose

## 2026-09-01 验证记录

- 空测试库：`alembic downgrade base -> upgrade head -> current -> check` 通过，head 为 `8f3c0d29a2b7`。
- MySQL：8.0.46、`utf8mb4`、`utf8mb4_0900_ai_ci`、session time zone `+00:00`。
- Backend：`pytest -q` 44 passed；`ruff check .` 通过；OpenAPI 55 paths。
- Frontend：`npm run build` 通过；`npm test -- --run` 2 passed（存在非阻塞的 bundle size warning）。
- Demo seed（在专用测试库验证）：1006 Messages、34 InformationItems、238 MessageInformation、24 Events、24 EventReminders、24 Attachments。
- Phase 6 静态校验：12 个收尾文件、43 个环境变量、16 张核心表、6 个数据库高级对象全部通过。
- 业务演示项保持未勾选，表示尚未按 `docs/DEMO_SCRIPT.md` 完整录屏/课堂走查；真实 AI 与 NapCat 项不得用 seed 或 mock 替代。
