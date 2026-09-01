# PROGRESS.md

> Codex 每完成一个 Phase 后更新这里。不要删除历史记录。

## Current Phase
- Phase 0 - Not started

## Checklist
- [ ] Phase 0 - 仓库初始化
- [ ] Phase 1 - 数据库与基础后端
- [ ] Phase 2 - AI 分析与有效信息
- [ ] Phase 3 - 数据库高级对象和统计
- [ ] Phase 4 - 前端核心页面
- [ ] Phase 5 - 演示数据与健壮性
- [ ] Phase 6 - 收尾

## Latest validation
- Backend tests: not run
- Frontend build: not run
- DB migration from empty: not run
- Environment recheck: on 2026-09-01 `C:\Users\ASUS\AppData\Local\Programs\Python\Python312\python.exe --version` returned Python 3.12.5; Python 3.11.9 is the separate MSYS2 interpreter currently resolved inside the Codex sandbox
- MySQL readiness: on 2026-09-01 TCP login to `root@127.0.0.1:3306` succeeded on MySQL 8.0.46; `unibrief` and `unibrief_test` were created with `utf8mb4_0900_ai_ci`; application connections must set session time zone to UTC
- Design consistency: on 2026-09-01 the pre-development baseline was frozen as a 16-table multi-user MVP with user-managed MySQL 8.x (no Docker Compose), Vite same-origin proxy, local attachments, EventReminder, item-level AI confidence, retry/compare modes, half-open time ranges, exact Event transitions, mandatory Stored Procedure, and a default-disabled NapCat bridge whose real integration test is deferred; no implementation exists

## Known risks
- 多用户复合外键和用户级统计需要在 Phase 1/3 用真实 MySQL 验证。
- MySQL 8.x、DATABASE_URL 和 TEST_DATABASE_URL 已就绪；空库 migration 和数据库集成测试仍需等 Phase 0/1 代码生成后执行。
- system_setting 必须坚持键名白名单，避免演变为无约束业务数据容器。
- HttpOnly Cookie 跨开发端口配置、CSRF 和 session version 需要专项测试。
- 附件下载必须限制协议、大小、超时和目标地址，并防止路径穿越、SSRF 与敏感错误泄露。
- EventReminder 新表、到期扫描幂等性及 Deadline 更新规则需要在 Phase 1 至 3 用真实 MySQL 验证。
- 月历/议程时间范围口径、组合筛选 SQL 和 URL 状态同步需要前后端联合测试。
- NapCat bridge 先实现调用方法但暂不测试；等其他模块稳定且用户搭好 NapCat 后，再执行合成事件和真实手工联调。断线期间是否补拉由外部框架决定，JSON/CSV 始终作为可靠降级路径。
- 当前二进制 PPT/图片中的 ER 图仍需按 16 表、19 外键和 EventReminder 重新绘制；开发以 `docs/DATABASE.md` 为源事实。
