# PROGRESS.md

> Codex 每完成一个 Phase 后更新这里。不要删除历史记录。

## Current Phase
- Phase 6 - 收尾（实现完成、外部验收待办）：文档、schema/SQL 导出、本机与 clean clone 安装/迁移/启动/测试均已完成；仍缺真实 AI Key/model、NapCat 第三方框架和最终课堂演示记录。
- Phase 2 代码与自动化测试已完成；当前 `.env` 没有 `AI_API_KEY`/`AI_DEFAULT_MODEL`，真实供应商联调按文档明确保持未完成，不伪造通过。

## Checklist
- [x] Phase 0 - 仓库初始化
- [x] Phase 1 - 数据库与基础后端
- [ ] Phase 2 - AI 分析与有效信息（仅剩真实供应商联调）
- [x] Phase 3 - 数据库高级对象和统计
- [x] Phase 4 - 前端核心页面
- [x] Phase 5 - 演示数据与健壮性
- [ ] Phase 6 - 收尾

## Completed phases

### Phase 0 - 2026-09-01
- 创建 FastAPI、React/Vite 最小运行骨架和 `/health`。
- 建立完整 `.env.example`、Vite 同源代理、MySQL 连接检查和启动 README。
- 实际验证 FastAPI、Vite 首页、`/health` 代理、MySQL 8/utf8mb4/UTC。

### Phase 1 - 2026-09-01
- 实现 16 张核心表 ORM、集中状态枚举、真实 PK/FK/复合 FK/UNIQUE/CHECK/INDEX。
- 创建 Alembic 初始 migration；预置 `registration_enabled=false`、`admin_session_version=1` 和 6 个 Category，不创建默认管理员密码。
- 实现 Repository / Service / Router 分层及明确 commit/rollback 边界。
- 实现 Argon2id、普通用户/管理员独立 HttpOnly Cookie、双提交 CSRF、Origin 检查和 session version 撤销。
- 实现注册开关、普通用户登录/退出/改密、管理员交互式密码初始化/重置、用户创建/启停/密码重置。
- 实现管理员 Platform/Category 和普通用户私有 Channel/Sender 管理；越权资源统一 404。
- 实现 JSON 逐条导入、CSV Adapter、完全重复 `DUPLICATE`、证据冲突 `DUPLICATE_CONFLICT` 和半开时间过滤。
- 实现附件元数据先提交、HTTP/HTTPS 校验、SSRF 公网地址限制、大小/超时/重定向限制、临时文件+原子重命名、SHA-256、鉴权下载、失败重试、启动恢复和磁盘缺失检测。
- 实现 NapCat OneBot 11 group/private、字符串 ID、消息段/附件映射、普通用户 Cookie/CSRF 导入、20 条/5 秒传输批量、登录恢复和指数退避重连；默认 `NAPCAT_ENABLED=false`，按计划未连接真实框架、未运行 NapCat 专项测试。
- 实现安全错误 envelope、request_id、数据库 readiness 和不返回敏感设置/存储路径的响应。

## Phase 2 implementation - 2026-09-01
- 使用官方 `openai` SDK `AsyncOpenAI` 和自定义 `base_url` 实现唯一运行时 `OpenAICompatibleProvider`，没有产品级 MockAIProvider。
- 实现安全 AI 配置、排序模型列表、不支持 `/models` 时手工输入回退、基础限频连接测试以及不打印 Key 的真实联调脚本。
- 实现严格 `extra=forbid` 的 AI JSON schema；顶层只含 `useful/items`，item 级 importance/confidence/action/target/relation/event，并校验固定兼容矩阵和带时区时间。
- 实现单条和 1..100 条批量 `retry|compare`；retry 原子抢占 Message，compare 只追加 AIAnalysis，批量逐 Message 独立短事务并允许部分成功。
- 保存 SUCCEEDED/FAILED AIAnalysis、真实 model、错误码、脱敏错误、耗时、严格结果和截断原始响应；Provider 401 映射为 502 AUTH_ERROR，不与本站会话 401 混淆。
- 实现 current-user 候选、create/link/update/correct、MessageInformation、Category/Tag 归一化、Event 和默认提前 24 小时 EventReminder 的原子业务写入。
- 实现 InformationItem version 乐观锁；首次冲突重新读取候选并重新调用 AI 一次，第二次冲突失败且不覆盖新数据。
- Deadline 更新会重算默认提醒并重置旧 READ；自定义提醒时间和 DISABLED 提醒受保护。
- `scripts/test_ai_connection.py` 已实际运行；因当前服务端未配置 Key/默认模型，脚本返回 `AUTH_ERROR` 并明确标记 integration test 未运行，未输出任何 Key。

## Phase 3 implementation - 2026-09-01
- 新 migration `8f3c0d29a2b7` 创建 4 个数据库 View：近期事项、渠道有效率、分类分布和标签热门度。
- 创建 `trg_information_item_set_updated_at`，直接 SQL UPDATE 也由 MySQL 自动维护 InformationItem.updated_at。
- 创建并由 Statistics service 实际调用 `sp_channel_statistics(p_user_id,p_start,p_end)`；渠道消息与有效消息使用 distinct Message 和 `[start,end)`。
- 实现 overview、channels、categories、tags、upcoming-events 5 个只读当前用户 Statistics API；上海“今天”窗口在服务端转换为 UTC。
- 实现单进程 Event/Reminder 幂等扫描：deadline 到点优先 EXPIRED，否则 start_at 到点 UPCOMING -> ONGOING；终态未触发提醒关闭，到期提醒 PENDING -> DUE。
- 实现同一 user/channel 的 PENDING 自动分析窗口、数量/等待阈值、逐 Message 条件抢占，以及超过配置时间的 PROCESSING 恢复和失败审计。
- FastAPI lifespan 启动并在 shutdown 取消两个周期 loop；不引入 Redis、消息队列或外部 Worker。
## Phase 4 implementation - 2026-09-01
- 建立集中 API client、类型层、CSRF Header、错误 envelope 处理、TanStack Query 与 React Router 架构。
- 实现普通用户登录、注册开关显示、修改密码、退出和受保护路由；独立管理员登录和管理端。
- 实现普通端 Dashboard、Information 列表/详情/编辑、Message 列表/详情/附件下载重试、Sources、AI Settings、Import & Analyze、Statistics、Calendar/议程和提醒中心。
- Information 支持分类、多标签 OR、重要度、状态、信息时间、事项时间、关键词、排序和分页；筛选与分页写入 URL，刷新和前进后退保持。
- Information 详情展示 Categories、Tags、Event、Reminder 与原始 Message 证据；编辑提交 expected_version，冲突不覆盖。
- AI Settings 读取安全服务端配置、加载真实模型列表、允许手工模型 ID、执行真实连接测试并展示延迟/错误；模型选择保存 localStorage。
- Import & Analyze 支持 JSON、CSV multipart、选择消息、选择模型、单页批量 retry/compare，并展示部分成功结果。
- 管理端支持用户创建/启停/重置密码、注册开关、管理员改密、Platform/Category 创建和启停。
- Calendar 月历与议程共用 Event range API；支持编辑时间、完成、取消、恢复并携带 Information version。
- 提醒中心每 60 秒刷新，支持自定义时间、关闭/重新启用和 DUE 标记已读。
- 补齐 Information、Tag、Event、Reminder 后端 API 与响应 schema，所有查询经 InformationItem/Event 限定当前用户。
## Phase 5 implementation - 2026-09-01
- 新建 `scripts/reset_seed_demo.py --force` 一键 reset + seed，确定性生成完全合成的 1006 条 Message、34 条 InformationItem、238 条 Message-Information、24 条 Event、24 条 Reminder 和 24 条附件元数据。
- 数据覆盖多平台/多渠道/老师/班长/学生/管理员、闲聊过滤、重复/冲突导入口径、AI 失败样例、待真实 AI 样例、同一信息多关系证据和隔离用户。
- README 补充一键 seed、演示账号和课堂演示顺序；后续只有在环境提供真实 AI Key/模型时才运行脚本式真实联调。
- 重复导入、AI 错误处理、事务回滚、组合筛选、统计和隔离已由 44 项后端测试覆盖。
## Phase 6 implementation - 2026-09-01
- 重写 README 的 clean clone 启动、管理员初始化、demo seed、真实 AI、测试和文档索引，移除“下一步 Phase 5”的过时口径。
- 新增 `docs/DATA_DICTIONARY.md`、`docs/ER_MAPPING.md`、`docs/STATISTICS_SQL.md`、`docs/DEMO_SCRIPT.md`、`docs/TESTING.md`、`docs/SCREENSHOT_CHECKLIST.md`、`docs/KNOWN_LIMITATIONS.md`。
- 通过 Alembic offline SQL 导出 `infra/schema.sql`，包含 Alembic version 表、16 张核心表、migration seed、4 View、Trigger 和 Stored Procedure；新增 `infra/statistics.sql` 便于报告引用。
- 新增 `scripts/verify_phase6.py`，静态核对 12 个收尾文件、43 个环境变量、16 张核心表、6 个高级对象及无 Docker Compose 约束。
- 更新 `pre/README.md`、当前答辩材料和 Event 状态图说明，明确早期单用户文档已废止、第一次展示稿是历史口径，最终演示使用当前 16 表/附件/提醒实现。
- 更新 `PROJECT_TREE.txt`，与当前仓库结构一致。
- 本地浏览器 smoke test 覆盖普通登录、Dashboard、Information 列表/详情、Message/附件、Sources、Import、AI Settings、Statistics、Calendar/议程和 Reminder；修复 Dashboard 因每次 render 生成新时间范围导致的重复请求循环，补齐 Information 详情的 Category/Tag/Reminder 展示，并清理 Ant Design 6 已废止属性警告。
- 从提交 `89f224f` 建立独立 clean clone：全新 Python 3.12 venv `pip install '.[dev]'`、`npm ci`、空测试库 downgrade/upgrade、pytest、ruff、alembic check、frontend build/test、FastAPI 8010 `/health` 与 Vite 5174 页面均通过。
- clean clone 在日期边界复测发现 upcoming-events 测试写死 2026-09-02；已改为按 Asia/Shanghai“明天”动态生成并重新通过 44 项测试。
## Latest validation
- Backend tests: on 2026-09-01 `backend/.venv/Scripts/python.exe -m pytest -q` passed, **44 tests passed**；覆盖认证、导入/附件、AI Provider/结构化分析、统计高级对象、周期任务、Information 组合筛选、乐观锁、Event/Reminder 生命周期与跨用户隔离。
- Backend lint: on 2026-09-01 `backend/.venv/Scripts/python.exe -m ruff check .` passed.
- OpenAPI: 55 paths；Phase 2 AI、Phase 3 Statistics 和 Phase 4 Information/Tag/Event/Reminder 接口均已注册。
- ORM/migration drift: Phase 3 test DB 已验证 `8f3c0d29a2b7 -> 4ae437bb1586 -> 8f3c0d29a2b7`，downgrade 后高级对象均为 0，重新 upgrade 后 `alembic check` 无漂移。
- Empty-schema migration: on 2026-09-01 dedicated `unibrief_test` successfully completed `alembic downgrade base -> upgrade head` and recreated all 16 tables/seeds.
- Development database: `unibrief` at revision `8f3c0d29a2b7`; MySQL 8.0.46、utf8mb4、UTC session check passed.
- Frontend tests: on 2026-09-01 `npm test -- --run` passed, **2 tests passed**，覆盖数组查询参数序列化和 Asia/Shanghai 时间显示。
- Frontend build: on 2026-09-01 `npm run build` passed；Vite 输出 chunk size warning（不影响构建）。React/TypeScript strict、Ant Design、TanStack Query、ECharts 与 React Router 完整业务 UI 已实现。`npm test -- --run` 同日通过，2 tests passed。

## Environment notes
- 正式后端虚拟环境使用 Python 3.12.5；OpenAI SDK 当前安装版本为 2.54.0。
- 本机标准 npm wrapper 被用户级 prefix 配置影响；README 保留 Node 安装目录 npm CLI 的临时调用方式。
- pytest 的系统临时目录 ACL 不可访问，因此固定使用仓库内、Git 忽略的 `backend/.pytest-tmp`。
- MySQL 由用户自行管理；仓库不包含 Docker Compose。

## Known risks / next phase
- Phase 2 唯一未完成的验收是使用用户提供的真实 AI Key/model 成功连接并分析至少一条消息；当前配置缺失，不能伪造通过。
- Phase 6 本机与 clean clone 的文档、schema/SQL、依赖安装、空库迁移、seed、pytest、ruff、alembic check、frontend build/test 和实际启动均已完成。
- NapCat 真实框架联调仍依赖用户搭建第三方框架；最终业务演示清单需由用户按 `docs/DEMO_SCRIPT.md` 完成或录屏。
- FastAPI 当前依赖组合会输出上游 TestClient 弃用 warning，但测试结果有效；后续依赖升级时复核。

## 2026-09-02 课堂手工 AI 分析数据追加

- 新增 `sample_data/pending_ai_messages_60.json`：固定 60 条合成校园原始消息，包含 52 条独立有效信息和 8 条无用闲聊。
- 新增 `scripts/import_pending_ai_demo.py`：通过正式 ingestion service 追加导入、固定 external ID 幂等、严格验证 60 条均为 PENDING，不执行 reset。
- 已实际写入开发库 `unibrief` 的 `demo_student` 私有空间：60 inserted、0 duplicate、0 failed，Message ID 为 1014–1073。
- 数据覆盖普通通知、作业提交窗口、课程/考试、活动、行政生活和同学小道消息；未预生成 AIAnalysis、InformationItem 或 MessageInformation，等待真实 AI 批量分析。
- 验证：数据文件 check-only 通过；新增脚本 Ruff 通过；后端 pytest 44 passed（仅现有 Starlette/httpx 弃用警告）。

## 2026-09-01 Dashboard 事项统计修复

- 修复 Dashboard 将最近 29 天历史时间窗错误传给 overview 的问题；未来事项不再被 `end=当前时间` 排除。
- Dashboard 总览卡片改为读取当前用户全局状态总数；渠道、分类图表继续保持最近 29 天统计口径。
- 使用 `sedatemickey` 开发数据复现：修复前未来事项为 0，全局正确值为 50；当前没有 DUE 状态提醒，因此到期提醒正确值仍为 0。`npm test -- --run` 2 tests passed，`npm run build` 通过（仅保留已有 chunk size warning）。
