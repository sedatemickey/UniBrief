# REST API 契约（多用户 MVP）

本文是前后端并行开发的接口源事实。实现后 OpenAPI 必须与本文一致；接口变化必须同步更新本文。

## 1. 通用约定

- API 前缀：`/api/v1`；健康检查为 `/health`。
- JSON 使用 `application/json; charset=utf-8`；CSV 导入使用 `multipart/form-data`。
- 普通业务接口不接受 `user_id`，只使用普通用户 Cookie 中的当前用户。
- 管理接口只使用管理员 Cookie；管理员不得读取用户私有业务内容。
- 所有 ID 在 JSON 中为整数；NapCat/平台外部 ID 在导入结构中一律为字符串。
- 时间输入必须为带时区 ISO 8601，例如 `2026-09-01T16:00:00+08:00`；后端转 UTC，响应统一使用 `Z`，例如 `2026-09-01T08:00:00Z`。
- 跨用户资源、已停用或不存在资源统一返回 404，避免泄露存在性。
- 列表默认 `page=1&page_size=20`，`page_size` 范围 1..100。
- 除 Event 相交查询外，所有 `from/to`、`start/end` 统计和列表时间范围统一使用半开区间 `[start, end)`；start 必须早于 end。这样相邻日/月窗口不会重复计数边界记录。
- PATCH 采用字段存在性语义：未传字段表示保持不变；显式 `null` 只有在该字段契约允许清空时才表示清空；不可空字段传 null 返回 422。空数组表示清空对应关联集合。

### 1.1 普通成功响应

单对象直接返回对象；创建成功使用 HTTP 201。删除/无响应操作使用 HTTP 204。

分页响应：

```json
{
  "items": [],
  "page": 1,
  "page_size": 20,
  "total": 0,
  "total_pages": 0
}
```

### 1.2 统一错误响应

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "请求参数不合法",
    "retryable": false,
    "details": {"field": "username"},
    "request_id": "01J..."
  }
}
```

状态码：

| HTTP | 用途 |
|---:|---|
| 400 | 业务参数错误、模型未指定、注册关闭 |
| 401 | UniBrief 未登录或会话失效 |
| 403 | CSRF 失败或管理员/普通用户入口类型错误 |
| 404 | 资源不存在或不属于当前用户 |
| 409 | 用户名冲突、乐观锁冲突、状态不允许 |
| 413 | 导入文件或附件超过限制 |
| 422 | Pydantic 请求校验失败 |
| 429 | 本系统限流或上游 AI 限流 |
| 502 | AI Provider 错误、非法上游输出 |
| 503 | 数据库、AI 或后台依赖暂不可用 |
| 504 | AI/附件下载超时 |

稳定错误码至少包括：`VALIDATION_ERROR`、`NOT_AUTHENTICATED`、`SESSION_EXPIRED`、`CSRF_FAILED`、`NOT_FOUND`、`USERNAME_CONFLICT`、`REGISTRATION_DISABLED`、`ADMIN_NOT_INITIALIZED`、`INVALID_STATE`、`VERSION_CONFLICT`、`IMPORT_PARTIAL_FAILURE`、`PLATFORM_NOT_AVAILABLE`、`DUPLICATE_CONFLICT`、`AUTH_ERROR`、`MODEL_NOT_FOUND`、`MODEL_LIST_UNSUPPORTED`、`RATE_LIMITED`、`TIMEOUT`、`NETWORK_ERROR`、`PROVIDER_ERROR`、`INVALID_AI_OUTPUT`、`CONCURRENT_UPDATE`、`PERSISTENCE_ERROR`、`ATTACHMENT_TOO_LARGE`、`ATTACHMENT_UNSAFE_URL`、`ATTACHMENT_FILE_MISSING`。

## 2. Cookie、会话与 CSRF

Cookie 名称：

| 作用 | Session Cookie | CSRF Cookie | Header |
|---|---|---|---|
| 普通用户 | `unibrief_session` | `unibrief_csrf` | `X-CSRF-Token` |
| 管理员 | `unibrief_admin_session` | `unibrief_admin_csrf` | `X-Admin-CSRF-Token` |

- Session Cookie：HttpOnly、SameSite=Lax；生产环境 Secure。
- CSRF Cookie：非 HttpOnly，前端读取后原样放入对应 Header；服务端执行双提交校验。
- 登录成功时轮换 Session 和 CSRF；退出时清除。
- 所有 POST/PATCH/DELETE 写操作均校验 CSRF；登录和注册不依赖已有 CSRF，但必须校验 Origin/Host。
- 普通和管理员 Cookie 不能互相替代。
- Session 载荷包含主体 ID/类型、`session_version`、签发和过期时间；停用、改密、重置密码后旧 Session 返回 401 `SESSION_EXPIRED`。

## 3. Health

### GET `/health`

无需认证。HTTP 200：

```json
{"status":"ok","service":"unibrief","version":"0.1.0"}
```

### GET `/api/v1/health/ready`

无需认证，检查数据库连接。就绪返回 200；不可用返回 503，不泄露 DSN。

## 4. 普通用户认证

### GET `/api/v1/auth/registration-status`

```json
{"enabled":false}
```

### POST `/api/v1/auth/register`

仅 `registration_enabled=true` 可用。

```json
{
  "username": "student01",
  "display_name": "学生一",
  "password": "ExamplePass123"
}
```

约束：username 3..64，只允许字母、数字、下划线和短横线；display_name 1..128；password 10..128。成功 201 并建立普通会话；关闭时 400 `REGISTRATION_DISABLED`；重名 409。

### POST `/api/v1/auth/login`

```json
{"username":"student01","password":"ExamplePass123"}
```

成功 200，设置普通 Session/CSRF Cookie：

```json
{"id":1,"username":"student01","display_name":"学生一","status":"ACTIVE"}
```

用户名或密码错误统一返回 401，不区分账号是否存在；DISABLED 用户也返回相同外部提示。

### POST `/api/v1/auth/logout`

需要普通 CSRF。成功 204。

### GET `/api/v1/auth/me`

返回当前用户基本信息，不返回 password_hash/session_version。

### POST `/api/v1/auth/change-password`

```json
{"current_password":"old-password","new_password":"new-password-123"}
```

成功后递增 session_version、清除当前 Cookie，返回 204；前端跳转登录页。

## 5. 管理员认证与管理

### POST `/api/v1/admin/auth/login`

```json
{"password":"admin-password"}
```

成功设置管理员 Session/CSRF，返回 `{"authenticated":true}`。管理员不是 User，不返回 user_id。

管理员尚未通过命令行初始化 `admin_password_hash` 时返回 HTTP 503 `ADMIN_NOT_INITIALIZED`；普通密码错误返回 401，二者必须区分。

### POST `/api/v1/admin/auth/logout`

需要管理员 CSRF，成功 204。

### GET `/api/v1/admin/auth/me`

返回 `{"authenticated":true}`。

### POST `/api/v1/admin/auth/change-password`

```json
{"current_password":"old","new_password":"new-password-123"}
```

成功更新 `admin_password_hash`、递增 `admin_session_version`、清除 Cookie，返回 204。

### GET `/api/v1/admin/users`

参数：`keyword`、`status=ACTIVE|DISABLED`、`page`、`page_size`、`sort=created_at_desc|username_asc`。返回分页用户，不返回私有数据计数和密码字段。

### POST `/api/v1/admin/users`

```json
{"username":"student02","display_name":"学生二","password":"ExamplePass123"}
```

成功 201。

### PATCH `/api/v1/admin/users/{id}`

```json
{"display_name":"新昵称","status":"DISABLED"}
```

字段均可选，但至少一个；停用时递增 session_version。

### POST `/api/v1/admin/users/{id}/reset-password`

```json
{"new_password":"TemporaryPass123"}
```

成功递增 session_version，返回 204。服务端不生成、不保存明文临时密码。

### GET `/api/v1/admin/settings`

```json
{
  "registration_enabled": false,
  "admin_password_configured": true
}
```

不得返回敏感 `value_text`。

### PATCH `/api/v1/admin/settings/registration`

```json
{"enabled":true}
```

返回 `{"enabled":true}`。

## 6. Platform、Channel、Sender

### 管理员 Platform

- `GET /api/v1/admin/platforms?status=ACTIVE&page=1&page_size=20`
- `POST /api/v1/admin/platforms`
- `PATCH /api/v1/admin/platforms/{id}`

创建：

```json
{"name":"QQ","type":"IM","status":"ACTIVE"}
```

更新可修改 `name`、`type`、`status`；历史已引用 Platform 不物理删除。

### GET `/api/v1/platforms`

普通用户读取 ACTIVE Platform：

```json
{"items":[{"id":1,"name":"QQ","type":"IM"}]}
```

### GET `/api/v1/channels`

参数：`platform_id`、`keyword`、`channel_type`、分页。

### POST `/api/v1/channels`

```json
{
  "platform_id": 1,
  "external_id": "group-123",
  "name": "数据库课程群",
  "channel_type": "GROUP"
}
```

同一用户下 `(platform_id, external_id)` 幂等；完全相同返回已有对象 200，不同字段冲突返回 409。

### PATCH `/api/v1/channels/{id}`

仅允许修改 `name`、`channel_type`；不能修改归属、platform_id、external_id。

### GET `/api/v1/senders`

参数：`platform_id`、`keyword`、`source_type`、`credibility_min/max`、分页。

### POST `/api/v1/senders`

```json
{
  "platform_id":1,
  "external_id":"user-456",
  "display_name":"张老师",
  "source_type":"TEACHER",
  "credibility":0.95
}
```

### PATCH `/api/v1/senders/{id}`

可修改 `display_name`、`source_type`、`credibility`；不能修改平台外部 ID。

## 7. Message 导入与 NapCat Adapter

### POST `/api/v1/messages/import`

JSON Adapter 的统一输入：

```json
{
  "platform": {"name":"QQ","type":"IM"},
  "channel": {"external_id":"group-123","name":"数据库课程群","channel_type":"GROUP"},
  "messages": [
    {
      "external_id":"msg-1001",
      "sender":{"external_id":"user-456","display_name":"张老师","source_type":"TEACHER"},
      "content":"课程设计报告 9 月 20 日前提交",
      "sent_at":"2026-09-01T09:30:00+08:00",
      "attachments":[
        {
          "external_id":"file-1",
          "file_name":"要求.pdf",
          "file_type":"application/pdf",
          "file_url":"https://example.edu/files/requirement.pdf"
        }
      ]
    }
  ]
}
```

限制：每次 1..1000 条；external_id 必填且按字符串处理；附件 URL 仅允许 HTTP/HTTPS。`platform.name` 只用于匹配管理员已创建且 ACTIVE 的 Platform，导入不得隐式创建或更新全局 Platform；名称不存在、已停用或 type 不一致时该条返回 `PLATFORM_NOT_AVAILABLE`。响应 200：

```json
{
  "received": 1,
  "inserted": 1,
  "duplicates": 0,
  "failed": 0,
  "attachment_metadata_created": 1,
  "attachment_downloads_scheduled": 1,
  "results": [
    {"external_id":"msg-1001","status":"INSERTED","message_id":101,"error":null}
  ]
}
```

逐条校验和幂等；允许部分失败。完全相同的已存在 Message 返回 `DUPLICATE`；同一外部 ID 但 sender/content/sent_at 不同返回 `DUPLICATE_CONFLICT`，保留原 Message。重复导入可以幂等补充此前不存在的附件元数据。请求格式整体非法返回 422，单条非法放入 results 并返回 200；如果所有条目失败，返回 400 `IMPORT_PARTIAL_FAILURE`。

### POST `/api/v1/messages/import-csv`

`multipart/form-data` 字段 `file`，UTF-8 CSV，最大 10 MiB。固定列：

```text
platform_name,platform_type,channel_external_id,channel_name,channel_type,message_external_id,sender_external_id,sender_display_name,sender_source_type,content,sent_at
```

CSV MVP 不内嵌附件；附件使用 JSON Adapter。响应与 JSON 导入一致。

### NapCat OneBot 11 支持

NapCat 官方仓库：[NapCatQQ](https://github.com/NapNeko/NapCatQQ)。完整边界和映射见 `docs/NAPCAT_INTEGRATION.md`。本项目提供独立 `NapCatOneBotAdapter`/桥接脚本：

- 连接 NapCat OneBot 11 WebSocket Server；
- 只消费 `post_type=message` 的 group/private 消息事件；
- 将 `message_id`、`group_id`、`user_id`、`self_id` 转为字符串外部 ID；
- 将消息段转换为正文和附件候选，再调用当前普通用户的 `/messages/import`；
- 目标 UniBrief 用户由桥接进程环境变量和普通用户登录会话确定；每个进程只绑定一个用户；
- NapCat token、UniBrief 密码/Cookie 不写数据库、不提交 Git、不打印日志；
- 不实现 QQ 协议逆向、账号生命周期管理、消息发送或自动回复。

桥接配置至少包括：`NAPCAT_ENABLED=false`、`NAPCAT_WS_URL`、`NAPCAT_ACCESS_TOKEN`、`UNIBRIEF_BASE_URL`、`UNIBRIEF_USERNAME`；密码通过启动时交互输入或部署 Secret 注入。Phase 1 写好调用方法但不运行专项测试；待其他模块稳定且用户完成 NapCat 搭建后，再做合成事件和真实手工联调。

## 8. Message 查询与分析

### GET `/api/v1/messages`

参数：`platform_id`、`channel_id`、`sender_id`、`process_status`、`sent_from/to`、`keyword`、`has_attachment`、`sort=sent_at_desc|sent_at_asc|ingested_at_desc`、分页。

### GET `/api/v1/messages/{id}`

返回 Message、Platform、Channel、Sender、附件元数据和 AIAnalysis 历史。附件不返回 `storage_key`、服务器绝对路径或完整敏感错误。

### POST `/api/v1/messages/{id}/analyze`

```json
{"model":"model-a","mode":"retry"}
```

model 为空时使用 AI_DEFAULT_MODEL；两者都为空返回 400。`mode` 默认为 `retry`：retry 只允许 PENDING/FAILED 并会写正式业务结果；compare 只允许 PROCESSED/IGNORED，只追加 AIAnalysis，绝不修改 Message 状态或任何 Information/Event/Reminder。若状态不允许或 Message 已 PROCESSING，返回 409 `INVALID_STATE`。retry 成功：

```json
{
  "message_id":101,
  "process_status":"PROCESSED",
  "analysis_id":501,
  "model_name":"model-a",
  "useful":true,
  "information_ids":[201]
}
```

compare 成功返回原 Message 状态，并明确不应用业务变更：

```json
{"message_id":101,"process_status":"PROCESSED","analysis_id":503,"model_name":"model-b","useful":true,"business_applied":false}
```

### POST `/api/v1/messages/analyze-batch`

```json
{"message_ids":[101,102],"model":"model-a","mode":"retry"}
```

1..100 个 ID，必须全部属于当前用户；返回每条结果，HTTP 200 允许部分成功：

```json
{
  "mode":"retry",
  "results":[
    {"message_id":101,"status":"PROCESSED","analysis_id":501,"business_applied":true,"error":null},
    {"message_id":102,"status":"FAILED","analysis_id":502,"business_applied":false,"error":{"code":"INVALID_AI_OUTPUT","retryable":true}}
  ]
}
```

compare 批次返回 `mode=compare`，每条 `business_applied` 必须为 false，status 保留原 Message 状态。

## 9. Attachment

### GET `/api/v1/attachments/{id}/download`

仅当前用户。DOWNLOADED 且文件存在时流式返回；未完成 409；文件记录与磁盘不一致时标记 FAILED 并返回 404/`ATTACHMENT_FILE_MISSING`。不允许路径参数直接访问存储目录。

### POST `/api/v1/attachments/{id}/retry-download`

仅 FAILED/PENDING 可重试；返回 202：

```json
{"id":301,"download_status":"PENDING","scheduled":true}
```

### GET `/api/v1/attachments/{id}`

返回 `id`、message_id、file_name/type/size、sha256、download_status/attempts/downloaded_at、脱敏错误摘要；不返回 file_url 中的敏感查询参数、storage_key 或绝对路径。

## 10. AI Provider

### GET `/api/v1/ai/config`

```json
{"base_url":"https://api.example.com/v1","default_model":"model-a","timeout_seconds":60,"max_retries":2,"has_api_key":true}
```

### GET `/api/v1/ai/models`

支持列表时：

```json
{"supports_listing":true,"models":[{"id":"model-a"}],"error_code":null,"message":null}
```

Provider 不支持列表时仍返回 HTTP 200：

```json
{"supports_listing":false,"models":[],"error_code":"MODEL_LIST_UNSUPPORTED","message":"请手工输入模型 ID"}
```

Provider Key 无效/无权限返回 502 `AUTH_ERROR`；模型不存在返回 502 `MODEL_NOT_FOUND`；上游限流返回 429；超时返回 504；网络、供应商或非法输出返回 502。只有 UniBrief 自身会话失效使用 401。绝不返回 API Key。

### POST `/api/v1/ai/test`

```json
{"model":"model-a"}
```

成功：

```json
{"ok":true,"model":"model-a","latency_ms":832,"message":"连接成功"}
```

该接口会产生真实请求和 Token 成本，后端应做基础频率限制。

## 11. Information、Category、Tag

### GET `/api/v1/information`

参数：`category_ids`（重复参数）、`tag_ids`（重复参数，标签内部 OR）、`importance_min/max`、`status`、`created_from/to`、`event_from/to`、`keyword`、`sort=created_at_desc|updated_at_desc|importance_desc|deadline_asc`、分页。不同筛选维度 AND。

### GET `/api/v1/information/{id}`

返回 InformationItem、`version`、Categories、Tags、Event、Reminder 和关联 Message 来源。

### PATCH `/api/v1/information/{id}`

```json
{
  "expected_version":3,
  "title":"更新标题",
  "summary":"更新摘要",
  "importance":4,
  "status":"ACTIVE",
  "category_ids":[1,2],
  "tag_names":["数据库","课程设计"]
}
```

除 expected_version 外字段可选但至少一个；`title`、`summary`、`importance`、`status` 不允许 null；`category_ids:[]` 或 `tag_names:[]` 明确清空该集合，未传集合则保持不变。成功返回更新对象和递增后的 version；冲突返回 409 `VERSION_CONFLICT` 和当前 version，不覆盖数据。

### POST `/api/v1/information/{id}/link-message/{message_id}`

```json
{"relation_type":"SUPPORT"}
```

relation_type 为 CREATE/SUPPORT/UPDATE/CORRECTION；重复关系返回现有关系 200；跨用户 404。

### Category

- `GET /api/v1/categories`：普通用户读取 ACTIVE Category。
- `GET|POST|PATCH /api/v1/admin/categories[/{id}]`：管理员维护 name、description、status；被引用时不删除。

### Tag

- `GET /api/v1/tags?keyword=&page=&page_size=`
- `POST /api/v1/tags`，body `{"name":"数据库"}`
- `PATCH /api/v1/tags/{id}`，body `{"name":"数据库系统"}`
- `GET /api/v1/tags/popular?limit=10&created_from=&created_to=`，limit 1..100

Tag 名称在当前用户内唯一；重命名冲突返回 409。

## 12. Event 与 Reminder

### GET `/api/v1/events`

参数：`range_start`、`range_end`、`status`、`sort=start_at_asc|deadline_asc|updated_at_desc`、分页。range_start/end 必须成对提供，返回与窗口相交的当前用户 Event，月历和议程必须共用此接口。

Event 窗口也使用半开区间 `[range_start, range_end)`。把缺失 start_at 视为 deadline，把缺失 deadline 视为 start_at；相交定义为 `effective_start < range_end AND effective_end >= range_start`，从而让恰好在 range_end 开始的事项只进入下一个窗口。

### GET `/api/v1/events/{id}`

返回 Event、Information 摘要、当前 `information_version` 和 Reminder。

### PATCH `/api/v1/events/{id}`

```json
{
  "expected_information_version":4,
  "start_at":"2026-09-10T08:00:00+08:00",
  "deadline":"2026-09-10T18:00:00+08:00",
  "event_status":"COMPLETED"
}
```

可修改时间或执行 `COMPLETED/CANCELLED/UPCOMING` 用户状态操作；不能手工设置 ONGOING/EXPIRED。`start_at`、`deadline` 未传表示不改，显式 null 表示清空；更新后仍必须至少保留一个时间且 deadline >= start_at。将 COMPLETED/CANCELLED 恢复为 UPCOMING 后，周期扫描会立即按当前时间修正为 ONGOING 或 EXPIRED。更新父 InformationItem version。默认 Reminder 按规则重算，自定义/DISABLED 不覆盖。

### GET `/api/v1/reminders`

参数：`status=PENDING|DUE|READ|DISABLED`、`remind_from/to`、分页。时间范围使用 `[remind_from, remind_to)`；只返回当前用户。

### PATCH `/api/v1/reminders/{id}`

修改时间：

```json
{"remind_at":"2026-09-09T18:00:00+08:00"}
```

设置 `is_custom_time=true`，根据当前时间进入 PENDING/DUE。

关闭/重新启用：

```json
{"enabled":false}
```

重新启用可以同时传 remind_at；没有可用时间返回 400。DISABLED 之后 Deadline 更新不自动重启。

### POST `/api/v1/reminders/{id}/read`

仅 DUE 可标记 READ；重复 READ 幂等返回 200。

## 13. Statistics

所有统计只计算当前用户，时间参数为带时区 ISO 8601 并转 UTC；start/end 均使用半开区间 `[start,end)`。

### GET `/api/v1/statistics/overview`

参数 `start/end` 可选且必须成对；返回 message_total、information_active_total、event_upcoming_total、reminder_due_total。

### GET `/api/v1/statistics/channels`

参数 `start/end`、`platform_id`。总消息数为时间范围内 Channel 的 Message；有效消息数为至少关联一个 InformationItem 的 distinct Message；`effectiveness_rate=effective_message_count/message_count`，分母 0 时为 0。

### GET `/api/v1/statistics/categories`

参数 `start/end`、`include_archived=false`。按当前用户 InformationItem 与 Category 关联计数。

### GET `/api/v1/statistics/tags`

参数 `start/end`、`limit=10`（1..100）、`include_archived=false`。

### GET `/api/v1/statistics/upcoming-events`

参数 `days=7`（1..90），按当前用户、上海时区“今天”起算后转换为 UTC 查询。

## 14. 后台任务的可观察性

普通用户不暴露全局任务队列。以下状态通过业务资源体现：Message.process_status/processing_started_at、Attachment.download_status/attempts、Event.event_status、Reminder.reminder_status。

管理员也不得读取用户业务任务内容。后台扫描错误写服务日志和指标，但日志不得包含消息正文、附件 URL 查询参数、Cookie、密码或 AI API Key。
