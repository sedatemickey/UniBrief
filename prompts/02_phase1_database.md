阅读 AGENTS.md、docs/DATABASE.md、docs/ROADMAP.md、docs/PROGRESS.md。
只完成 ROADMAP Phase 1。

重点：
- 严格按 DATABASE.md 实现 13 张表的 ORM 和初始 Alembic migration；
- 创建真实 PK/FK/UNIQUE/INDEX；
- 实现 platform/channel/sender/message 的 repository/service/API；
- 实现 JSON 批量导入，使用 platform+external_id/channel+external_id 幂等归一化；
- 重复导入同一数据不能产生重复 Message；
- 预置 Category；
- 做服务端分页和过滤；
- 写 pytest；
- 从空数据库实际执行 alembic upgrade 验证。

不要做前端业务页面，不要实现 AI。
完成后更新 PROGRESS.md。
