# DECISIONS.md

# Architecture Decision Log

## D001 - 单用户 MVP
- Status: Accepted
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
