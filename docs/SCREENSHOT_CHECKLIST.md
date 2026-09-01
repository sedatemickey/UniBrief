# 报告与课堂展示截图清单

> 建议统一使用 1920×1080 浏览器窗口，隐藏真实 API Key、Cookie、数据库密码、附件绝对路径和真实聊天内容。截图文件按 `01_...png` 命名并记录拍摄日期。

## 1. 必拍数据库材料

- [ ] MySQL 版本、数据库名、utf8mb4、会话 `+00:00` 的安全检查输出
- [ ] Alembic `current` 为 `8f3c0d29a2b7 (head)`
- [ ] 16 张核心表列表
- [ ] ER 总图与三个模块局部图
- [ ] `message_information`、`information_tag` 复合外键
- [ ] `event.information_id` UNIQUE、`event_reminder.event_id` UNIQUE
- [ ] 关键索引列表
- [ ] 4 个 View 列表及一项查询结果
- [ ] Trigger 定义
- [ ] `sp_channel_statistics` 定义与 CALL 结果
- [ ] seed 数量输出（1006/34/238 等）

## 2. 必拍核心业务页面

- [ ] 普通用户登录页（注册开关状态）
- [ ] 独立管理员登录与管理面板
- [ ] Dashboard 总览
- [ ] 原始 Message 列表与筛选
- [ ] Message 详情、附件状态、下载/重试按钮
- [ ] JSON/CSV 导入结果（新增、重复、冲突）
- [ ] AI 设置：安全配置、模型列表或手工模型、连接测试
- [ ] Analyze 结果与实际 `model_name`
- [ ] Information 组合筛选和带查询参数 URL
- [ ] Information 详情：Category、Tag、Event、Reminder、原始 Message 证据
- [ ] 同一 InformationItem 的多条 Message 关系
- [ ] Calendar 月历视图
- [ ] Calendar 议程视图中的同一事项
- [ ] Reminder PENDING/DUE/READ/DISABLED 状态
- [ ] Event 编辑/完成/取消/恢复

## 3. 至少三项统计

- [ ] Channel 消息数/有效数/有效率图表
- [ ] Category 分布图表
- [ ] Tag 热门度 Top N 图表
- [ ] 未来 7 天 Event（加分项）

## 4. 健壮性与安全证据

- [ ] 完全重复导入返回 `DUPLICATE`
- [ ] 同外部 ID 核心内容冲突返回 `DUPLICATE_CONFLICT`
- [ ] AI 认证/模型/限流/超时/非法输出的明确错误（至少 1–2 个页面示例）
- [ ] AI 失败后 Message 保留且可重试
- [ ] 附件失败不回滚 Message
- [ ] 附件文件丢失被检测并转 FAILED
- [ ] 用户 B 访问用户 A 资源返回 404
- [ ] 管理员界面无用户私有内容入口
- [ ] 乐观锁冲突提示 409，不覆盖较新内容
- [ ] 空列表/无统计数据状态

## 5. 测试证据

- [ ] `pytest -q` 全通过
- [ ] `ruff check .` 全通过
- [ ] `alembic check` 无漂移
- [ ] 空库 downgrade base → upgrade head
- [ ] `npm run build` 通过
- [ ] `npm test -- --run` 通过
- [ ] clean clone 启动验证记录
- [ ] 真实 AI 联调输出（仅在真实配置成功后）
- [ ] NapCat 手工联调记录（仅在第三方框架搭建后）

## 6. 隐私复核

截图提交前逐张检查：

- [ ] 没有 `.env` 内容
- [ ] 没有 Authorization/Cookie/CSRF 值
- [ ] 没有数据库管理员密码
- [ ] 没有 AI Key 或 NapCat Token
- [ ] 没有真实 QQ/微信/钉钉聊天记录
- [ ] 没有服务器附件绝对路径
