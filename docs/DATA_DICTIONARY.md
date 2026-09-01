# UniBrief 数据字典

> 基线：Alembic revision `8f3c0d29a2b7`，对应 `backend/app/models/entities.py` 与 `docs/DATABASE.md`。所有 MySQL `DATETIME` 均按 UTC 保存，API 返回 UTC，前端按 Asia/Shanghai 展示。

## 1. 通用约定

- 主键默认使用 `BIGINT AUTO_INCREMENT`；关联表使用联合主键。
- `TimestampMixin` 提供 `created_at DATETIME NOT NULL`、`updated_at DATETIME NOT NULL`。
- 用户私有资源以 `user_id` 归属，或通过受约束的父实体继承归属。
- 状态值集中定义于 `backend/app/core/enums.py`，数据库不使用 MySQL ENUM，便于 Alembic 演进。
- 删除策略以保留证据为先：User/Platform/Category 停用而不物理删除；受控 reset 才执行级联删除。

## 2. 实体表

### 2.1 `user`

| 字段 | 类型 | 空值/默认 | 键或约束 | 说明 |
|---|---|---|---|---|
| `id` | BIGINT | NOT NULL | PK | 普通用户 ID |
| `username` | VARCHAR(64) | NOT NULL | UNIQUE | 登录名 |
| `display_name` | VARCHAR(128) | NOT NULL |  | 显示名 |
| `password_hash` | VARCHAR(255) | NOT NULL |  | Argon2id 哈希 |
| `status` | VARCHAR(32) | `ACTIVE` |  | `ACTIVE/DISABLED` |
| `session_version` | INT UNSIGNED | `1` |  | 改密、停用、重置密码后使旧会话失效 |
| `last_login_at` | DATETIME | NULL |  | 最近登录时间 |
| `created_at` | DATETIME | 当前时间 |  | 创建时间 |
| `updated_at` | DATETIME | 当前时间 |  | 更新时间 |

### 2.2 `system_setting`

| 字段 | 类型 | 空值/默认 | 键或约束 | 说明 |
|---|---|---|---|---|
| `setting_key` | VARCHAR(128) | NOT NULL | PK | 仅允许代码登记的键 |
| `value_text` | TEXT | NOT NULL |  | 序列化后的设置值 |
| `value_type` | VARCHAR(32) | NOT NULL |  | `BOOLEAN/INTEGER/SECRET` |
| `is_sensitive` | BOOLEAN | `FALSE` |  | 敏感项不得通过普通 API 返回 |
| `description` | VARCHAR(255) | NULL |  | 设置说明 |
| `updated_at` | DATETIME | 当前时间 |  | 更新时间 |

初始键：`registration_enabled=false`、`admin_session_version=1`；管理员密码哈希由 CLI 初始化后写入登记的敏感键。

### 2.3 `platform`

| 字段 | 类型 | 空值/默认 | 键或约束 | 说明 |
|---|---|---|---|---|
| `id` | BIGINT | NOT NULL | PK | 平台 ID |
| `name` | VARCHAR(64) | NOT NULL | UNIQUE | 平台名称 |
| `type` | VARCHAR(32) | NOT NULL |  | 平台类型 |
| `status` | VARCHAR(32) | `ACTIVE` |  | `ACTIVE/DISABLED` |
| `created_at` | DATETIME | 当前时间 |  | 创建时间 |

### 2.4 `channel`

| 字段 | 类型 | 空值/默认 | 键或约束 | 说明 |
|---|---|---|---|---|
| `id` | BIGINT | NOT NULL | PK | 渠道 ID |
| `user_id` | BIGINT | NOT NULL | FK → `user.id` | 私有数据归属 |
| `platform_id` | BIGINT | NOT NULL | FK → `platform.id` | 所属平台 |
| `external_id` | VARCHAR(128) | NOT NULL | UQ 组成 | 外部群/会话 ID |
| `name` | VARCHAR(255) | NOT NULL |  | 渠道名称 |
| `channel_type` | VARCHAR(32) | NOT NULL |  | 群聊、私聊等 |
| `created_at` | DATETIME | 当前时间 |  | 创建时间 |

唯一约束：`(user_id, platform_id, external_id)`、`(user_id, id)`。

### 2.5 `sender`

| 字段 | 类型 | 空值/默认 | 键或约束 | 说明 |
|---|---|---|---|---|
| `id` | BIGINT | NOT NULL | PK | 发送者 ID |
| `user_id` | BIGINT | NOT NULL | FK → `user.id` | 私有数据归属 |
| `platform_id` | BIGINT | NOT NULL | FK → `platform.id` | 所属平台 |
| `external_id` | VARCHAR(128) | NOT NULL | UQ 组成 | 外部账号 ID |
| `display_name` | VARCHAR(255) | NOT NULL |  | 显示名 |
| `source_type` | VARCHAR(32) | `UNKNOWN` |  | `TEACHER/STUDENT/ADMIN/UNKNOWN` 等来源类型 |
| `credibility` | DECIMAL(4,3) | `0.500` | CHECK 0..1 | 可信度 |
| `created_at` | DATETIME | 当前时间 |  | 创建时间 |

唯一约束：`(user_id, platform_id, external_id)`、`(user_id, id)`。

### 2.6 `message`

| 字段 | 类型 | 空值/默认 | 键或约束 | 说明 |
|---|---|---|---|---|
| `id` | BIGINT | NOT NULL | PK | 原始消息 ID |
| `user_id` | BIGINT | NOT NULL | FK → `user.id` | 私有数据归属 |
| `channel_id` | BIGINT | NOT NULL | 复合 FK → `channel(user_id,id)` | 来源渠道 |
| `sender_id` | BIGINT | NOT NULL | 复合 FK → `sender(user_id,id)` | 发送者 |
| `external_id` | VARCHAR(191) | NOT NULL | UQ 组成 | 外部消息 ID |
| `content` | TEXT | NOT NULL |  | 原始消息正文 |
| `sent_at` | DATETIME | NOT NULL |  | 平台发送时间 |
| `ingested_at` | DATETIME | 当前时间 |  | 系统接入时间 |
| `process_status` | VARCHAR(32) | `PENDING` |  | `PENDING/PROCESSING/PROCESSED/FAILED/IGNORED` |
| `processing_started_at` | DATETIME | NULL |  | 抢占分析时间，用于恢复陈旧任务 |

唯一约束：`(user_id, channel_id, external_id)` 防重复导入；另有 `(user_id,id)` 支撑跨表同用户复合外键。

### 2.7 `message_attachment`

| 字段 | 类型 | 空值/默认 | 键或约束 | 说明 |
|---|---|---|---|---|
| `id` | BIGINT | NOT NULL | PK | 附件 ID |
| `message_id` | BIGINT | NOT NULL | FK → `message.id` CASCADE | 所属消息 |
| `external_id` | VARCHAR(191) | NOT NULL | UQ 组成 | 外部附件 ID |
| `file_type` | VARCHAR(64) | NULL |  | MIME/业务类型 |
| `file_name` | VARCHAR(255) | NOT NULL |  | 原文件名 |
| `file_url` | VARCHAR(1024) | NOT NULL |  | 下载 URL；日志需脱敏查询参数 |
| `storage_key` | VARCHAR(512) | NULL |  | 受控目录下相对键，不暴露绝对路径 |
| `file_size` | BIGINT UNSIGNED | NULL |  | 文件字节数 |
| `sha256` | VARCHAR(64) | NULL |  | 完整性校验值 |
| `download_status` | VARCHAR(32) | `PENDING` |  | `PENDING/DOWNLOADING/DOWNLOADED/FAILED/SKIPPED` |
| `download_attempts` | INT UNSIGNED | `0` |  | 尝试次数 |
| `downloaded_at` | DATETIME | NULL |  | 下载完成时间 |
| `last_error` | VARCHAR(512) | NULL |  | 脱敏错误摘要 |
| `extracted_text` | TEXT | NULL |  | 预留文本提取结果，MVP 不做复杂 OCR |
| `created_at` | DATETIME | 当前时间 |  | 创建时间 |
| `updated_at` | DATETIME | 当前时间 |  | 更新时间 |

唯一约束：`(message_id, external_id)`。

### 2.8 `ai_analysis`

| 字段 | 类型 | 空值/默认 | 键或约束 | 说明 |
|---|---|---|---|---|
| `id` | BIGINT | NOT NULL | PK | 分析记录 ID |
| `message_id` | BIGINT | NOT NULL | FK → `message.id` CASCADE | 被分析消息 |
| `model_name` | VARCHAR(255) | NOT NULL |  | 实际使用模型 ID |
| `status` | VARCHAR(32) | NOT NULL |  | `SUCCEEDED/FAILED` |
| `useful` | BOOLEAN | NULL |  | 是否为有效信息 |
| `error_code` | VARCHAR(64) | NULL |  | 规范化错误码 |
| `error_message` | VARCHAR(512) | NULL |  | 脱敏错误信息 |
| `latency_ms` | INT UNSIGNED | NULL |  | 上游耗时 |
| `raw_result` | JSON | NULL |  | 严格校验后的结构化结果 |
| `raw_response_text` | MEDIUMTEXT | NULL |  | 截断、脱敏后的原始响应 |
| `analyzed_at` | DATETIME | NOT NULL |  | 分析完成时间 |
| `created_at` | DATETIME | 当前时间 |  | 记录创建时间 |

### 2.9 `information_item`

| 字段 | 类型 | 空值/默认 | 键或约束 | 说明 |
|---|---|---|---|---|
| `id` | BIGINT | NOT NULL | PK | 有效信息 ID |
| `user_id` | BIGINT | NOT NULL | FK → `user.id` | 私有数据归属 |
| `title` | VARCHAR(255) | NOT NULL |  | 标题 |
| `summary` | TEXT | NOT NULL |  | 摘要 |
| `source_type` | VARCHAR(32) | NOT NULL |  | 信息来源类型 |
| `importance` | TINYINT | NOT NULL | CHECK 1..5 | 重要度 |
| `confidence` | DECIMAL(4,3) | NOT NULL | CHECK 0..1 | AI/系统置信度 |
| `status` | VARCHAR(32) | `ACTIVE` |  | `ACTIVE/UPDATED/EXPIRED/ARCHIVED` |
| `version` | INT UNSIGNED | `1` |  | 乐观锁版本 |
| `created_at` | DATETIME | 当前时间 |  | 创建时间 |
| `updated_at` | DATETIME | 当前时间 | Trigger 自动维护 | 更新时间 |

唯一约束：`(user_id,id)`；人工与 AI 更新均使用 `expected_version` 防止静默覆盖。

### 2.10 `category`

| 字段 | 类型 | 空值/默认 | 键或约束 | 说明 |
|---|---|---|---|---|
| `id` | BIGINT | NOT NULL | PK | 全局分类 ID |
| `name` | VARCHAR(64) | NOT NULL | UNIQUE | 分类名 |
| `description` | VARCHAR(255) | NULL |  | 描述 |
| `status` | VARCHAR(32) | `ACTIVE` |  | `ACTIVE/DISABLED` |
| `created_at` | DATETIME | 当前时间 |  | 创建时间 |

### 2.11 `tag`

| 字段 | 类型 | 空值/默认 | 键或约束 | 说明 |
|---|---|---|---|---|
| `id` | BIGINT | NOT NULL | PK | 标签 ID |
| `user_id` | BIGINT | NOT NULL | FK → `user.id` | 私有数据归属 |
| `name` | VARCHAR(128) | NOT NULL | UQ 组成 | 标签名 |
| `created_at` | DATETIME | 当前时间 |  | 创建时间 |

唯一约束：`(user_id,name)`、`(user_id,id)`。

### 2.12 `event`

| 字段 | 类型 | 空值/默认 | 键或约束 | 说明 |
|---|---|---|---|---|
| `id` | BIGINT | NOT NULL | PK | 事项 ID |
| `information_id` | BIGINT | NOT NULL | FK → `information_item.id` CASCADE；UNIQUE | 保证 InformationItem 1:0..1 Event |
| `start_at` | DATETIME | NULL | CHECK 组成 | 开始时间 |
| `deadline` | DATETIME | NULL | CHECK 组成 | 截止时间 |
| `event_status` | VARCHAR(32) | `UPCOMING` |  | `UPCOMING/ONGOING/COMPLETED/EXPIRED/CANCELLED` |
| `created_at` | DATETIME | 当前时间 |  | 创建时间 |
| `updated_at` | DATETIME | 当前时间 |  | 更新时间 |

CHECK：至少存在一个时间；两者都有时 `deadline >= start_at`。

### 2.13 `event_reminder`

| 字段 | 类型 | 空值/默认 | 键或约束 | 说明 |
|---|---|---|---|---|
| `id` | BIGINT | NOT NULL | PK | 提醒 ID |
| `event_id` | BIGINT | NOT NULL | FK → `event.id` CASCADE；UNIQUE | 每个 Event 至多一个提醒 |
| `remind_at` | DATETIME | NOT NULL | 索引组成 | 提醒时间 |
| `reminder_status` | VARCHAR(32) | `PENDING` | 索引组成 | `PENDING/DUE/READ/DISABLED` |
| `is_custom_time` | BOOLEAN | `FALSE` |  | 用户是否自定义时间 |
| `triggered_at` | DATETIME | NULL |  | 首次到期时间 |
| `read_at` | DATETIME | NULL |  | 已读时间 |
| `created_at` | DATETIME | 当前时间 |  | 创建时间 |
| `updated_at` | DATETIME | 当前时间 |  | 更新时间 |

索引：`(reminder_status, remind_at)`。

## 3. 关联表

### 3.1 `message_information`

| 字段 | 类型 | 键或约束 | 说明 |
|---|---|---|---|
| `user_id` | BIGINT | 复合 FK 组成 | 关系所属用户 |
| `message_id` | BIGINT | PK 组成；复合 FK → `message(user_id,id)` CASCADE | 原始消息 |
| `information_id` | BIGINT | PK 组成；复合 FK → `information_item(user_id,id)` CASCADE | 有效信息 |
| `relation_type` | VARCHAR(32) |  | `CREATE/SUPPORT/UPDATE/CORRECTION` |
| `created_at` | DATETIME |  | 建立关系时间 |

联合主键：`(message_id, information_id)`。两个复合外键从数据库层阻止跨用户关系。

### 3.2 `information_category`

| 字段 | 类型 | 键或约束 | 说明 |
|---|---|---|---|
| `information_id` | BIGINT | PK；FK → `information_item.id` CASCADE | 有效信息 |
| `category_id` | BIGINT | PK；FK → `category.id` RESTRICT | 全局分类 |

联合主键：`(information_id, category_id)`。

### 3.3 `information_tag`

| 字段 | 类型 | 键或约束 | 说明 |
|---|---|---|---|
| `user_id` | BIGINT | 复合 FK 组成 | 关系所属用户 |
| `information_id` | BIGINT | PK 组成；复合 FK → `information_item(user_id,id)` CASCADE | 有效信息 |
| `tag_id` | BIGINT | PK 组成；复合 FK → `tag(user_id,id)` RESTRICT | 用户标签 |

联合主键：`(information_id, tag_id)`。复合外键阻止跨用户标签关联。

## 4. 关键索引

| 索引 | 用途 |
|---|---|
| `message(user_id, channel_id, sent_at)` | 用户/渠道时间线查询 |
| `message(user_id, sender_id, sent_at)` | 用户/发送者时间线查询 |
| `message(user_id, process_status, ingested_at)` | 自动分析候选窗口 |
| `message(process_status, processing_started_at)` | 陈旧 PROCESSING 恢复 |
| `information_item(user_id, status, importance, created_at)` | 组合筛选与稳定排序 |
| `ai_analysis(message_id, analyzed_at)` | 消息分析历史 |
| `event(deadline)` | 截止事项查询 |
| `event(event_status, deadline)` | 状态扫描 |
| `event_reminder(reminder_status, remind_at)` | 到期提醒幂等扫描 |

## 5. 数据库高级对象

- View：`v_upcoming_events`、`v_channel_effectiveness`、`v_category_statistics`、`v_tag_popularity`。
- Trigger：`trg_information_item_set_updated_at`。
- Stored Procedure：`sp_channel_statistics(p_user_id, p_start, p_end)`，时间范围为 `[p_start,p_end)`。
- 真实定义见 `backend/alembic/versions/8f3c0d29a2b7_add_statistics_objects.py` 与 `docs/STATISTICS_SQL.md`。
