阅读 AGENTS.md、docs/API.md、docs/ARCHITECTURE.md、docs/ROADMAP.md、docs/PROGRESS.md。
只完成 ROADMAP Phase 4。
使用 React + TypeScript + Ant Design + TanStack Query + ECharts。

实现可课堂演示的中文 UI：
- 普通用户登录、按开关显示注册、修改密码和退出
- 独立管理员登录、用户管理、注册开关、Platform/Category 管理和管理员改密
- Dashboard
- Information 列表
- Information 的分类/多标签 OR/重要度/状态/信息时间/事项时间/关键词组合筛选，排序、分页和筛选全部写入 URL，刷新和前进后退保持
- Information 详情（必须能追溯原始 Message）
- Message 列表，展示附件 PENDING/DOWNLOADING/DOWNLOADED/FAILED 状态并支持鉴权下载和失败重试
- Sources
- AI Settings：
  - 显示服务端 base URL / API Key 已配置状态
  - 加载真实模型列表
  - 下拉选择模型
  - 手工输入 model ID
  - 测试连接
  - 显示延迟与错误
- Import & Analyze：
  - 每次分析可以选择 model
- Statistics
- Calendar 月历与议程时间线，共用同一个 Event 范围接口
- Event 编辑、完成、取消、恢复，并处理 InformationItem version 冲突
- 站内提醒中心每 60 秒刷新，支持自定义提醒时间、关闭、重新启用和标记已读

不要做复杂动画。
优先清晰、稳定、信息密度合理。
所有列表有 loading/error/empty。
接口访问集中在 API client。
PATCH 表单必须区分“未修改”和“显式清空”；前端时间按 Asia/Shanghai 显示，提交带时区 ISO 8601。
完成后运行 npm run build 并更新 PROGRESS.md。
