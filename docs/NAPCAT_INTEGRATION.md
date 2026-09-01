# NapCat OneBot 11 Adapter 设计

> 设计基线日期：2026-09-01。NapCat 是独立第三方项目，实际可用的网络适配和事件字段以其当前官方仓库与运行版本为准。

官方仓库：[NapNeko/NapCatQQ](https://github.com/NapNeko/NapCatQQ)。

## 1. 系统边界

UniBrief 不逆向 QQ 协议。NapCat 负责连接 NTQQ 并提供 OneBot 11 接口；UniBrief 只提供独立桥接进程，把 OneBot 消息事件转换为统一 Message 导入结构。

MVP 支持：
- NapCat OneBot 11 WebSocket Server；
- group/private message 事件；
- 文本、at、reply 等正文片段；
- 能取得 URL/文件信息的图片、文件、语音、视频附件元数据；
- 调用 UniBrief 普通用户 JSON 导入 API；
- 断线重连和重复事件幂等。

不支持：
- 在 UniBrief 内启动或管理 NapCat/QQ；
- 二维码登录、QQ Cookie 管理或协议逆向；
- 发送消息、自动回复、群管理；
- 以管理员身份导入或查看用户消息；
- 复杂 OCR、语音识别或附件内容理解。

## 2. 部署模型

```text
NTQQ <-> NapCatQQ <-> OneBot WebSocket <-> NapCat bridge process
                                             |
                                             v
                                  POST /api/v1/messages/import
                                             |
                                             v
                                      UniBrief/MySQL
```

- 一个 bridge 进程只绑定一个普通 UniBrief 用户；多用户需要分别启动进程和配置。
- bridge 使用普通用户登录接口建立 HttpOnly Cookie 会话，并保存内存中的 Cookie/CSRF；不得使用管理员 Cookie。
- 密码优先在启动时交互输入；无人值守部署可通过受控 Secret 注入，禁止写入配置文件、日志或 Git。
- NapCat 和 bridge 建议部署在同机或受信任内网；跨主机必须使用 TLS/WSS 和网络访问控制。

## 3. 配置

`.env.example` 登记但不填写真实值：

```env
NAPCAT_ENABLED=false
NAPCAT_WS_URL=ws://127.0.0.1:3001
NAPCAT_ACCESS_TOKEN=
NAPCAT_RECONNECT_MAX_SECONDS=30
NAPCAT_HEARTBEAT_TIMEOUT_SECONDS=90
NAPCAT_IMPORT_BATCH_SIZE=20
NAPCAT_IMPORT_FLUSH_SECONDS=5
UNIBRIEF_BASE_URL=http://127.0.0.1:8000
UNIBRIEF_USERNAME=
UNIBRIEF_PASSWORD=
```

`UNIBRIEF_PASSWORD` 仅用于部署 Secret；交互模式不要求该变量。日志只能显示用户名、目标主机和连接状态，不显示密码、Cookie、CSRF 或 NapCat token。

## 4. OneBot 事件映射

所有 OneBot ID 在进入 Adapter 时先转换为字符串，避免 JavaScript 大整数和供应商类型变化。

| OneBot 字段 | UniBrief 字段 |
|---|---|
| `self_id` | Adapter 实例标识/日志上下文，不作为 user_id |
| `message_id` | `message.external_id` |
| `group_id` | group Channel 的 `channel.external_id` |
| private `user_id` | private Channel 的 `channel.external_id` |
| `user_id` | `sender.external_id` |
| sender nickname/card | `sender.display_name` |
| `time` Unix 秒 | 带时区时间转换为 UTC `sent_at` |
| message/raw_message | 归一化 `content` |
| image/file/record/video segment | MessageAttachment 候选 |

Platform 固定归一化为：

```json
{"name":"QQ","type":"IM"}
```

Channel：
- 群消息：`channel_type=GROUP`，external_id 使用 group_id；
- 私聊：`channel_type=PRIVATE`，external_id 使用对方 user_id；
- Channel 名称优先使用事件/补充查询得到的群名或昵称，取不到时使用 `QQ群 {group_id}` / `QQ私聊 {user_id}`。

Sender：
- external_id 使用 user_id；
- source_type 默认 `UNKNOWN`，用户可在 Sources 页面改为 TEACHER/STUDENT/CLASS_LEADER 等；
- 不根据 QQ 群角色自动断言真实身份。

## 5. 消息段和附件

- text：拼入正文；
- at：正文写入可读占位，如 `@123456`；
- reply：正文保留引用标记；若能取得原 message_id，可写入 Adapter 日志上下文，但 MVP 不新增回复关系表；
- image/file/record/video：优先使用 segment 中稳定 file ID 作为 attachment.external_id；没有稳定 ID 时使用“消息 external_id + segment 序号 + 文件名/URL”生成稳定哈希；
- 临时 URL 缺失时，Adapter 可通过隔离的 NapCat/OneBot 文件信息兼容层查询；查询失败不得丢弃 Message，正文加入附件占位并记录可重试警告；
- 只有取得 HTTP/HTTPS URL 时才创建待下载 MessageAttachment；实际下载仍由 UniBrief attachment_service 执行统一 SSRF、大小、超时和校验规则。

## 6. 批量、幂等与重连

- bridge 最多累计 20 条或等待 5 秒后调用一次 `/messages/import`；这只是传输批量，与 AI 的 20 条/5 分钟窗口无关；
- 网络断开使用 1、2、5、10、30 秒上限的指数退避；恢复连接后继续消费新事件；
- OneBot 事件按至少一次处理，UniBrief 的 `UNIQUE(user_id, channel_id, external_id)` 是最终幂等保证；
- bridge 收到导入响应后逐条记录 INSERTED/DUPLICATE/FAILED 计数，但不得记录消息正文；
- bridge 进程意外退出期间 NapCat 是否重放由外部实现决定，MVP 不承诺离线补拉；课堂演示必须先启动 UniBrief、再启动 bridge，并保留 JSON/CSV 导入作为可靠降级方案。

## 7. 安全要求

- NapCat WebSocket 仅监听 localhost/受信任网段；不得无 token 暴露公网；
- 验证 WS URL scheme，只允许 ws/wss；生产远程连接使用 wss；
- 设置最大事件大小和批次大小，拒绝异常超大 payload；
- 日志脱敏 access token、密码、Cookie、CSRF、附件 URL 查询参数和消息正文；
- bridge 只持有绑定普通用户的权限，不能导入到其他 user_id；
- 不接收客户端传入 user_id，UniBrief 仍从 Cookie 会话决定归属。

## 8. 分阶段实现与延后联调

Phase 1 必须写好以下调用方法和边界，但暂时不运行 NapCat 专项测试，也不连接真实框架：WebSocket 客户端、鉴权 Header、事件解析、消息段映射、批量 flush、普通用户登录/CSRF、统一导入 API 调用、指数退避重连和脱敏日志。`NAPCAT_ENABLED=false` 是默认值。

在其他后端、数据库、AI 和前端模块完成并调试稳定，且用户自行搭建好 NapCat 框架后，再进入 NapCat 验收。验收顺序：

1. 先用保存的合成 OneBot payload 验证：
- group/private 映射；
- 字符串和超大数字 ID；
- text/at/reply/附件 segment；
- 重复 event 幂等；
- NapCat 断线重连；
- UniBrief 登录失效后重新登录；
- 导入 API 部分失败；
- token、Cookie、密码和正文不进入日志。

2. 再连接用户提供的真实 NapCat 实例做手工联调。不得把真实 QQ Cookie、聊天内容或 Access Token 保存到仓库；演示优先使用专门测试群和合成消息。

在上述两步完成前，`docs/ACCEPTANCE.md` 的 NapCat 项必须保持未勾选，项目说明只能写“调用方法已实现、真实联调待完成”。
