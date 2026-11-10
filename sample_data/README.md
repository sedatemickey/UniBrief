# Synthetic demo data

本目录记录 UniBrief 的合成演示数据说明。真实个人聊天、Cookie、Token 和附件不得提交。

- 生成入口：`scripts/reset_seed_demo.py`
- 数据来源：脚本内确定性字符串模板，不包含任何真实个人数据。
- 演示主用户：`demo_student`
- 隔离验证用户：`demo_observer`
- 数据包含多平台、多群、多种发送者、大量闲聊、有效通知、多条消息支持/更新/更正同一信息、附件元数据、AI 失败样例和待真实 AI 分析样例。

## 60 条待真实 AI 分析消息

- 数据文件：`sample_data/pending_ai_messages_60.json`
- 追加导入：`backend\.venv\Scripts\python.exe scripts\import_pending_ai_demo.py`
- 只校验文件：`backend\.venv\Scripts\python.exe scripts\import_pending_ai_demo.py --check-only`
- 默认目标用户：`demo_student`；可通过 `--username` 指定其他 ACTIVE 普通用户。
- 固定构成：60 条 Message，其中 52 条彼此独立的有效校园信息、8 条无信息量闲聊。
- 覆盖普通通知、作业提交窗口、课程调整、考试、校园活动、学生事务、校园生活和可信度较低的同学小道消息。
- 7 个批次分别落入 7 个合成 Channel，每个 Channel 少于自动批量阈值 20，避免刚导入就因数量阈值触发。
- 脚本通过正式 `ingestion_service.import_messages` 追加写入，不清空现有数据；固定 external ID 使重复执行返回 DUPLICATE，不会复制消息。
- 成功导入后严格验证 60 条都为 `PENDING`，且没有预生成 AIAnalysis、InformationItem 或关联关系。

> 若 FastAPI 后台任务正在运行，最早一批消息等待超过 `AI_BATCH_MAX_WAIT_SECONDS`（当前默认 300 秒）后仍会被自动分析。需要课堂手工批量操作时，应在导入后尽快完成选择和分析。
