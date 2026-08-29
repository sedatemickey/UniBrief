阅读：
- AGENTS.md
- docs/COURSE_REQUIREMENTS.md
- docs/AI_INTEGRATION.md
- docs/DATABASE.md
- docs/ARCHITECTURE.md
- docs/PROGRESS.md

只完成 ROADMAP Phase 2。

本阶段明确禁止实现产品级 MockAIProvider。

必须实现真实可用的 OpenAI-compatible AI：

1. 使用服务端环境变量：
   - AI_BASE_URL
   - AI_API_KEY
   - AI_DEFAULT_MODEL
   - AI_TIMEOUT_SECONDS
   - AI_MAX_RETRIES

2. 实现 OpenAICompatibleProvider：
   - 优先使用 openai Python SDK AsyncOpenAI + custom base_url
   - Chat Completions 兼容调用
   - 真实 API 返回经过 Pydantic 严格校验

3. 实现：
   - GET /api/v1/ai/config
   - GET /api/v1/ai/models
   - POST /api/v1/ai/test
   - POST /messages/{id}/analyze 支持 model
   - POST /messages/analyze-batch 支持 model

4. /models 不受兼容供应商支持时：
   - 不得让系统不可用
   - API 明确返回 supports_listing=false
   - 后续前端必须允许手工 model ID

5. 完成：
Message -> AIAnalysis -> InformationItem -> MessageInformation -> Category/Tag -> Event
的事务化业务流程。

6. 必须覆盖：
   - useful=false 不生成 InformationItem
   - create/link/update
   - relation_type CREATE/SUPPORT/UPDATE/CORRECTION
   - Category/Tag 查找或创建
   - deadline/start_at -> Event
   - 401
   - model not found
   - 429
   - timeout
   - network error
   - invalid JSON
   - schema invalid
   - 失败后 Message 可重试

7. 提供 scripts/test_ai_connection.py：
   - 使用当前 .env 做真实 API 联调
   - 输出 base URL、model、latency、成功/失败
   - 永远不打印 API Key

8. 自动化 pytest 不应消耗真实 Token：
   - 可以 mock HTTP transport / SDK 方法
   - 但不允许实现可被应用运行时选择的 MockAIProvider

完成后：
- 若环境提供真实 API 配置，实际运行一次真实连接测试；
- 若当前开发环境没有 Key，不能伪造通过，应明确标记 integration test 未运行；
- 运行 pytest；
- 更新 docs/PROGRESS.md。
