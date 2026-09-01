# 多用户系统架构

## 1. 系统定位

UniBrief 是多用户校园消息智能聚合与信息管理系统。普通用户拥有互相隔离的消息、信息、标签和事项空间；管理员只管理账号、注册开关及全局 Platform/Category，不读取用户私有内容。

外部采集工具把 QQ、微信、钉钉等消息转换为统一格式；本项目不逆向平台协议。项目必须实现独立的 [NapCatQQ](https://github.com/NapNeko/NapCatQQ) OneBot 11 Adapter/桥接调用方法，但运行时默认关闭：桥接进程连接 NapCat WebSocket，把 OneBot 消息事件转换为统一导入格式后调用 UniBrief 导入 API。真实 NapCat 联调等其他模块稳定、用户完成框架搭建后再进行。UniBrief 不管理 NapCat 生命周期，不发送 QQ 消息，不自动回复。

## 2. 总体数据流

```text
管理员入口 -> Admin Auth -> User / SystemSetting / Platform / Category

普通用户 -> User Auth -> 私有 Channel / Sender
                         |
JSON/CSV/NapCat Adapter --+-> Message -> MessageAttachment -> 附件下载 -> 本地文件存储
                                      -> OpenAI-compatible AI -> AIAnalysis
                                      -> MessageInformation -> InformationItem
                                                                 -> Category / Tag
                                                                 -> Event -> EventReminder
                                                                              -> 到期扫描
                                                                              -> 站内提醒
                                                                 -> 查询与统计
```

所有普通业务请求先经过认证中间件，从 HttpOnly Cookie 解析当前 `user_id`。Router、Service 和 Repository 都不得信任请求体中的用户归属。

## 3. 认证与设置

- 普通用户以唯一用户名和密码登录；是否开放自助注册由 `system_setting.registration_enabled` 控制，默认关闭。
- 管理员登录页只输入管理员密码；哈希存于 `system_setting.admin_password_hash`。
- 普通会话和管理员会话使用不同 Cookie、签名用途和 API 前缀。
- 密码使用 Argon2id；管理员通过命令行初始化/重置密码。
- `session_version` 用于在停用、重置或改密后使旧 Cookie 失效。
- `system_setting` 仅保存代码白名单内的系统杂项配置，敏感项不会通过设置 API 返回。

## 4. Backend 模块

- `auth_service`：用户登录、注册开关、退出、改密和会话校验。
- `admin_service`：管理员认证、用户管理和全局字典管理。
- `setting_service`：系统设置白名单、类型转换和敏感值保护。
- `platform_service`：全局 Platform 与用户 Channel。
- `sender_service`：当前用户范围内发送者归一化。
- `ingestion_service`：按用户幂等导入消息。
- `napcat_adapter`：必须实现、默认禁用的独立 OneBot 11 桥接进程；按配置绑定一个普通用户会话，把 QQ `message_id/group_id/user_id` 作为字符串外部 ID 归一化导入，不进入管理员权限域。Phase 1 只完成调用方法，不宣称已完成真实 NapCat 联调。
- `attachment_service`：下载受控 HTTP/HTTPS 附件，将文件写入本地存储并维护下载状态；失败不回滚 Message。
- `analysis_service`：只分析当前用户 Message，保存成功或失败 AIAnalysis，并使用 InformationItem version 乐观锁防止并发覆盖。
- `information_service`：在同一用户范围内创建/链接/更新 InformationItem。
- `classification_service`：共享 Category、私有 Tag。
- `event_service`：创建/更新 Event，并为带 Deadline 的事项维护默认提前 24 小时的提醒。
- `reminder_service`：同进程定期幂等扫描到期提醒，提供当前用户的站内提醒。
- `statistics_service`、`search_service`：所有查询按当前用户过滤；Information 支持分类、标签、重要度、状态、信息时间、事项时间和关键词组合筛选。

## 5. 前端页面

普通端：
1. 登录/按开关显示注册页；
2. Dashboard；
3. Information 列表与详情，筛选条件写入 URL；
4. Messages 与附件下载状态；
5. Sources；
6. AI 设置与真实连接测试；
7. Import & Analyze；
8. Statistics；
9. Calendar，提供月历与议程时间线；
10. 站内提醒中心；
11. 个人资料与修改密码。

管理员端：
1. 独立管理员登录；
2. 用户列表、创建、启停、重置密码；
3. 注册开关；
4. Platform 与 Category 管理；
5. 管理员修改密码。

管理员端不提供用户消息或信息入口。

## 6. 批量 AI 窗口

Phase 3 的单进程任务每 30 秒扫描一次。同一用户、同一 Channel 的待处理 Message 累计 20 条或最早一条等待满 5 分钟时触发一次 AI 请求；任一阈值先满足即可。用户可手动立即分析重要消息。手工和自动任务使用同一条件更新原子抢占，批次绝不跨用户或 Channel，返回结果按 Message 独立短事务保存，允许部分成功。超过 10 分钟仍为 PROCESSING 的 Message 恢复为 FAILED 并可重试。

## 7. 非功能目标

- 1000 至 10000 条 Message 下分页、筛选和用户级统计保持可用。
- 越权资源统一返回 404；管理员不能读取私有内容。
- 导入幂等，AI 失败不丢失 Message，成功结果使用短事务。
- 附件只写入配置的受控目录，数据库仅保存相对存储键和校验元数据；下载失败可重试且不影响原始消息入库。下载器拒绝本机、私网和链路本地目标，并在重定向后重新校验目标，避免 SSRF。
- 附件配置：`ATTACHMENT_STORAGE_DIR=./var/attachments`、`ATTACHMENT_MAX_BYTES=20971520`、`ATTACHMENT_TIMEOUT_SECONDS=30`、`ATTACHMENT_MAX_RETRIES=2`。
- 提醒扫描使用单进程周期任务和幂等状态更新，默认 `REMINDER_SCAN_INTERVAL_SECONDS=60`；不引入 Redis、消息队列、邮件或推送服务。
- Event 状态扫描与提醒扫描共用周期任务：deadline 到点优先把 UPCOMING/ONGOING 置为 EXPIRED，否则 start_at 到点把 UPCOMING 置为 ONGOING；COMPLETED/CANCELLED 只由用户操作，恢复为 UPCOMING 后下次扫描立即按当前时间重算。
- 所有业务时间经带时区 ISO 8601 输入，转换为 UTC 后写入 MySQL；API 返回 UTC，前端按 `Asia/Shanghai` 显示。
- Cookie 使用 HttpOnly、SameSite=Lax；生产环境使用 Secure，写请求校验 CSRF Token。
- 注册默认关闭；密码、API Key 和敏感设置不写日志、不返回前端。
