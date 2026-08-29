只完成 ROADMAP Phase 3。
先核对现有 migration 和索引，不要破坏已完成业务。

实现至少三个课堂有意义的统计：
1. 渠道消息数、有效消息数、有效率；
2. Category 信息分布；
3. Tag 热门度 Top N；
另提供未来 7 天 Event 统计作为加分项。

优先用数据库 View 展示课程数据库能力。
增加一个简单、合理、可解释的 Trigger 或数据库自动维护机制。
如果 Stored Procedure 成本可控，实现时间区间渠道统计过程；否则在 DECISIONS.md 记录为何不做。
提供 Statistics API 和测试，更新 PROGRESS.md。
