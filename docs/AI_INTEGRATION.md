# AI_INTEGRATION.md

# 真实 OpenAI-compatible AI 接入设计

## 1. 原则

本项目**不提供运行时 MockAIProvider**。

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
  "model": "model-a"
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

### POST `/api/v1/messages/analyze-batch`

请求体：

```json
{
  "message_ids": [1, 2, 3],
  "model": "model-a"
}
```

所有同一批次分析使用所选模型，并将实际使用的模型名写入 `ai_analysis.model_name`。

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

最低结构：

```json
{
  "useful": true,
  "importance": 1,
  "confidence": 0.9,
  "action": "create",
  "target_information_id": null,
  "relation_type": "CREATE",
  "items": [
    {
      "title": "标题",
      "summary": "摘要",
      "source_type": "TEACHER",
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
- `useful=false` 时 `items` 可以为空；
- 所有字段写数据库前必须严格 Pydantic 校验；
- 对额外字段采用明确策略，不允许静默污染业务模型。

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
- 写清错误日志；
- 前端可再次选择模型并重试。

## 10. 事务边界

真实 AI HTTP 请求**不要放在长时间数据库事务内部**。

推荐：

1. 把 Message 标记 PROCESSING 并 commit；
2. 调真实 AI；
3. 校验输出；
4. 开启一个短事务：
   - insert AIAnalysis
   - create/link/update InformationItem
   - insert MessageInformation
   - Category / Tag 关联
   - Event
   - Message -> PROCESSED
5. commit

如果第 4 步失败：
- rollback；
- 另一个短事务把 Message 标记 FAILED。

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
- 404 model
- 429
- timeout
- invalid JSON
- schema invalid
- batch 部分失败
