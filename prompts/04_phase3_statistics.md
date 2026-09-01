阅读 AGENTS.md、docs/DATABASE.md、docs/API.md、docs/AI_INTEGRATION.md、docs/ROADMAP.md、docs/PROGRESS.md。
只完成 ROADMAP Phase 3。
先核对现有 migration 和索引，不要破坏已完成业务。

实现至少三个课堂有意义的统计：
1. 渠道消息数、有效消息数、有效率；
2. Category 信息分布；
3. Tag 热门度 Top N；
另提供未来 7 天 Event 统计作为加分项。

优先用数据库 View 展示课程数据库能力。
增加一个简单、合理、可解释的 Trigger 或数据库自动维护机制。
必须实现 `sp_channel_statistics(p_user_id, p_start, p_end)` Stored Procedure。
实现单进程周期任务：每 30 秒检查同一用户、同一 Channel 的 PENDING Message，达到 20 条或最早等待 5 分钟时自动分析；使用条件更新原子抢占，并恢复超过 10 分钟的 PROCESSING。
同一周期任务还负责 EventReminder 到期扫描，并严格维护 Event：deadline 到点优先把 UPCOMING/ONGOING 置为 EXPIRED；否则 start_at 到点把 UPCOMING 置为 ONGOING；COMPLETED/CANCELLED 不自动改写，恢复 UPCOMING 后下次扫描重新推导。
所有统计 start/end 和 Stored Procedure 使用 `[start,end)` 半开区间；事件范围查询按 API.md 的相交规则。
提供 Statistics API 和测试，更新 PROGRESS.md。
