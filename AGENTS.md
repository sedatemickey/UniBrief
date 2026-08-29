# AGENTS.md

## 1. 项目目标

本仓库是“校园多源消息智能聚合与信息管理系统”的数据库课程设计项目。

核心问题：
- 校园信息分散在 QQ、微信、钉钉等不同渠道；
- 大量闲聊淹没有价值信息；
- 系统需要把原始消息统一接入，交给 AI 判断、摘要、分类、打标签，并将有价值的信息结构化保存；
- 对具有时间属性的信息生成事项 Event；
- 用户可以在 Web 界面中浏览、搜索、筛选、查看来源、查看统计。

本课程设计按“单用户系统”实现，不做账号体系，不做 User/UserFeedback 表。

## 2. 强制阅读顺序

开始任何开发任务前，先阅读：
1. `docs/COURSE_REQUIREMENTS.md`
2. `docs/ARCHITECTURE.md`
3. `docs/DATABASE.md`
4. `docs/AI_INTEGRATION.md`
5. `docs/ROADMAP.md`
6. `docs/ACCEPTANCE.md`
7. `docs/PROGRESS.md`

涉及数据库结构修改时，必须重新阅读 `docs/DATABASE.md`。
涉及前后端接口修改时，必须检查 `docs/API.md`；若接口发生变化，同步更新该文件。

## 3. MVP 范围

必须实现：
- 消息平台 Platform 管理；
- 消息渠道 Channel 管理；
- 发送者 Sender 管理；
- 原始消息 Message 存储和查询；
- 附件元数据 MessageAttachment；
- AI 分析记录 AIAnalysis；
- 有效信息 InformationItem；
- Message 与 InformationItem 的多对多关联；
- Category 分类及其关联；
- Tag 标签及其关联；
- Event 事项；
- JSON/CSV 或模拟 Adapter 导入消息；
- AI Provider 抽象；
- 真实可用的 OpenAI-compatible AI Provider；
- 模型列表、模型选择与真实连接测试接口；
- Web 前端；
- 至少 3 个有实际意义的统计视图/接口/页面；
- MySQL 数据库迁移、索引、约束、测试和演示数据。

明确不做：
- 用户注册、登录、权限系统；
- User / UserFeedback；
- 真正逆向 QQ、微信、钉钉协议；
- 自动回复；
- 多 Agent；
- RAG / 向量数据库；
- 浏览器控制；
- 复杂 OCR 流水线；
- 移动端 App。

## 4. 技术栈

除非用户明确要求修改，否则固定使用：

### Backend
- Python 3.12+
- FastAPI
- SQLAlchemy 2.x
- Alembic
- Pydantic v2
- PyMySQL 或 mysqlclient
- pytest

### Database
- MySQL 8.x
- 字符集 utf8mb4
- 所有结构变更必须通过 Alembic migration 落地
- 不允许只改 ORM Model 而不生成 migration

### Frontend
- React
- TypeScript
- Vite
- Ant Design
- TanStack Query
- ECharts
- Vitest（关键工具函数和核心组件即可，不追求全覆盖）

### AI
- 使用真实 OpenAI-compatible API
- 优先使用 `openai` Python SDK + 自定义 `base_url`
- 运行时不提供 MockAIProvider
- 模型列表优先通过兼容的 `/v1/models` 获取
- 必须允许手工输入模型 ID，避免供应商不实现模型列表接口
- API Key 仅服务端环境变量保存，绝不返回给前端
- 自动化单元测试允许 mock HTTP transport，但产品/演示流程必须走真实 API

### Infrastructure
- Docker Compose 至少提供 MySQL
- `.env.example` 记录所有配置项
- 禁止提交真实 API Key、真实 Cookie、真实 QQ/微信/钉钉凭据

## 5. 仓库结构约束

保持以下主要结构：

```text
backend/
frontend/
infra/
docs/
prompts/
scripts/
sample_data/
```

Backend 采用分层：
- `api/`：HTTP 路由，只负责校验、调用 service、返回响应；
- `models/`：SQLAlchemy ORM；
- `schemas/`：Pydantic request/response；
- `repositories/`：数据库访问；
- `services/`：业务逻辑；
- `ai/`：AI Provider、Prompt、结果解析；
- `adapters/`：消息导入适配器；
- `db/`：session、base、初始化及 DB helpers。

不要把复杂业务逻辑写在 Router 中。

## 6. 数据库是本项目主角

数据库设计必须优先于界面炫技。

数据库规则：
- 表名和字段名统一 `snake_case`；
- 每个实体表有明确主键；
- 外键必须真实创建，不只在代码里逻辑关联；
- 多对多必须通过关联表实现；
- `event.information_id` 必须同时为 FK + UNIQUE，保证 InformationItem 1 : 0..1 Event；
- `tag.name`、`category.name` 应 UNIQUE；
- 平台外部 ID 应设计合理唯一约束，防止重复导入；
- 原始消息需要防重复导入；
- 所有枚举/状态字段在代码中集中定义；
- 不用 JSON 字段偷懒替代本来应建模的关系；
- 不把多个 tag 直接塞进逗号字符串。

至少实现并解释以下索引：
- `message(channel_id, sent_at)`
- `message(sender_id, sent_at)`
- `information_item(status, importance, created_at)`
- `event(deadline)`
- 适合导入去重的唯一索引

至少实现：
- 3 个数据库视图或等价统计查询；
- 1 个合理的 Trigger 或数据库级自动维护机制；
- 1 个 Stored Procedure（如果实现成本可控；若省略，必须在 `docs/DECISIONS.md` 说明原因）。

## 7. AI 处理约束

AI 不是数据库的替代品，且本项目运行时不得使用 MockAIProvider。

详细规则以 `docs/AI_INTEGRATION.md` 为准。

必须实现：
- `OpenAICompatibleProvider`
- `GET /api/v1/ai/config`
- `GET /api/v1/ai/models`
- `POST /api/v1/ai/test`
- 单条和批量分析时可显式选择 model
- 前端 AI 设置/模型选择界面
- `/models` 不受支持时允许手工输入 model ID
- 真实 AI 错误分类、超时、重试和可重试状态

配置至少包括：
- `AI_BASE_URL`
- `AI_API_KEY`
- `AI_DEFAULT_MODEL`
- `AI_TIMEOUT_SECONDS`
- `AI_MAX_RETRIES`

API Key：
- 仅服务端保存；
- 不写数据库；
- 不返回前端；
- 不出现在日志；
- 不提交 Git。

AI 返回必须经过 Pydantic 严格校验，不能把未校验的模型文本直接写入数据库。

AI 失败时：
- 不得丢失原始 Message；
- 不得留下半成品 InformationItem；
- Message 状态必须可重试；
- 记录清晰错误类型；
- 前端允许更换 model 后重试。

产品代码不提供 mock AI。
单元测试可以 mock 网络请求/HTTP transport，避免自动化测试消耗真实 Token。

## 8. 信息去重/关联策略

课程设计阶段不要实现复杂向量检索。

MVP 策略：
1. 先从最近 ACTIVE 的 InformationItem 中取有限候选；
2. 通过标题关键词/简单相似规则形成候选集；
3. 让 AI 在候选中决定 `create / link / update`；
4. MockAIProvider 使用确定性规则完成同样逻辑；
5. 所有 Message -> InformationItem 关系写入 `message_information`。

必须支持：
- 多条 Message 支持同一个 InformationItem；
- 一条 Message 产生多个 InformationItem 的数据模型能力；
- `relation_type` 至少支持 `CREATE / SUPPORT / UPDATE / CORRECTION`。

MVP 界面不强制提供“一条消息拆多事项”的复杂人工编辑器，但数据库和 service 不应阻止这种情况。

## 9. 编码规范

Python：
- 类型注解完整；
- 公共函数必须有简短 docstring；
- 尽量小函数；
- 不滥用全局变量；
- service 层负责事务边界；
- 所有数据库写操作必须明确 commit/rollback 策略。

TypeScript：
- 启用 strict；
- 禁止大面积 `any`；
- API 类型集中管理；
- 页面不要直接散落 fetch，统一通过 API client + TanStack Query。

通用：
- 不做无关重构；
- 不为了“高级”引入额外微服务、消息队列、Redis、Kafka；
- 优先可读、可演示、可测试；
- 代码和数据库命名使用英文，UI 显示使用中文；
- 不添加真实个人聊天数据到仓库，演示数据全部合成。

## 10. 测试与验收

每次完成代码修改后，必须运行与改动相关的检查。

Backend 最低：
```bash
pytest
```

若配置了：
```bash
ruff check .
```

Frontend 最低：
```bash
npm run build
```

若已有测试：
```bash
npm test
```

数据库：
- Alembic 能从空库升级到最新版本；
- 迁移后可以加载演示数据；
- 外键、唯一约束、关键索引真实存在。

每个阶段结束：
1. 更新 `docs/PROGRESS.md`
2. 记录关键决策到 `docs/DECISIONS.md`
3. 运行测试
4. 输出本阶段修改文件、测试结果、剩余风险
5. 不要自行扩大下一阶段范围

## 11. Git 工作方式

- 开工前检查 `git status`；
- 不删除用户已有改动；
- 每个阶段保持改动聚焦；
- 提交信息采用：
  - `feat: ...`
  - `fix: ...`
  - `docs: ...`
  - `test: ...`
  - `refactor: ...`
- 如果当前环境允许提交，每个 Roadmap Phase 可独立提交；
- 不强制改写已有提交历史。

## 12. 优先级原则

发生取舍时依次保证：
1. 数据不丢失；
2. 数据库结构正确；
3. 核心业务流程可跑通；
4. 课堂演示稳定；
5. 测试可重复；
6. UI 美观；
7. 扩展性。

如果工期紧：
- 可以降低 UI 动画和视觉复杂度；
- 可以只实现 Mock/JSON/CSV 消息 Adapter；
- 不可以用 Mock AI 替代真实 AI；若真实 API 不可用，应明确展示失败和重试机制，而不是伪造分析结果；
- 不得通过删除数据库核心关系来“省时间”。

## 13. 完成定义

只有当 `docs/ACCEPTANCE.md` 中的 MVP 条目全部满足，项目才算课程设计版本完成。

## 14. 课程评分约束

`docs/COURSE_REQUIREMENTS.md` 是项目级硬约束文件。

尤其必须保证：
- 数据表不少于 5；
- 第一次展示可解释需求分析、用例图、ER 图、实体关系；
- 第二次展示有代表性的完整业务流程；
- 至少 3 个统计功能；
- 演示实体数据不少于 30 条；
- 演示关联关系数据不少于 200 条；
- 健壮性和易用性不能只停留在文档；
- 报告需要有数据库规划、系统定义、需求分析、概念/逻辑/物理设计材料。

课程要求与普通工程“最佳实践”冲突时，优先满足课程明确评分项，同时保证设计合理。
