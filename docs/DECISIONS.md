# DECISIONS.md

# Architecture Decision Log

## D001 - 单用户 MVP
- Status: Superseded by D006
- Decision: 不实现 User / UserFeedback，不实现认证授权。
- Reason: 课程设计工期有限，单用户是当前真实需求。

## D002 - 不直接接入真实 QQ/微信/钉钉协议
- Status: Accepted
- Decision: 课程设计使用统一 Adapter 接口 + JSON/CSV/Mock 数据。
- Reason: 平台协议接入不是数据库课设核心，且实现风险高。

## D003 - Category + Tag 同时保留
- Status: Accepted
- Decision:
  - Category 用于稳定大类；
  - Tag 用于动态细粒度主题；
  - 两者均与 InformationItem 建立 M:N。
- Reason: 便于筛选、跨分类聚合和统计，同时能体现关系数据库建模。

## D004 - 只使用真实 OpenAI-compatible AI
- Status: Accepted
- Decision:
  - 产品运行时不提供 MockAIProvider；
  - API Key 和 Base URL 由服务端环境变量提供；
  - 前端能够加载真实模型列表、手工输入模型 ID、测试连接并选择模型；
  - 自动化测试可 mock HTTP transport，但课堂正常业务流程必须使用真实 AI。
- Reason: 项目需要具备真实可用的 AI 能力，而不是离线模拟。

## D005 - OpenAI-compatible 优先使用 Chat Completions
- Status: Accepted
- Decision:
  - MVP 优先兼容 `/v1/chat/completions` 风格服务；
  - 模型列表使用兼容的 `/v1/models`；
  - 若 `/models` 不可用，允许手工指定模型 ID。
- Reason: 第三方“OpenAI-compatible”实现对 Chat Completions 的兼容通常比新接口更广，且课程项目应控制复杂度。

## D006 - 多用户私有数据空间
- Status: Accepted
- Decision:
  - 普通用户使用唯一用户名登录，业务权限相同；
  - Channel、Sender、Message、InformationItem、Tag 按用户隔离；
  - Platform、Category 全局共享；
  - 不实现团队空间、用户间共享或多级 RBAC。
- Reason: 多用户应首先保证隐私和归属清晰，私人空间比协作模型更适合当前工期。

## D007 - 独立管理员入口与 system_setting
- Status: Accepted
- Decision:
  - 管理员不是普通 User 的角色；
  - 管理员登录只输入密码，密码哈希保存在受控的 `system_setting.admin_password_hash`；
  - `system_setting.registration_enabled` 控制公开注册，默认关闭；
  - 管理员可管理账号、Platform、Category，但不能读取用户私有内容；
  - 管理员密码通过交互式命令行初始化或重置。
- Reason: 通用设置表可承载少量系统级开关和秘密，同时避免为每个杂项设置新增一张表。

## D008 - system_setting 不是任意数据容器
- Status: Accepted
- Decision:
  - 设置键、类型和敏感性由服务端白名单定义；
  - 未登记键不能通过 API 创建；
  - SECRET 值不返回、不记录日志；
  - 用户业务对象及关系不得写入设置表。
- Reason: 保留设置扩展能力，同时防止键值表破坏关系模型和数据约束。

## D009 - Cookie 会话与失效机制
- Status: Accepted
- Decision:
  - 普通端和管理端使用不同 HttpOnly Cookie；
  - 写操作使用 CSRF 防护；
  - User 和管理员设置分别维护 session version；
  - 停用、改密或重置密码后旧会话失效。
- Reason: 避免前端脚本直接持有认证令牌，并能及时撤销旧会话。

## D010 - 附件使用本地文件存储
- Status: Accepted
- Decision:
  - 受控 HTTP/HTTPS 附件在 Message 入库后自动下载到 `ATTACHMENT_STORAGE_DIR`；
  - MySQL 只保存相对存储键、大小、SHA-256、状态、次数和脱敏错误，不保存 BLOB 或服务器绝对路径；
  - 下载大小、超时和最大重试次数通过环境变量配置，默认分别为 20 MiB、30 秒和 2 次；
  - 下载器拒绝本机、私网和链路本地目标，重定向后的地址必须重新校验；
  - 下载失败不得回滚 Message，并提供鉴权下载与失败重试接口。
- Reason: 长期保留附件以避免来源链接过期，同时控制数据库体积并保持原始消息优先落库。

## D011 - 单提醒站内通知
- Status: Accepted
- Decision:
  - 每个带 Deadline 的 Event 在 MVP 中至多有一个 EventReminder，默认提前 24 小时；
  - 用户可修改提醒时间、关闭提醒或标记已读，AI 更新 Deadline 不覆盖用户自定义或关闭状态；
  - 同进程周期任务使用幂等数据库更新扫描到期提醒，前端每 60 秒读取当前用户的站内提醒；
  - 不引入 Redis、消息队列、邮件、浏览器推送或多提醒规则。
- Reason: 完整兑现自动提醒并保留数据库状态，同时适合单机课堂演示和当前工期。

## D012 - 月历、议程与组合筛选
- Status: Accepted
- Decision:
  - Event 使用同一时间范围 API 支撑月历和议程时间线；
  - Information 支持分类、多个标签、重要度、状态、信息时间、事项时间和关键词组合筛选；
  - 多标签内部使用 OR，不同筛选维度使用 AND，筛选、排序与分页保存在 URL。
- Reason: 让结构化信息能够按演讲稿中的标签、重要程度和时间被实际利用，并保证两个事项视图口径一致。

## D013 - InformationItem 使用乐观锁
- Status: Accepted
- Decision:
  - `information_item.version` 默认 1；每次内容或 Event 更新成功后递增；
  - 人工更新必须提交 expected_version，冲突返回 409；
  - AI 更新冲突时最多重新读取候选并重新调用一次，仍冲突则记录可重试失败。
- Reason: AI HTTP 请求期间不能持有数据库长事务，版本字段可以防止并发结果静默覆盖更新较新的信息。

## D014 - AIAnalysis 同时记录成功和失败尝试
- Status: Accepted
- Decision:
  - 每次请求/重试保存一条 AIAnalysis，不使用 message_id+model_name 唯一约束；
  - 记录 status、error_code、脱敏 error_message、latency_ms、raw_result 或截断的 raw_response_text；
  - 批量 AI 按 Message 独立短事务，允许部分成功。
- Reason: Message 的最终状态不足以解释历史失败；持久化尝试记录便于重试、演示健壮性和审计。

## D015 - UTC 存储与上海时区显示
- Status: Accepted
- Decision:
  - API 只接受带时区 ISO 8601；
  - 后端转 UTC，MySQL DATETIME 解释为无时区 UTC，API 返回 UTC；
  - 前端和课堂演示按 Asia/Shanghai 显示。
- Reason: 防止 Deadline、提醒、日历和未来 7 天统计产生 8 小时偏差。

## D016 - 单实例后台扫描
- Status: Accepted
- Decision:
  - Phase 3 使用单进程任务处理 20 条/5 分钟 AI 窗口、PROCESSING 恢复、Event 状态和 Reminder 到期；
  - AI 每 30 秒扫描，超过 10 分钟的 PROCESSING 视为陈旧；
  - 不引入 Redis/Celery，也不宣称多实例分布式调度能力。
- Reason: 满足课堂单机演示，同时把并发和崩溃恢复状态保存在数据库中。

## D017 - NapCat OneBot 11 作为默认关闭的 QQ Adapter
- Status: Accepted
- Decision:
  - 使用独立桥接进程连接 NapCat OneBot 11 WebSocket Server；
  - 调用方法属于必须实现范围，但是否启用 QQ 接入由部署配置决定；
  - 每个桥接进程绑定一个普通用户，把 QQ 消息转换为统一 JSON 导入格式；
  - 外部 ID 按字符串保存；不新增凭据表，Secret 仅来自环境变量/交互输入；
  - UniBrief 不逆向 QQ 协议、不管理 QQ 账号、不发送消息、不自动回复。
- Reason: 在不污染数据库核心和权限模型的前提下提供真实 QQ 消息接入能力。

## D018 - Stored Procedure 为必做项
- Status: Accepted
- Decision: 必须通过 Alembic migration 创建 `sp_channel_statistics(p_user_id, p_start, p_end)`，并由 service 传入当前认证用户 ID。
- Reason: 实现成本低，能直接体现课程对数据库高级对象的综合运用要求。

## D019 - 用户管理 MySQL，不使用 Docker Compose
- Status: Accepted
- Decision:
  - MySQL 8.x 的安装、启动、端口、账号以及开发/测试数据库创建由用户负责；
  - 仓库不提供 Docker Compose，也不尝试管理 MySQL 服务；
  - 应用、Alembic 和 pytest 只通过 `DATABASE_URL` / `TEST_DATABASE_URL` 连接并验证版本、utf8mb4 和 UTC。
- Reason: 当前开发环境由用户直接维护 MySQL，减少无用的容器依赖和双重运行方式。

## D020 - Python 3.12.5 固定路径与 Vite 同源代理
- Status: Accepted
- Decision:
  - 使用 `C:\Users\ASUS\AppData\Local\Programs\Python\Python312\python.exe` 创建后端虚拟环境；
  - 不使用当前 MSYS2 PATH 命中的 Python 3.11.9；
  - Vite 把 `/api` 和 `/health` 代理到 FastAPI，前端只使用相对路径和 Cookie。
- Reason: 消除多 Python 安装造成的版本误判，并简化开发阶段 HttpOnly Cookie/CSRF 的同源行为。

## D021 - AI item 级置信度与 retry/compare
- Status: Accepted
- Decision:
  - AI 顶层只保留 `useful`，每个 item 各自包含 `importance` 和 `confidence`；
  - AIAnalysis 不保存歧义的单值 importance/confidence/summary，只保存 useful、状态、错误、耗时和原始审计结果；
  - `retry` 会写正式业务结果，`compare` 只追加 AIAnalysis，不修改 Message 或业务实体；
  - action/target/relation 采用固定兼容矩阵。
- Reason: 一条消息可能生成多个信息项，Message 级单值置信度无法准确表达结果；模型对比也不应覆盖既有业务数据。

## D022 - NapCat 先实现调用方法，后联调
- Status: Accepted
- Decision:
  - Phase 1 写好 OneBot WebSocket、映射、批量导入、重连和鉴权调用方法，默认 `NAPCAT_ENABLED=false`；
  - 在其他模块稳定且用户完成 NapCat 框架搭建前，不运行 NapCat 专项测试、不宣称联调完成；
  - 后续先跑合成事件，再做真实手工联调。
- Reason: 保留 QQ 接入能力，同时避免外部框架环境阻塞数据库、AI 和前端主线开发。

## D023 - 半开时间范围、PATCH 存在性与 Event 状态推导
- Status: Accepted
- Decision:
  - 普通列表和统计统一使用 `[start,end)`，Event 使用同一半开窗口的相交查询；
  - PATCH 未传表示保持，允许的显式 null 表示清空，空数组表示清空关联；
  - deadline 到点优先 EXPIRED，否则 start_at 到点进入 ONGOING；COMPLETED/CANCELLED 不被周期任务覆盖。
- Reason: 消除相邻窗口重复计数、前端清空字段歧义和事项状态随时间变旧的问题。
