# ACCEPTANCE.md

# 课程设计 MVP 验收清单

## 数据库
- [ ] MySQL 8 可从空库通过 Alembic 创建全部表
- [ ] 16 张核心表存在
- [ ] information_item.version 乐观锁字段存在且并发更新不会静默覆盖
- [ ] 主键/外键/唯一约束正确
- [ ] user 与 system_setting 存在，system_setting 仅允许登记键
- [ ] 跨用户 Message/InformationItem/Tag 关联被数据库拒绝
- [ ] Event.information_id 为 UNIQUE
- [ ] EventReminder.event_id 为 UNIQUE，且 `(reminder_status, remind_at)` 索引存在
- [ ] Message 防重复导入
- [ ] Message 的完全重复返回 DUPLICATE；同外部 ID 核心内容冲突返回 DUPLICATE_CONFLICT 且不覆盖原文
- [ ] 关键索引存在
- [ ] `(process_status, processing_started_at)` 支持陈旧 PROCESSING 恢复
- [ ] 至少 3 个统计查询或 View
- [ ] 至少 1 个数据库级自动维护机制
- [ ] `sp_channel_statistics(p_user_id, p_start, p_end)` Stored Procedure 存在并通过当前用户调用测试
- [ ] 演示数据中实体数据 >= 30
- [ ] 演示数据中关系数据 >= 200

## 后端
- [ ] /health
- [ ] 普通用户登录/退出/改密
- [ ] registration_enabled 默认关闭且能控制注册接口
- [ ] 管理员命令行初始化/重置密码
- [ ] 管理员未初始化时登录返回 503 ADMIN_NOT_INITIALIZED，不存在默认管理员密码
- [ ] 独立管理员登录
- [ ] 管理员创建、启停、重置普通用户
- [ ] 管理员维护 Platform、Category 和注册开关
- [ ] 敏感系统设置不通过 API 返回
- [ ] HttpOnly Cookie、CSRF 和 session version 失效机制
- [ ] Platform/Channel 基础管理
- [ ] Message JSON 和 CSV 导入
- [ ] 导入只使用管理员预置的 ACTIVE Platform，不隐式创建或更新 Platform
- [ ] NapCat OneBot 11 bridge 调用方法已实现且默认 NAPCAT_ENABLED=false
- [ ] 用户完成 NapCat 框架搭建后，合成事件与真实手工联调通过：字符串 ID、重复事件、附件段、重连和登录恢复
- [ ] Message 查询/分页/过滤
- [ ] 附件自动下载到受控本地目录，数据库保存相对存储键、校验值和状态
- [ ] 附件失败不回滚 Message，支持重试；下载鉴权且不暴露服务器绝对路径
- [ ] 运行时无 MockAIProvider
- [ ] 真实 OpenAI-compatible Provider
- [ ] AI Base URL / API Key / default model 可通过环境变量配置
- [ ] GET /ai/models 可从真实服务读取模型列表，或明确报告不支持
- [ ] 可手工输入模型 ID
- [ ] POST /ai/test 可真实测试所选模型
- [ ] 单条/批量分析可指定模型
- [ ] AIAnalysis.model_name 保存实际使用模型
- [ ] 单条/批量 Analyze
- [ ] AI 顶层只有 useful；每个 item 独立保存 importance/confidence/action/target/relation
- [ ] action/target/relation 合法组合被严格校验
- [ ] retry 只处理 PENDING/FAILED 并写业务；compare 只处理 PROCESSED/IGNORED 且不改业务
- [ ] Provider AUTH_ERROR/MODEL_NOT_FOUND 返回 502，限流 429，超时 504；本站会话失败才返回 401
- [ ] AIAnalysis 持久化
- [ ] AIAnalysis 持久化 SUCCEEDED/FAILED、错误码、耗时和脱敏原始响应
- [ ] InformationItem 创建/链接/更新
- [ ] Category
- [ ] Tag
- [ ] Event
- [ ] 带 Deadline 的 Event 原子生成默认提前 24 小时的 EventReminder
- [ ] 提醒到期扫描幂等，支持修改时间、关闭和已读，且不覆盖用户自定义
- [ ] 20 条/5 分钟自动分析窗口原子抢占，超过 10 分钟的 PROCESSING 可恢复
- [ ] Event 状态扫描维护 UPCOMING/ONGOING/EXPIRED，用户可完成、取消和恢复
- [ ] Event deadline 到点优先 EXPIRED，start_at 到点进入 ONGOING；恢复后按当前时间重新推导
- [ ] PATCH 正确区分未传、显式 null 和空数组；时间范围按 `[start,end)` 处理
- [ ] Information 分类/标签/重要度/状态/信息时间/事项时间/关键词组合筛选
- [ ] 统计 API
- [ ] 错误处理和日志
- [ ] pytest 通过

## 前端
- [ ] 普通用户登录、按开关显示注册、修改密码
- [ ] 独立管理员登录和管理面板
- [ ] Dashboard
- [ ] Information 列表
- [ ] Information 筛选条件与分页写入 URL，刷新后保持
- [ ] Information 详情及原始来源
- [ ] Message 列表展示附件状态并支持下载和失败重试
- [ ] Sources
- [ ] AI Settings / Model Selection
- [ ] Import / Analyze
- [ ] Statistics
- [ ] Calendar 月历与议程时间线双视图
- [ ] 站内提醒中心每 60 秒刷新，支持修改、关闭和已读
- [ ] Event 编辑/完成/取消/恢复与乐观锁冲突提示
- [ ] 中文 UI
- [ ] npm run build 通过

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
- [ ] README
- [ ] DATABASE.md
- [ ] API.md
- [ ] 数据字典
- [ ] ER 图和真实表结构一致
- [ ] 演示稿、用例图、业务流程图和 ER/模型图与 16 表设计一致
- [ ] 演示步骤文档
- [ ] 测试说明
- [ ] `.env.example` 与 CONFIGURATION.md 字段一致，项目不包含 Docker Compose
