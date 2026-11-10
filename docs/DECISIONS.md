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

## D024 - Phase 0 健康检查与数据库就绪检查分离
- Status: Accepted
- Decision:
  - `/health` 只验证 FastAPI 进程可响应，保证开发代理和部署探针轻量稳定；
  - `scripts/check_database.py` 专门验证 MySQL 8、utf8mb4 和 UTC 会话时区，并且只输出非敏感属性；
  - SQLAlchemy 在每次新连接上执行 `SET time_zone = '+00:00'`。
- Reason: 数据库暂时不可用时仍能区分应用进程状态与数据库配置错误，同时满足 Phase 0 对真实 MySQL 连接的独立验收。

## D025 - Repository / Service / Router 分层与短事务
- Status: Accepted
- Decision:
  - HTTP Router 只做请求依赖、schema 转换和响应状态处理；
  - SQL 查询集中到 `repositories/`，事务和业务状态转换集中到 `services/`；
  - 普通写操作由 service 明确 commit/rollback；批量导入按 Message 独立提交，允许部分成功；
  - 附件下载只在 Message 和附件元数据提交后执行，不持有长数据库事务。
- Reason: 满足仓库分层约束，并避免网络请求、批量处理或单条失败扩大事务锁和回滚范围。

## D026 - pytest 强制测试库与可重复 schema 重建
- Status: Accepted
- Decision:
  - `tests/conftest.py` 缺少 `TEST_DATABASE_URL` 时直接拒绝运行，不回退到开发库；
  - 集成测试只清理专用测试库并恢复 migration 种子；
  - 初始 migration 的 downgrade 直接按依赖顺序删除表，不先删除可能被 MySQL 外键复用的索引；
  - Phase 1 实际验证 `downgrade base -> 空 schema -> upgrade head`。
- Reason: 防止 pytest 污染开发数据，并保证课程演示前可以可靠地从空库重建完整结构。

## D027 - 运行时只保留真实 OpenAI-compatible Provider
- Status: Accepted
- Decision:
  - 产品代码只实现基于官方 `openai` Python SDK `AsyncOpenAI` 的 `OpenAICompatibleProvider`；
  - API Key 只从服务端环境变量读取，安全配置接口只返回 `has_api_key`；
  - `/models` 不支持时返回 `supports_listing=false`，不阻止手工输入模型 ID；
  - pytest 仅在 SDK/HTTP 边界使用测试替身，不提供可由应用选择的 MockAIProvider。
- Reason: 同时满足真实课堂演示、安全边界和自动化测试不消耗 Token 的要求。

## D028 - AI 请求与数据库业务写入分离为短事务
- Status: Accepted
- Decision:
  - retry 先用条件 UPDATE 抢占 Message 并提交，再执行不持有数据库事务的真实 AI 请求；
  - 严格校验成功后，在一个短事务中保存 AIAnalysis、Information、证据关系、分类标签、Event/Reminder 并更新 Message；
  - compare 只写独立 AIAnalysis，不改变 Message 状态和任何正式业务实体；
  - Provider、输出校验、并发或持久化失败均另行保存 FAILED AIAnalysis，并让 retry Message 回到 FAILED 可重试状态。
- Reason: 避免网络延迟扩大数据库锁范围，并保证不会留下半成品业务关系。

## D029 - AI 候选限制、乐观锁重试与默认提醒保护
- Status: Accepted
- Decision:
  - 候选只取当前用户最近 ACTIVE/UPDATED InformationItem，并用简单词/双字重叠做有限排序；
  - AI 只能引用候选 ID，update/correct 使用候选 version 条件更新；首次冲突重新取候选并最多重调 AI 一次；
  - 新建带 deadline 的 Event 同事务创建提前 24 小时提醒；默认提醒随 deadline 重算，用户自定义时间和 DISABLED 状态不被 AI 覆盖。
- Reason: 在不引入向量库的前提下满足用户隔离、去重关联、并发安全和提醒一致性。

## D030 - 统计高级对象全部通过 Alembic 管理
- Status: Accepted
- Decision:
  - migration 创建 `v_upcoming_events`、`v_channel_effectiveness`、`v_category_statistics`、`v_tag_popularity`；
  - `trg_information_item_set_updated_at` 负责数据库级更新时间维护；
  - `sp_channel_statistics(p_user_id,p_start,p_end)` 使用 Message.sent_at 的 `[start,end)`，Statistics service 只能传当前认证用户 ID；
  - downgrade 先删除 Procedure、Trigger 和 Views，再允许回退核心 schema。
- Reason: 让数据库课程要求可直接在 MySQL 中展示、可重复迁移，并保持用户隔离和时间口径统一。

## D031 - 单进程周期扫描复用现有短事务分析流程
- Status: Accepted
- Decision:
  - FastAPI lifespan 启动两个可取消的单进程 loop：Event/Reminder 扫描和自动 AI 窗口扫描；
  - 自动分析按同一 user/channel 聚合，达到配置数量或最早等待超时后取最旧一批，并复用手工 analyze 的逐 Message 条件抢占与短事务；
  - 无 AI Key/default model 时跳过自动调用但仍恢复 stale PROCESSING；
  - Event 扫描先以 deadline 为准过期，再根据 start_at 进入 ONGOING，COMPLETED/CANCELLED 不覆盖；Reminder 只用条件更新幂等推进。
- Reason: 满足单实例课堂部署要求，不引入 Redis、队列或伪分布式 Worker，同时复用已测试的数据一致性边界。

## D032 - Phase 4 以既有 API 契约驱动完整中文 UI
- Status: Accepted
  - 前端使用 React Router、TanStack Query 和集中 API client，不把 fetch 散落在页面；
  - 普通端与管理端完全分离，管理员入口无任何用户私有业务数据页面；
  - Information 分类、多标签 OR、重要度、状态、信息时间、事项时间、关键词、排序和分页统一写入 URL；
  - Calendar 月历与议程使用同一个 Event range API，前端按 Asia/Shanghai 展示、提交带时区 ISO 8601。
- Reason: 保证课程演示主流程不依赖 Swagger，并让筛选、刷新、前进后退和两个事项视图共享同一数据口径。

## D033 - UI 编辑必须携带当前乐观锁版本
- Status: Accepted
  - Information、Event 和 Reminder 编辑均从当前详情读取 version；
  - 后端冲突返回 409 VERSION_CONFLICT 与当前 version，前端显示冲突且不覆盖新数据；
  - Event 编辑同时递增父 InformationItem version，避免信息与事项状态失去同步。
- Reason: 将数据库并发正确性作为可演示功能，而不是只停留在 schema。

## D034 - Phase 6 导出材料不替代 Alembic
- Status: Accepted
- Decision:
  - `infra/schema.sql` 由 `alembic upgrade head --sql` 生成，用于报告、审阅和离线展示；
  - `infra/statistics.sql` 是高级对象的可读副本；
  - 实际部署、升级和回滚仍只执行 Alembic migration，不允许手工 SQL 成为第二套 schema 来源；
  - `scripts/verify_phase6.py` 静态核对文档、环境变量、16 表和高级对象，数据库真实性仍由 migration/pytest/MySQL 检查证明。
- Reason: 既满足课程报告需要的 schema/统计 SQL 材料，又避免静态 SQL 与 ORM/migration 形成双写漂移。

## D035 - 第一展示历史稿与最终实现口径分离
- Status: Accepted
- Decision:
  - `pre/00`–`04` 保留为已废止的单用户历史材料；
  - `pre/11`、`pre/12` 明确标记为第一次设计展示历史稿，可保留当时的未来时态；
  - 当前答辩、第二次系统演示与报告以 `docs/PROGRESS.md`、`docs/ER_MAPPING.md`、`docs/DEMO_SCRIPT.md` 和 16 表实现为准；
  - 真实 AI、NapCat 与 clean clone 未验证项必须明确保留，不用 seed 或 mock 伪造完成。
- Reason: 保留课程过程材料的同时，防止旧版阶段状态、13 表或单用户口径混入最终答辩。

## D036 - 课堂手工 AI 演示数据采用追加式独立消息集
- Status: Accepted
- Decision:
  - 新增固定 60 条的合成原始消息集，默认追加到 `demo_student`，不调用 reset、不删除或覆盖现有演示数据；
  - 通过正式 ingestion service 导入并使用固定 external ID 保证幂等，导入后必须验证全部 Message 为 PENDING；
  - 52 条有效消息按互不相干的独立主题设计，使 AI 优先执行 create；8 条普通闲聊用于展示 useful=false；
  - 消息分布在 7 个低于 20 条数量阈值的演示 Channel，覆盖通知、作业、课程考试、活动、行政生活和低可信度小道消息。
- Reason: 满足课堂“先展示原始消息、再手工批量调用真实 AI 形成实体与关系”的流程，同时避免伪造 AIAnalysis 或预写 InformationItem。

## D037 - Dashboard 状态卡片不复用历史统计时间窗
- Status: Accepted
- Decision:
  - Dashboard 的消息、有效信息、未来事项和到期提醒卡片调用无时间参数的 overview，展示当前用户全局状态总数；
  - 最近 29 天时间窗只用于渠道有效率与分类分布等趋势图；
  - `event_upcoming_total` 继续表示 UPCOMING/ONGOING 事项，`reminder_due_total` 继续只表示 DUE 提醒，不把 PENDING 提醒误计为到期。
- Reason: 历史窗口的 `end=当前时间` 会天然排除未来事项，且状态型 KPI 与历史趋势图不应共享同一时间口径。
