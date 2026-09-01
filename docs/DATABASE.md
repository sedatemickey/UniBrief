# 数据库逻辑模型（多用户 MVP）

数据库：MySQL 8.x，字符集 `utf8mb4`。

时间约定：所有 API 输入必须是带时区的 ISO 8601；后端统一转换为 UTC，MySQL `DATETIME` 保存无时区 UTC，API 返回 UTC，前端按 `Asia/Shanghai` 显示。演示数据和统计时间范围遵守同一规则。

> 本文件是数据库结构的业务源事实。修改 ORM 前先更新设计并通过 Alembic migration 实现。

## 1. 多用户边界

- 普通用户之间的数据完全隔离。
- `platform`、`category` 和非敏感系统配置全局共享。
- `channel`、`sender`、`message`、`information_item`、`tag` 属于具体用户；附件、事项和提醒通过父实体继承归属。
- 子表通过父实体继承归属；关键关联使用复合外键阻止跨用户连接。
- 管理员只有账号和全局字典管理权限，不能读取用户消息或有效信息。
- 普通业务 API 不接受客户端传入的 `user_id`，归属从登录会话取得。

## 2. user

用途：普通登录用户，不代表群聊中的消息发送者。

字段：
- `id` BIGINT PK
- `username` VARCHAR(64) NOT NULL UNIQUE
- `display_name` VARCHAR(128) NOT NULL
- `password_hash` VARCHAR(255) NOT NULL
- `status` VARCHAR(32) NOT NULL DEFAULT 'ACTIVE'
- `session_version` INT UNSIGNED NOT NULL DEFAULT 1
- `last_login_at` DATETIME NULL
- `created_at` DATETIME NOT NULL
- `updated_at` DATETIME NOT NULL

状态：`ACTIVE`、`DISABLED`。用户不物理删除；停用或重置密码时递增 `session_version`，使旧会话失效。

## 3. system_setting

用途：保存少量、受控的系统级设置，取代专用管理员凭据表。

字段：
- `setting_key` VARCHAR(128) PK
- `value_text` TEXT NOT NULL
- `value_type` VARCHAR(32) NOT NULL
- `is_sensitive` BOOLEAN NOT NULL DEFAULT FALSE
- `description` VARCHAR(255) NULL
- `updated_at` DATETIME NOT NULL

首批允许键：

| setting_key | value_type | sensitive | 默认/用途 |
|---|---|---:|---|
| `registration_enabled` | BOOLEAN | 否 | `false`；控制公开注册接口 |
| `admin_password_hash` | SECRET | 是 | 管理员 Argon2id 密码哈希 |
| `admin_session_version` | INTEGER | 是 | 默认 `1`；改密后递增以注销旧管理会话 |

规则：
- 键名和类型必须在服务端白名单中登记，未知键不得通过 API 创建。
- BOOLEAN 只接受 `true`/`false`，INTEGER 必须严格解析；SECRET 只允许专用服务读写。
- 敏感值不通过普通设置接口、日志或异常返回。
- AI API Key 仍只保存在服务端环境变量，不进入本表。
- 本表不得保存用户业务对象、列表或本应通过关系建模的数据。
- 初始 migration 只插入 `registration_enabled=false` 和 `admin_session_version=1`；`admin_password_hash` 必须由交互式管理员初始化命令创建，禁止在 migration、seed 或 `.env.example` 中放默认管理员密码。
- `admin_password_hash` 尚不存在时，管理员登录返回 503 `ADMIN_NOT_INITIALIZED`，不得把“未初始化”伪装成普通密码错误。

## 4. platform

用途：全局消息平台字典，例如 QQ、微信、钉钉。

字段：`id` BIGINT PK、`name` VARCHAR(64) NOT NULL UNIQUE、`type` VARCHAR(32) NOT NULL、`status` VARCHAR(32) NOT NULL DEFAULT 'ACTIVE'、`created_at` DATETIME NOT NULL。

状态：`ACTIVE`、`DISABLED`。Platform 不物理删除；普通导入只能使用已存在且 ACTIVE 的 Platform，Adapter 不得隐式创建或修改全局 Platform。

## 5. channel

用途：某用户导入的具体群聊或消息渠道。

字段：
- `id` BIGINT PK
- `user_id` BIGINT NOT NULL FK -> user.id
- `platform_id` BIGINT NOT NULL FK -> platform.id
- `external_id` VARCHAR(128) NOT NULL
- `name` VARCHAR(255) NOT NULL
- `channel_type` VARCHAR(32) NOT NULL
- `created_at` DATETIME NOT NULL

约束：`UNIQUE(user_id, platform_id, external_id)`、`UNIQUE(user_id, id)`；`user_id`、`platform_id` 使用 `ON DELETE RESTRICT`。

## 6. sender

用途：某用户消息库中的外部发送者，不是登录 User。

字段：
- `id` BIGINT PK
- `user_id` BIGINT NOT NULL FK -> user.id
- `platform_id` BIGINT NOT NULL FK -> platform.id
- `external_id` VARCHAR(128) NOT NULL
- `display_name` VARCHAR(255) NOT NULL
- `source_type` VARCHAR(32) NOT NULL DEFAULT 'UNKNOWN'
- `credibility` DECIMAL(4,3) NOT NULL DEFAULT 0.500
- `created_at` DATETIME NOT NULL

约束：`UNIQUE(user_id, platform_id, external_id)`、`UNIQUE(user_id, id)`；可信度由 MySQL CHECK 和 Pydantic 同时限制为 0 至 1；`user_id`、`platform_id` 使用 `ON DELETE RESTRICT`。

## 7. message

用途：保存用户的原始消息，是核心大表。

字段：
- `id` BIGINT PK
- `user_id` BIGINT NOT NULL FK -> user.id
- `channel_id` BIGINT NOT NULL
- `sender_id` BIGINT NOT NULL
- `external_id` VARCHAR(191) NOT NULL
- `content` TEXT NOT NULL；纯附件消息允许空字符串，不允许 NULL
- `sent_at` DATETIME NOT NULL
- `ingested_at` DATETIME NOT NULL
- `process_status` VARCHAR(32) NOT NULL DEFAULT 'PENDING'
- `processing_started_at` DATETIME NULL

约束：
- `UNIQUE(user_id, channel_id, external_id)`；
- `UNIQUE(user_id, id)`；
- `FK(user_id, channel_id) -> channel(user_id, id)`；
- `FK(user_id, sender_id) -> sender(user_id, id)`。

状态：`PENDING`、`PROCESSING`、`PROCESSED`、`FAILED`、`IGNORED`。

处理规则：进入 `PROCESSING` 时写入 `processing_started_at`；成功、失败或忽略时清空。周期任务可将超过 10 分钟仍为 `PROCESSING` 的 Message 原子恢复为 `FAILED`，之后允许用户或自动窗口重试。

索引：
- `(user_id, channel_id, sent_at)`；
- `(user_id, sender_id, sent_at)`；
- `(user_id, process_status, ingested_at)`；
- `(process_status, processing_started_at)`，用于单实例陈旧任务恢复。

导入幂等与冲突规则：
- 导入按 Platform 名称查找已存在 ACTIVE Platform；不存在、停用或请求中的 `platform.type` 与数据库不一致时，单条结果返回 `PLATFORM_NOT_AVAILABLE`，不得由普通用户导入隐式创建/修改 Platform。
- `(user_id, channel_id, external_id)` 已存在且核心字段 `sender_id/content/sent_at` 一致时返回 `DUPLICATE`，不新增 Message。
- 同一外部 ID 已存在但任一核心字段不一致时返回 `DUPLICATE_CONFLICT`，保留原 Message，不静默覆盖证据。
- 重复导入可按 `UNIQUE(message_id, external_id)` 幂等补充此前不存在的附件元数据；已有附件不重复创建。

## 8. message_attachment

用途：保存附件来源、受控本地文件的定位信息和下载生命周期。文件本体不存入 MySQL。

字段：
- `id` BIGINT PK
- `message_id` BIGINT NOT NULL FK -> message.id ON DELETE CASCADE
- `external_id` VARCHAR(191) NOT NULL
- `file_type` VARCHAR(64) NULL
- `file_name` VARCHAR(255) NOT NULL
- `file_url` VARCHAR(1024) NOT NULL
- `storage_key` VARCHAR(512) NULL
- `file_size` BIGINT UNSIGNED NULL
- `sha256` CHAR(64) NULL
- `download_status` VARCHAR(32) NOT NULL DEFAULT 'PENDING'
- `download_attempts` INT UNSIGNED NOT NULL DEFAULT 0
- `downloaded_at` DATETIME NULL
- `last_error` VARCHAR(512) NULL
- `extracted_text` TEXT NULL
- `created_at` DATETIME NOT NULL
- `updated_at` DATETIME NOT NULL

约束和规则：
- `UNIQUE(message_id, external_id)` 防止同一消息重复保存同一附件；Adapter 未提供附件外部 ID 时，由稳定的 URL 与文件名生成。
- 状态为 `PENDING`、`DOWNLOADING`、`DOWNLOADED`、`FAILED`、`SKIPPED`。
- `storage_key` 只保存相对于 `ATTACHMENT_STORAGE_DIR` 的键，不保存或返回服务器绝对路径。
- 仅下载受控 HTTP/HTTPS 地址，并限制大小、超时和重试次数；`last_error` 必须脱敏。
- Message 和附件元数据先入库；文件下载失败只把附件标为 `FAILED`，不得回滚或丢失 Message。
- 下载在 Message 事务提交后执行；使用临时文件写入，大小和 SHA-256 校验成功后原子重命名到最终 `storage_key`。
- 下载器限制重定向次数，在每次 DNS 解析和重定向后拒绝本机、私网、链路本地和保留地址；禁止路径穿越、符号链接逃逸，只信任实际接收字节数。
- 应用启动时扫描遗留 `PENDING` 和超时 `DOWNLOADING`；磁盘文件缺失时不得伪装成功，应标记失败并允许重试。

## 9. ai_analysis

用途：某条 Message 的一次 AI 分析记录，支持重新分析和模型对比。

字段：
- `id` BIGINT PK
- `message_id` BIGINT NOT NULL FK -> message.id
- `model_name` VARCHAR(255) NOT NULL
- `status` VARCHAR(32) NOT NULL，`SUCCEEDED` / `FAILED`
- `useful` BOOLEAN NULL
- `error_code` VARCHAR(64) NULL
- `error_message` VARCHAR(512) NULL，必须脱敏
- `latency_ms` INT UNSIGNED NULL
- `raw_result` JSON NULL，仅保存通过结构校验的 JSON 审计副本
- `raw_response_text` MEDIUMTEXT NULL，保存截断、脱敏后的非法或非 JSON 响应
- `analyzed_at` DATETIME NOT NULL
- `created_at` DATETIME NOT NULL

规则：每次请求、重试或 compare 都保存独立 AIAnalysis，不设置 `(message_id, model_name)` 唯一约束。失败请求也必须保存错误分类；`raw_result` 和 `raw_response_text` 不替代正式业务关系。顶层只保存 Message 级 `useful`，`importance`、`confidence` 和 `summary` 属于 `raw_result.items[]` 及最终 InformationItem，不在 AIAnalysis 上保存容易歧义的单值列。

索引：`(message_id, analyzed_at)`。AI 原始 JSON 不得代替业务关系。

## 10. information_item

用途：用户最终保留的有效信息。

字段：
- `id` BIGINT PK
- `user_id` BIGINT NOT NULL FK -> user.id ON DELETE RESTRICT
- `title` VARCHAR(255) NOT NULL
- `summary` TEXT NOT NULL
- `source_type` VARCHAR(32) NOT NULL
- `importance` TINYINT NOT NULL
- `confidence` DECIMAL(4,3) NOT NULL
- `status` VARCHAR(32) NOT NULL DEFAULT 'ACTIVE'
- `version` INT UNSIGNED NOT NULL DEFAULT 1
- `created_at` DATETIME NOT NULL
- `updated_at` DATETIME NOT NULL

约束：`UNIQUE(user_id, id)`。状态：`ACTIVE`、`UPDATED`、`EXPIRED`、`ARCHIVED`。

索引：`(user_id, status, importance, created_at)`。

乐观锁：更新前必须比较调用方读取到的 `version`，更新语句使用 `WHERE id=:id AND user_id=:user_id AND version=:expected_version`，成功时 `version=version+1`。影响行数为 0 表示并发冲突；AI 流程最多重新读取候选并重试一次，仍冲突则记录可重试失败，禁止静默覆盖。

## 11. message_information

用途：Message 与 InformationItem 的 M:N 证据关系。

字段：`user_id` BIGINT NOT NULL、`message_id` BIGINT NOT NULL、`information_id` BIGINT NOT NULL、`relation_type` VARCHAR(32) NOT NULL、`created_at` DATETIME NOT NULL。

约束：
- `PRIMARY KEY(message_id, information_id)`；
- `FK(user_id, message_id) -> message(user_id, id)`；
- `FK(user_id, information_id) -> information_item(user_id, id)`。

关系类型：`CREATE`、`SUPPORT`、`UPDATE`、`CORRECTION`。复合外键保证消息和信息属于同一用户。

删除规则：`message_information`、`information_category`、`information_tag` 随其直接父实体删除使用 `ON DELETE CASCADE`；正常业务不提供删除 Message/InformationItem 的接口，级联主要服务于测试 reset 和受控维护。

## 12. category / information_category

`category` 是全局、稳定的粗粒度分类：`id` BIGINT PK、`name` VARCHAR(64) NOT NULL UNIQUE、`description` VARCHAR(255) NULL、`status` VARCHAR(32) NOT NULL DEFAULT 'ACTIVE'、`created_at` DATETIME NOT NULL。

`information_category` 的 `information_id`、`category_id` 均 NOT NULL，使用 `(information_id, category_id)` 联合主键和两个真实外键；关联随 InformationItem 删除而 CASCADE，Category 一侧 RESTRICT。Category 可被管理员停用；被历史数据引用时不物理删除。

## 13. tag / information_tag

`tag` 是用户私有的细粒度标签：`id` BIGINT PK、`user_id` BIGINT NOT NULL FK -> user.id ON DELETE RESTRICT、`name` VARCHAR(128) NOT NULL、`created_at` DATETIME NOT NULL，约束 `UNIQUE(user_id, name)` 和 `UNIQUE(user_id, id)`。

`information_tag` 字段 `user_id`、`information_id`、`tag_id` 均 NOT NULL，使用 `(information_id, tag_id)` 联合主键，并通过两组复合外键保证 InformationItem 与 Tag 属于同一用户；关联随 InformationItem 删除而 CASCADE，Tag 一侧 RESTRICT。

## 14. event

用途：有明确时间属性的 InformationItem 转化出的事项。

字段：`id` BIGINT PK、`information_id` BIGINT NOT NULL FK -> information_item.id ON DELETE CASCADE + UNIQUE、`start_at` DATETIME NULL、`deadline` DATETIME NULL、`event_status` VARCHAR(32) NOT NULL DEFAULT 'UPCOMING'、`created_at` DATETIME NOT NULL、`updated_at` DATETIME NOT NULL。

状态：`UPCOMING`、`ONGOING`、`COMPLETED`、`EXPIRED`、`CANCELLED`。索引：`(deadline)`、`(event_status, deadline)`。查询 Event 时必须通过 InformationItem 限定当前用户。

约束：`start_at` 与 `deadline` 至少一个非 NULL；两者同时存在时 `deadline >= start_at`。`COMPLETED`、`CANCELLED` 由用户操作；周期任务按以下顺序和条件更新，比较均使用 UTC：
- `deadline IS NOT NULL AND now >= deadline`：`UPCOMING/ONGOING -> EXPIRED`；
- 否则 `start_at IS NOT NULL AND now >= start_at`：`UPCOMING -> ONGOING`；
- 只有 deadline 的 Event 在到期前保持 UPCOMING，到期直接 EXPIRED；只有 start_at 的 Event 到点进入 ONGOING，不自动 EXPIRED；
- COMPLETED/CANCELLED 不被周期任务改写；用户恢复为 UPCOMING 后，下次扫描立即按当前时间推导 ONGOING/EXPIRED。

## 15. event_reminder

用途：带 Deadline 的 Event 的站内提醒。每个 Event 在 MVP 中至多有一个提醒。

字段：
- `id` BIGINT PK
- `event_id` BIGINT NOT NULL UNIQUE FK -> event.id ON DELETE CASCADE
- `remind_at` DATETIME NOT NULL
- `reminder_status` VARCHAR(32) NOT NULL DEFAULT 'PENDING'
- `is_custom_time` BOOLEAN NOT NULL DEFAULT FALSE
- `triggered_at` DATETIME NULL
- `read_at` DATETIME NULL
- `created_at` DATETIME NOT NULL
- `updated_at` DATETIME NOT NULL

状态：`PENDING`、`DUE`、`READ`、`DISABLED`。索引：`(reminder_status, remind_at)`，用于周期任务扫描所有到期且未关闭的提醒。

规则：
- 创建带 Deadline 的 Event 时，在同一事务内创建 `remind_at = deadline - 24 hours` 的提醒；若计算结果不晚于当前时间，则创建后可立即进入 `DUE`。
- 用户修改提醒时间后设置 `is_custom_time=true`；用户可将提醒设为 `DISABLED`。
- Event 的 Deadline 更新时，默认提醒重新计算；即使旧提醒为 `READ`，也视为新的截止时间提醒并重新进入 `PENDING` 或 `DUE`。自定义提醒不改时间，`DISABLED` 提醒绝不自动重启。
- `READ` 仅表示用户已读；Event 完成、取消或过期后，尚未触发的提醒不再转为 `DUE`。
- Event 完成、取消或过期时，尚未触发的提醒转为 `DISABLED`；新计算的 `remind_at` 已经过期时直接进入 `DUE`。
- 普通用户查询必须经 Event -> InformationItem 限定归属；管理员入口不得读取提醒内容。

## 16. 表数量与关系总览

16 张核心表：`user`、`system_setting`、`platform`、`channel`、`sender`、`message`、`message_attachment`、`ai_analysis`、`information_item`、`message_information`、`category`、`information_category`、`tag`、`information_tag`、`event`、`event_reminder`。

新增/调整的核心关系：
- User 1:N Channel、Sender、Message、InformationItem、Tag；
- Platform 与 Category 全局共享；
- Message 与 InformationItem、InformationItem 与 Tag 的关联必须同用户；
- Event 1 : 0..1 EventReminder，提醒通过 Event 和 InformationItem 继承用户归属；
- Admin 不作为 User 角色，凭据和注册开关由 system_setting 管理。

## 17. 删除与隐私策略

- User 使用 DISABLED，不物理删除；其业务数据继续保留。
- 管理员不得通过管理 API 查看用户 Message、InformationItem、Tag 或 Event。
- Platform、Category 采用停用，不破坏历史外键。
- Message 是证据，原则上不物理删除；InformationItem 使用 ARCHIVED。
- 专用 reset/seed 流程删除附件记录时必须同步清理对应本地文件，正常业务不提供绕过归属校验的文件删除接口。
- 越权访问统一返回 404，避免泄露其他用户资源是否存在。

## 18. 统计视图与高级对象

至少实现：
1. `v_upcoming_events`：必须包含 `user_id`，查询近期事项；
2. `v_channel_effectiveness`：按 `user_id` 和 Channel 统计消息量与有效率；有效消息定义为至少关联一个 InformationItem 的 distinct Message，有效率为有效消息数 / 总消息数；
3. `v_category_statistics`：按 `user_id` 统计分类数量；
4. 可选 `v_tag_popularity`：按用户统计 Tag 使用次数。

Trigger/自动维护：维护 `information_item.updated_at`。

Stored Procedure（必须实现）：`sp_channel_statistics(p_user_id, p_start, p_end)`，调用方只能传入当前认证用户 ID；权限校验仍由服务层完成。过程按 Message.sent_at 的半开区间 `[p_start,p_end)` 统计。过程和视图必须通过 Alembic migration 创建和删除。

## 19. CHECK 与删除策略

MySQL 8 migration 至少创建：
- `sender.credibility BETWEEN 0 AND 1`；
- `information_item.confidence BETWEEN 0 AND 1`；
- `information_item.importance BETWEEN 1 AND 5`；
- `event.start_at IS NOT NULL OR event.deadline IS NOT NULL`；
- `event.start_at IS NULL OR event.deadline IS NULL OR event.deadline >= event.start_at`。

删除策略：
- User、Platform、Category 不物理删除，使用状态停用；
- Message 原则上不删除；InformationItem 使用 `ARCHIVED`；
- AIAnalysis 和 MessageAttachment 对 Message 使用 `ON DELETE CASCADE`，仅供 reset/受控维护；
- Event 对 InformationItem、EventReminder 对 Event 使用 `ON DELETE CASCADE`；
- 删除 MessageAttachment 记录前，受控 reset/维护服务必须先确认并删除对应本地文件；失败时回滚数据库删除或记录可恢复错误。
