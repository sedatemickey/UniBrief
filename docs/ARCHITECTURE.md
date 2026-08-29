# ARCHITECTURE.md

## 1. 系统定位

单用户校园多源消息智能聚合与信息管理系统。

系统外部的数据采集工具负责把 QQ / 微信 / 钉钉等消息转换为统一格式；本项目本身不逆向这些平台协议。课程设计阶段提供 Mock / JSON / CSV 导入方式。

## 2. 总体架构

```text
外部消息源 / 模拟数据
        |
        v
Message Adapter
        |
        v
FastAPI Ingestion API
        |
        v
MySQL: Message
        |
        +------> MessageAttachment
        |
        v
真实 OpenAI-compatible AI Service
        |
        +------> AIAnalysis
        |
        v
Information Service
        |
        +------> MessageInformation
        +------> InformationItem
        +------> InformationCategory -> Category
        +------> InformationTag -> Tag
        +------> Event
        |
        v
REST API
        |
        v
React Web UI
```

## 3. Backend 模块

- `platform_service`: 平台/渠道基础数据
- `sender_service`: 发送者识别和归一化
- `ingestion_service`: 幂等导入消息
- `analysis_service`: 调用 AI Provider、保存 AIAnalysis
- `information_service`: 创建/链接/更新 InformationItem
- `classification_service`: Category / Tag 归一化
- `event_service`: 从 AI 结果创建/更新 Event
- `statistics_service`: 统计查询
- `search_service`: 信息和原始消息筛选

## 4. 前端页面

MVP 页面：
1. Dashboard
   - 今日/近期重要信息
   - 未来 7 天事项
   - 统计卡片
2. 信息流 Information
   - 按 Category、Tag、重要度、状态筛选
   - 关键词搜索
3. 信息详情
   - 摘要、类别、标签、事项时间
   - 关联的原始 Message 列表
4. 原始消息 Messages
   - 按 Platform / Channel / Sender / 时间过滤
   - AI 处理状态
5. 消息源 Sources
   - Platform / Channel 列表
6. AI 设置
   - 显示服务端 Base URL / Key 是否已配置
   - 从真实 API 加载模型列表
   - 模型下拉选择 + 手工输入 model ID
   - 测试连接
7. 导入与 AI 处理
   - 上传 JSON/CSV
   - 选择本次使用的真实模型
   - 触发单条/批量分析
   - 显示成功/失败数
8. 统计 Statistics
   - 渠道消息量与有效率
   - 信息分类分布
   - 热门标签 Top N
   - 可选：未来截止事项趋势

## 5. 课程演示主流程

演示建议固定使用合成数据：

1. 导入一批来自“QQ-数据库课程群”的模拟消息；
2. 展示 Message 已进入数据库；
3. 在 AI 设置中从真实 OpenAI-compatible API 加载/选择模型并测试连接；
4. 触发真实 AI 分析；
5. 一部分闲聊被标记为无用；
6. 有价值消息生成/支持 InformationItem；
7. 同一事项的多条消息通过 MessageInformation 聚合；
8. AI 自动生成 Category、Tag；
9. 有截止时间的消息生成 Event；
10. 前端信息流出现有效信息；
11. 点击信息详情可追溯原始消息；
12. Dashboard/Statistics 展示至少三个统计结果。

## 6. 非功能目标

- 单机课程演示场景下稳定运行；
- 1000~10000 条消息的数据量下列表分页和筛选保持可用；
- 所有列表服务端分页；
- 真实 AI 失败不影响消息入库，并支持更换模型后重试；
- 导入必须幂等；
- 所有关键业务写入使用事务。
