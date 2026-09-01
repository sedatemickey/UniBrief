阅读 AGENTS.md、docs/DATABASE.md、docs/API.md、docs/CONFIGURATION.md、docs/NAPCAT_INTEGRATION.md、docs/ROADMAP.md、docs/PROGRESS.md。
只完成 ROADMAP Phase 1。

重点：
- 严格按 DATABASE.md 实现 16 张表的 ORM 和初始 Alembic migration；
- `information_item` 必须包含 `version` 乐观锁字段；
- 创建真实 PK/FK/UNIQUE/INDEX；
- 创建文档规定的 CHECK、ON DELETE 规则和 UTC 时间约定；
- 实现 user、system_setting、Argon2id、普通用户/管理员独立 HttpOnly Cookie、CSRF 和 session version；
- 实现注册开关、管理员命令行初始化、用户创建/启停/重置密码；
- 实现 platform/channel/sender/message 的 repository/service/API；
- 实现 JSON 批量导入，只匹配管理员预置的 ACTIVE Platform；相同 Message 返回 DUPLICATE，外部 ID 相同但核心内容不同返回 DUPLICATE_CONFLICT；
- 实现 CSV Adapter 和 NapCat OneBot 11 Adapter/桥接调用方法；NapCat 只负责把 OneBot 消息转换为统一导入格式，不发送消息、不自动回复；默认 NAPCAT_ENABLED=false，本阶段按用户要求不运行 NapCat 专项测试或真实联调；
- 重复导入同一数据不能产生重复 Message；
- 预置 Category；
- 做服务端分页和过滤；
- 实现附件元数据先入库、提交后后台下载、启动恢复、临时文件原子重命名、SSRF/路径穿越防护、鉴权下载和失败重试；
- 写 pytest；
- 从空数据库实际执行 alembic upgrade 验证。

不要做前端业务页面，不要实现 AI。
完成后更新 PROGRESS.md。
