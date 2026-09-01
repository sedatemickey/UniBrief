# 统计 SQL 与数据库高级对象说明

> 所有对象由 Alembic revision `8f3c0d29a2b7` 创建。`infra/statistics.sql` 是便于报告引用的导出副本，不代替 migration。

## 1. 可展示统计

| 对象/API | 指标 | 用户隔离 | 时间口径 |
|---|---|---|---|
| `v_channel_effectiveness` / `/api/v1/statistics/channels` | 各渠道总消息、有效消息、有效率 | View 含 `user_id`，服务只传当前用户 | API/Procedure 使用 `[start,end)` |
| `v_category_statistics` / `/api/v1/statistics/categories` | 分类信息数量 | 按 `information_item.user_id` 分组 | 可按 Information 创建时间过滤 |
| `v_tag_popularity` / `/api/v1/statistics/tags` | 用户热门标签 Top N | Tag 与关联均限定 `user_id` | 可按 Information 创建时间过滤 |
| `v_upcoming_events` / `/api/v1/statistics/upcoming-events` | 近期 UPCOMING/ONGOING 事项 | View 含 `user_id` | 上海“今天”转换 UTC 后查询 |
| `/api/v1/statistics/overview` | 消息、有效信息、未来事项、到期提醒总览 | Repository 强制当前用户 | `start/end` 成对且半开区间 |

## 2. 有效消息定义

“有效消息”是至少存在一条 `message_information` 关系的 distinct Message。若一条 Message 支持多个 InformationItem，只计一次；有效率为：

```text
effective_message_count / message_count
```

当 `message_count=0` 时返回 0，避免除零。

## 3. Stored Procedure

```sql
CALL sp_channel_statistics(:current_user_id, :start_utc, :end_utc);
```

- `p_user_id` 只能由认证会话中的当前用户 ID 提供，客户端不能任意指定。
- `p_start`、`p_end` 必须非空且 `p_start < p_end`，否则 Procedure 使用 SQLSTATE `45000` 拒绝。
- Message 时间过滤严格使用 `sent_at >= p_start AND sent_at < p_end`。
- 服务层入口：`backend/app/repositories/statistics_repository.py`。

## 4. Trigger

`trg_information_item_set_updated_at` 在 `information_item` 每次 UPDATE 前写入 `CURRENT_TIMESTAMP`。它作为数据库级自动维护机制，保证绕过 ORM 的合法 SQL 更新仍能维护 `updated_at`。

## 5. 索引解释

- `message(user_id,channel_id,sent_at)`：Procedure 和渠道时间范围统计从用户/渠道前缀定位。
- `information_item(user_id,status,importance,created_at)`：分类、概览和信息页先按用户/status 过滤。
- `event(event_status,deadline)`：未来事项与周期状态扫描。
- `event_reminder(reminder_status,remind_at)`：到期提醒扫描。

## 6. 权威 SQL

完整 SQL 见 `infra/statistics.sql`；创建/删除顺序及可回滚定义见 `backend/alembic/versions/8f3c0d29a2b7_add_statistics_objects.py`。
