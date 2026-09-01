# AI_INTEGRATION.md

# 真实 OpenAI-compatible AI 接入设计

## 1. 原则

本项目**不提供运行时 MockAIProvider**。

系统为多用户私有数据模型。任何候选信息查询、单条分析、批量分析、失败重试和结果写入都必须限定在当前认证用户范围内，不得把不同用户的消息放入同一个 AI 请求。

课程演示和真实使用都必须能连接实际的 OpenAI-compatible API。

允许在自动化单元测试中使用：
- HTTP transport stub
- monkeypatch
- fake response

这些只用于测试错误处理和解析逻辑，不能作为产品运行模式，也不能作为课堂演示的 AI 替代品。

## 2. 兼容性目标

优先兼容主流的 OpenAI-compatible Chat Completions 风格接口。

默认假设服务提供：

- `GET {base_url}/models`
- `POST {base_url}/chat/completions`

配置中的 `base_url` 统一约定为包含 `/v1` 的 API 根地址，例如：

```text
https://api.openai.com/v1
https://example-compatible-provider.com/v1
```

如果某兼容服务不支持模型列表接口，前端必须允许**手工输入模型 ID**，而不是阻止使用。

## 3. 后端 SDK

优先使用官方 `openai` Python SDK 的异步客户端，并通过自定义 `base_url` 兼容第三方服务。

概念代码：

```python
from openai import AsyncOpenAI

client = AsyncOpenAI(
    api_key=settings.ai_api_key,
    base_url=settings.ai_base_url,
    timeout=settings.ai_timeout_seconds,
)
```

核心调用使用 Chat Completions 兼容接口。

这样做是为了兼容大量只实现 OpenAI Chat Completions 协议的第三方服务。

## 4. 配置

`.env.example` 至少包含：

```env
AI_BASE_URL=https://api.openai.com/v1
AI_API_KEY=
AI_DEFAULT_MODEL=
AI_TIMEOUT_SECONDS=60
AI_MAX_RETRIES=2
AI_TEMPERATURE=0.1
AI_JSON_MODE=auto
AI_BATCH_POLL_SECONDS=30
AI_BATCH_SIZE_THRESHOLD=20
AI_BATCH_MAX_WAIT_SECONDS=300
AI_PROCESSING_STALE_SECONDS=600
```

安全要求：

- `AI_API_KEY` 只从服务端环境变量读取；
- API Key 绝不能进入 Git；
- API Key 绝不能通过普通 GET API 返回给前端；
- 日志中不得打印 Authorization Header 或完整 API Key；
- 异常信息中如包含 Key 必须脱敏。

## 5. 模型选择接口

### GET `/api/v1/ai/config`

返回安全配置，例如：

```json
{
  "base_url": "https://api.openai.com/v1",
  "default_model": "gpt-example",
  "timeout_seconds": 60,
  "has_api_key": true
}
```

不得返回真实 Key。

### GET `/api/v1/ai/models`

行为：

1. 后端使用已配置的 `base_url` 和 `api_key` 调用模型列表；
2. 返回可用 model ID；
3. 对 model ID 排序；
4. 如果兼容服务不支持 `/models`：
   - 返回明确错误码/状态；
   - 前端仍允许手工输入模型 ID。

建议返回：

```json
{
  "supports_listing": true,
  "models": [
    {"id": "model-a"},
    {"id": "model-b"}
  ]
}
```

### POST `/api/v1/ai/test`

输入：

```json
{
  "model": "model-a",
  "mode": "retry"
}
```

作用：
- 使用真实 API 做一次最小请求；
- 验证 base URL、API Key、模型是否可用；
- 返回 latency 和简短状态；
- 测试接口必须说明会产生实际 API 请求和可能的 Token 成本。

### POST `/api/v1/messages/{id}/analyze`

请求体支持：

```json
{
  "model": "model-a"
}
```

若未指定：
- 使用 `AI_DEFAULT_MODEL`；
- 如果 default model 为空，返回 400 并要求先选择模型。

`mode` 默认为 `retry`：

- `retry`：只允许 `PENDING` 或 `FAILED` Message；会原子抢占为 PROCESSING，并在成功后写入/更新 InformationItem 等正式业务关系。
- `compare`：只允许 `PROCESSED` 或 `IGNORED` Message；仅追加一条 AIAnalysis 供模型对比，不修改 Message.process_status，不创建/修改 InformationItem、关系、Event 或 Reminder，响应明确返回 `business_applied=false`。
- MVP 不提供“清空旧结果后重建”的 reprocess 模式，避免来源关系和用户修改被静默覆盖。

### POST `/api/v1/messages/analyze-batch`

请求体：

```json
{
  "message_ids": [1, 2, 3],
  "model": "model-a",
  "mode": "retry"
}
```

所有同一批次分析使用所选模型，并将实际使用的模型名写入 `ai_analysis.model_name`。

服务端必须验证所有 `message_ids` 都属于当前用户；混入其他用户 ID 时统一按资源不存在处理。

批量 AI 响应使用：

```json
{
  "results": [
    {
      "message_id": 1,
      "useful": true,
      "items": [
        {
          "action": "create",
          "target_information_id": null,
          "relation_type": "CREATE",
          "title": "数据库作业通知",
          "summary": "本周提交课程设计初稿",
          "source_type": "TEACHER",
          "importance": 4,
          "confidence": 0.91,
          "categories": ["课程"],
          "tags": ["数据库"],
          "event": null
        }
      ]
    },
    {"message_id": 2, "useful": false, "items": []}
  ]
}
```

批量持久化按 Message 使用独立短事务，允许部分成功；一条 Message 的失败不得回滚同批其他 Message。响应必须为每个请求中的 `message_id` 恰好返回一个结果，缺失、重复或额外 ID 都视为对应批次输出非法。

自动分析窗口在 Phase 3 实现：单进程每 30 秒扫描；只聚合同一用户、同一 Channel 的 PENDING Message；达到 20 条或最早消息等待满 5 分钟时触发。使用带当前状态条件的 UPDATE 原子抢占为 PROCESSING 并写 `processing_started_at`，手工分析和自动分析共用同一抢占逻辑。超过 10 分钟仍为 PROCESSING 的 Message 恢复为 FAILED，并保留可重试错误记录。项目只承诺单实例课堂部署，不宣称分布式 Worker 能力。

## 6. 前端 AI 设置/选择界面

新增页面或抽屉：**AI 设置**

显示：

- API Base URL（只读显示当前服务端配置即可；如要编辑，必须明确写入服务端配置文件或由重启生效）
- API Key 状态：已配置 / 未配置，不显示 Key
- “加载模型列表”按钮
- 模型下拉框
- 手工输入模型 ID
- “测试连接”按钮
- 当前默认/本次选中模型
- 错误信息
- API 请求耗时

模型选择优先级：

1. 用户本次在前端选择的 model
2. `AI_DEFAULT_MODEL`

前端可以把上次选择的 model ID 保存到 localStorage，
但每次真正分析时都把 model 明确发送给后端。
因此不需要新增数据库 Settings 表。

## 7. AI 输出结构

必须让模型输出可被 Pydantic 验证的 JSON。

单条 Message 的最低结构：

```json
{
  "useful": true,
  "items": [
    {
      "action": "create",
      "target_information_id": null,
      "relation_type": "CREATE",
      "title": "标题",
      "summary": "摘要",
      "source_type": "TEACHER",
      "importance": 4,
      "confidence": 0.9,
      "categories": ["课程"],
      "tags": ["数据库系统", "课程设计"],
      "event": {
        "start_at": null,
        "deadline": null,
        "status": "UPCOMING"
      }
    }
  ]
}
```

注意：
- 使用 `items` 是为了在数据模型层面支持“一条 Message 产生多个 InformationItem”；
- `action`、`target_information_id`、`relation_type` 必须属于每个 item，使同一 Message 可以同时创建、支持、更新或纠正不同 InformationItem；
- 顶层只有 Message 级 `useful`；`importance` 和 `confidence` 必须属于各自 item，禁止再返回顶层 confidence；
- `useful=false` 时 `items` 可以为空；
- `useful=true` 时 `items` 至少一个；每个 item 的 `importance` 为 1..5，`confidence` 为 0..1；
- 所有字段写数据库前必须严格 Pydantic 校验；
- 对额外字段采用明确策略，不允许静默污染业务模型。

### action / target / relation 兼容矩阵

| action | target_information_id | relation_type | 业务效果 |
|---|---|---|---|
| `create` | 必须为 null | 必须为 `CREATE` | 新建 InformationItem 并关联来源 Message |
| `link` | 必须引用候选中的当前用户 InformationItem | 必须为 `SUPPORT` | 只新增支持关系，可补充分类/标签，但不覆盖正文和 Event |
| `update` | 必须引用候选中的当前用户 InformationItem | 必须为 `UPDATE` | 使用 expected version 更新信息/事项并新增关系 |
| `correct` | 必须引用候选中的当前用户 InformationItem | 必须为 `CORRECTION` | 使用 expected version 更正信息/事项并新增关系 |

任何其他组合、引用候选列表外 ID、跨用户目标、重复 item 目标冲突均为 `INVALID_AI_OUTPUT`。同一响应若对同一 target 同时给出多个写操作，也视为非法，不依赖数组顺序解决冲突。

## 8. JSON 兼容策略

不同 OpenAI-compatible 服务对 Structured Outputs / JSON mode 的支持不同。

因此 MVP 不依赖某个供应商特有的 Structured Outputs。

推荐：

1. system prompt 严格要求“只输出 JSON，不要 Markdown code fence”；
2. 如果配置 `AI_JSON_MODE=auto`：
   - 可尝试供应商支持的 JSON response format；
   - 若接口返回“不支持参数”类错误，可退回普通 Chat Completion；
3. 无论哪种路径，最终都必须：
   - 提取 JSON
   - Pydantic validate
   - 校验失败则记录 FAILED，可重试

不要用“尽量解析一切”的方式吞掉错误。

## 9. 超时、重试与错误状态

至少区分：

- AUTH_ERROR：Key 无效/无权限
- MODEL_NOT_FOUND
- RATE_LIMITED
- TIMEOUT
- NETWORK_ERROR
- PROVIDER_ERROR
- INVALID_AI_OUTPUT
- CONCURRENT_UPDATE
- PERSISTENCE_ERROR

对外 HTTP 映射固定为：

| 场景 | HTTP | error.code |
|---|---:|---|
| UniBrief 普通/管理员会话无效 | 401 | `NOT_AUTHENTICATED` / `SESSION_EXPIRED` |
| AI Provider Key 无效或无权限 | 502 | `AUTH_ERROR` |
| 上游模型不存在 | 502 | `MODEL_NOT_FOUND` |
| 上游限流 | 429 | `RATE_LIMITED` |
| 上游超时 | 504 | `TIMEOUT` |
| 网络、供应商或非法输出 | 502 | `NETWORK_ERROR` / `PROVIDER_ERROR` / `INVALID_AI_OUTPUT` |

Provider 的 401 不得直接转换为 UniBrief 的 401，避免前端误判为本站登录失效。

Message 状态建议：

```text
PENDING
PROCESSING
PROCESSED
FAILED
IGNORED
```

失败时：
- 原始 Message 永远保留；
- 不创建半成品 InformationItem；
- 插入 `AIAnalysis(status=FAILED)`，保存错误码、脱敏错误、耗时，以及必要时截断后的 `raw_response_text`；
- 写清错误日志，但不得记录 API Key、Authorization Header 或完整敏感响应；
- 前端可再次选择模型并重试。

## 10. 事务边界

真实 AI HTTP 请求**不要放在长时间数据库事务内部**。

推荐：

1. `retry` 使用条件更新把 PENDING/FAILED Message 原子标记 PROCESSING，写入 `processing_started_at` 并 commit；若影响行数为 0，说明已被其他手工或自动任务抢占；
2. 调真实 AI；
3. 校验输出；
4. 开启一个短事务：
   - insert `AIAnalysis(status=SUCCEEDED)`
   - create/link/update/correct InformationItem
   - insert MessageInformation
   - Category / Tag 关联
   - Event；若存在 Deadline，同时创建或维护 EventReminder
   - Message -> PROCESSED
5. commit

第 4 步中的候选 InformationItem、Tag 和全部关联必须属于 Message 的同一用户；数据库复合外键作为第二道约束。

如果第 4 步失败：
- rollback；
- 另一个短事务插入 `AIAnalysis(status=FAILED, error_code=PERSISTENCE_ERROR)` 并把 Message 标记 FAILED。

如果 Provider 请求或输出校验失败：
- 不进入业务结果事务；
- 使用独立短事务插入失败 AIAnalysis，并把 Message 标记 FAILED；
- 清空 `processing_started_at`，使用户可以更换模型重试。

`compare` 不参与 Message 状态机：在单进程内按 message_id 使用异步锁避免同一消息的重复 compare 请求互相覆盖，仅写一条 SUCCEEDED/FAILED AIAnalysis；进程崩溃不会留下 PROCESSING。compare 的 `raw_result` 仍需严格校验和脱敏，但不能进入业务结果事务。

### InformationItem 乐观锁

- AI 请求前记录每个候选 InformationItem 的 `version`；
- update/correction 使用 `WHERE id=:id AND user_id=:user_id AND version=:expected_version`，成功时 `version=version+1`；
- 影响行数为 0 时重新加载候选和最新内容，最多重新调用 AI 一次；
- 第二次仍冲突则记录 `CONCURRENT_UPDATE` 且 `retryable=true`，不得覆盖较新的信息；
- 人工 PATCH Information 同样必须提交 `expected_version`，冲突返回 HTTP 409。

### 时间约定

- AI 输出中的 `start_at`、`deadline` 必须是带时区 ISO 8601 或 null；
- 后端转换为 UTC 后再写入 MySQL；MySQL DATETIME 按无时区 UTC 解释；
- Event 至少有 start_at/deadline 之一，两者同时存在时 deadline 不早于 start_at；
- API 返回 UTC，前端按 Asia/Shanghai 显示。

### EventReminder 派生规则

- 提醒时间不要求 AI 输出，由服务端根据已校验的 `deadline` 计算，默认提前 24 小时。
- 新建带 Deadline 的 Event 时，Event 与 EventReminder 必须在同一短事务中提交。
- AI 更新 Deadline 时，默认提醒重算；旧提醒即使已 READ，也作为新的截止时间提醒重新进入 PENDING/DUE。`is_custom_time=true` 不改时间，`DISABLED` 绝不自动恢复。
- AI 删除 Deadline 或把 Event 置为完成、取消、过期时，未触发提醒不得继续进入 `DUE`。
- Event 完成、取消或过期时，尚未触发提醒转为 DISABLED；新计算的 remind_at 已经过期则立即进入 DUE。
- 提醒写入失败时，本次 AI 业务结果整体回滚，避免 Event 与提醒规则不一致。

## 11. 测试要求

### 必须有真实联调测试方式
提供手工/可选 integration test：

```text
AI_BASE_URL=...
AI_API_KEY=...
AI_DEFAULT_MODEL=...
```

然后执行：

```text
python scripts/test_ai_connection.py
```

脚本真实调用 API。

### 自动化测试
CI / 普通 pytest 不应强制消耗真实 Token。
自动化单元测试可 mock HTTP 层，但不能实现产品级 MockAIProvider。

必须覆盖：
- 正常 JSON
- 401
- model not found -> HTTP 502 `MODEL_NOT_FOUND`
- 429
- timeout
- invalid JSON
- schema invalid
- batch 部分失败
- batch 缺失/重复/额外 message_id
- PROCESSING 原子抢占、手工与自动分析碰撞
- 超过 10 分钟的 PROCESSING 恢复
- InformationItem 乐观锁成功、首次冲突重试和二次冲突失败
- Event 与默认提醒原子创建
- Deadline 更新不覆盖自定义或关闭的提醒
- Deadline 更新后默认 READ 提醒重新进入 PENDING/DUE
- retry/compare 允许状态、compare 不改业务数据
- action/target/relation 兼容矩阵和同一 target 冲突
- Provider 认证失败返回本站 HTTP 502，而非会话 401
