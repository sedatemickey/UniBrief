# DATABASE.md

# 数据库逻辑模型（MVP）

数据库：MySQL 8.x，utf8mb4。

> 本文件是数据库结构的业务源事实。修改 ORM 前先更新设计并通过 migration 实现。

## 1. platform

用途：外部消息平台，例如 QQ、微信、钉钉。

建议字段：
- `id` BIGINT PK
- `name` VARCHAR(64) NOT NULL UNIQUE
- `type` VARCHAR(32) NOT NULL
- `status` VARCHAR(32) NOT NULL DEFAULT 'ACTIVE'
- `created_at` DATETIME NOT NULL

## 2. channel

用途：具体消息渠道，例如 QQ 群、微信群。

字段：
- `id` BIGINT PK
- `platform_id` BIGINT FK -> platform.id
- `external_id` VARCHAR(128) NOT NULL
- `name` VARCHAR(255) NOT NULL
- `channel_type` VARCHAR(32) NOT NULL
- `created_at` DATETIME NOT NULL

约束：
- UNIQUE(`platform_id`, `external_id`)

## 3. sender

用途：消息发送者。它是外部聊天世界中的人/机器人，不是本系统用户。

字段：
- `id` BIGINT PK
- `platform_id` BIGINT FK -> platform.id
- `external_id` VARCHAR(128) NOT NULL
- `display_name` VARCHAR(255) NOT NULL
- `source_type` VARCHAR(32) NOT NULL
- `credibility` DECIMAL(4,3) NOT NULL DEFAULT 0.500
- `created_at` DATETIME NOT NULL

约束：
- UNIQUE(`platform_id`, `external_id`)
- credibility 在业务层限制为 0~1

## 4. message

用途：保存原始消息，属于核心大表。

字段：
- `id` BIGINT PK
- `channel_id` BIGINT FK -> channel.id
- `sender_id` BIGINT FK -> sender.id
- `external_id` VARCHAR(191) NOT NULL
- `content` TEXT NOT NULL
- `sent_at` DATETIME NOT NULL
- `ingested_at` DATETIME NOT NULL
- `process_status` VARCHAR(32) NOT NULL DEFAULT 'PENDING'

约束：
- UNIQUE(`channel_id`, `external_id`)

状态建议：
- PENDING
- PROCESSING
- PROCESSED
- FAILED
- IGNORED

索引：
- (`channel_id`, `sent_at`)
- (`sender_id`, `sent_at`)
- (`process_status`, `ingested_at`)

## 5. message_attachment

用途：消息的图片/PDF/Word 等附件元数据。课程设计不要求复杂文件服务。

字段：
- `id` BIGINT PK
- `message_id` BIGINT FK -> message.id
- `file_type` VARCHAR(64)
- `file_name` VARCHAR(255)
- `file_url` VARCHAR(1024)
- `extracted_text` TEXT NULL
- `created_at` DATETIME NOT NULL

## 6. ai_analysis

用途：保存“某条 Message 的一次 AI 分析结果”，支持重新分析和模型对比。

字段：
- `id` BIGINT PK
- `message_id` BIGINT FK -> message.id
- `model_name` VARCHAR(128) NOT NULL
- `useful` BOOLEAN NOT NULL
- `importance` TINYINT NOT NULL
- `confidence` DECIMAL(4,3) NOT NULL
- `summary` TEXT NULL
- `raw_result` JSON NULL
- `analyzed_at` DATETIME NOT NULL

索引：
- (`message_id`, `analyzed_at`)

## 7. information_item

用途：系统最终保留的“有效信息”，是核心业务实体。

字段：
- `id` BIGINT PK
- `title` VARCHAR(255) NOT NULL
- `summary` TEXT NOT NULL
- `source_type` VARCHAR(32) NOT NULL
- `importance` TINYINT NOT NULL
- `confidence` DECIMAL(4,3) NOT NULL
- `status` VARCHAR(32) NOT NULL DEFAULT 'ACTIVE'
- `created_at` DATETIME NOT NULL
- `updated_at` DATETIME NOT NULL

状态：
- ACTIVE
- UPDATED
- EXPIRED
- ARCHIVED

索引：
- (`status`, `importance`, `created_at`)

## 8. message_information

用途：Message 与 InformationItem 的 M:N 关系。

字段：
- `message_id` BIGINT PK, FK -> message.id
- `information_id` BIGINT PK, FK -> information_item.id
- `relation_type` VARCHAR(32) NOT NULL
- `created_at` DATETIME NOT NULL

relation_type：
- CREATE
- SUPPORT
- UPDATE
- CORRECTION

说明：
- 多条原始消息可共同支持一个 InformationItem；
- 一条原始消息的数据模型上允许关联多个 InformationItem。

## 9. category

用途：稳定、粗粒度的大类。

字段：
- `id` BIGINT PK
- `name` VARCHAR(64) NOT NULL UNIQUE
- `description` VARCHAR(255) NULL

预置建议：
- 课程
- 竞赛
- 科研
- 活动
- 综测
- 就业
- 行政
- 生活
- 其他

## 10. information_category

用途：InformationItem 与 Category 的 M:N 关系。

字段：
- `information_id` BIGINT PK, FK
- `category_id` BIGINT PK, FK

## 11. tag

用途：动态、细粒度主题标签，例如“数据库系统”“CCPC”“ACM”“报名”。

字段：
- `id` BIGINT PK
- `name` VARCHAR(128) NOT NULL UNIQUE

说明：
- Category 回答“这是什么类型”；
- Tag 回答“它具体和什么主题/对象有关”。

## 12. information_tag

用途：InformationItem 与 Tag 的 M:N 关系。

字段：
- `information_id` BIGINT PK, FK
- `tag_id` BIGINT PK, FK

## 13. event

用途：有明确时间属性的 InformationItem 转化出的事项。

字段：
- `id` BIGINT PK
- `information_id` BIGINT NOT NULL FK -> information_item.id
- `start_at` DATETIME NULL
- `deadline` DATETIME NULL
- `event_status` VARCHAR(32) NOT NULL DEFAULT 'UPCOMING'
- `created_at` DATETIME NOT NULL
- `updated_at` DATETIME NOT NULL

关键约束：
- UNIQUE(`information_id`)
- 由此保证 InformationItem 1 : 0..1 Event

状态：
- UPCOMING
- ONGOING
- COMPLETED
- EXPIRED
- CANCELLED

索引：
- (`deadline`)
- (`event_status`, `deadline`)

## 14. 删除策略

默认不要级联删除业务历史。

建议：
- Platform/Channel/Sender 如果已有 Message，禁止物理删除，改状态；
- Message 原则上保留原始证据；
- InformationItem 使用 ARCHIVED，不轻易物理删除；
- 关联表可随父实体删除；
- 演示项目如需清库，通过专用 reset/seed 脚本执行。

## 15. 推荐视图

至少实现：
1. `v_upcoming_events`
   - 未完成且未来 7/30 天内到期的事项
2. `v_channel_effectiveness`
   - 各 Channel 总消息数、有效消息数、有效率
3. `v_category_statistics`
   - 各 Category 的 InformationItem 数量
4. 可选 `v_tag_popularity`
   - Tag 使用次数

## 16. 推荐数据库级功能

Trigger：
- `BEFORE UPDATE information_item` 自动维护 `updated_at`
  或使用 MySQL 原生 `ON UPDATE CURRENT_TIMESTAMP`，两者选其一。
- 为展示 Trigger，可实现一个简单、可解释且不会隐藏核心业务的 Trigger。

Stored Procedure（可选但推荐）：
- `sp_channel_statistics(p_start, p_end)`
- 返回时间区间内各渠道消息量、有效消息量和有效率。
