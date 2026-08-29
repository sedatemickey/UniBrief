# API.md

# 建议 REST API

统一前缀：`/api/v1`

## Health
- `GET /health`

## Platforms / Channels
- `GET /platforms`
- `POST /platforms`
- `GET /channels`
- `POST /channels`
- `PATCH /channels/{id}`


## AI Provider / Models
- `GET /ai/config`
  - 返回安全配置，不返回 API Key
- `GET /ai/models`
  - 调用真实 OpenAI-compatible `/models`
  - 服务不支持时返回 `supports_listing=false`
- `POST /ai/test`
  - body: `{ "model": "..." }`
  - 真实发起最小 API 请求，返回状态和 latency

## Messages
- `GET /messages`
  - query: platform_id, channel_id, sender_id, process_status, start, end, keyword, page, page_size
- `GET /messages/{id}`
- `POST /messages/import`
  - JSON 批量导入
- `POST /messages/{id}/analyze`
  - body: `{ "model": "optional-model-id" }`
- `POST /messages/analyze-batch`
  - body: `{ "message_ids": [...], "model": "optional-model-id" }`

## Information
- `GET /information`
  - query: category_id, tag_id, importance, status, keyword, start, end, page, page_size
- `GET /information/{id}`
  - 返回关联原始 Message、Category、Tag、Event
- `PATCH /information/{id}`
  - MVP 允许人工修正 title/summary/status/importance
- `POST /information/{id}/link-message/{message_id}`
  - 可选的人工关联能力

## Categories / Tags
- `GET /categories`
- `GET /tags`
- `GET /tags/popular`

## Events
- `GET /events`
  - query: status, deadline_before, deadline_after

## Statistics
- `GET /statistics/overview`
- `GET /statistics/channels`
- `GET /statistics/categories`
- `GET /statistics/tags`

接口实际实现后，以 OpenAPI 自动文档为准，并同步更新本文件。
