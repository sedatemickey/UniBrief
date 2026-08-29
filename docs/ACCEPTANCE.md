# ACCEPTANCE.md

# 课程设计 MVP 验收清单

## 数据库
- [ ] MySQL 8 可从空库通过 Alembic 创建全部表
- [ ] 13 张核心表存在
- [ ] 主键/外键/唯一约束正确
- [ ] Event.information_id 为 UNIQUE
- [ ] Message 防重复导入
- [ ] 关键索引存在
- [ ] 至少 3 个统计查询或 View
- [ ] 至少 1 个数据库级自动维护机制
- [ ] 演示数据中实体数据 >= 30
- [ ] 演示数据中关系数据 >= 200

## 后端
- [ ] /health
- [ ] Platform/Channel 基础管理
- [ ] Message JSON/CSV 或 JSON 导入
- [ ] Message 查询/分页/过滤
- [ ] 运行时无 MockAIProvider
- [ ] 真实 OpenAI-compatible Provider
- [ ] AI Base URL / API Key / default model 可通过环境变量配置
- [ ] GET /ai/models 可从真实服务读取模型列表，或明确报告不支持
- [ ] 可手工输入模型 ID
- [ ] POST /ai/test 可真实测试所选模型
- [ ] 单条/批量分析可指定模型
- [ ] AIAnalysis.model_name 保存实际使用模型
- [ ] 单条/批量 Analyze
- [ ] AIAnalysis 持久化
- [ ] InformationItem 创建/链接/更新
- [ ] Category
- [ ] Tag
- [ ] Event
- [ ] 统计 API
- [ ] 错误处理和日志
- [ ] pytest 通过

## 前端
- [ ] Dashboard
- [ ] Information 列表
- [ ] Information 详情及原始来源
- [ ] Message 列表
- [ ] Sources
- [ ] AI Settings / Model Selection
- [ ] Import / Analyze
- [ ] Statistics
- [ ] 中文 UI
- [ ] npm run build 通过

## 业务演示
- [ ] 导入模拟消息
- [ ] 展示闲聊过滤
- [ ] 展示真实 API 模型选择和连接测试
- [ ] 展示真实 AIAnalysis
- [ ] 展示有效信息生成
- [ ] 展示多条 Message 支持同一 InformationItem
- [ ] 展示 Category
- [ ] 展示 Tag
- [ ] 展示 deadline -> Event
- [ ] 展示至少 3 项统计
- [ ] 展示错误/重复数据处理

## 文档
- [ ] README
- [ ] DATABASE.md
- [ ] API.md
- [ ] 数据字典
- [ ] ER 图和真实表结构一致
- [ ] 演示步骤文档
- [ ] 测试说明
