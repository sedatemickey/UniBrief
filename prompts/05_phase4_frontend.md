只完成 ROADMAP Phase 4。
使用 React + TypeScript + Ant Design + TanStack Query + ECharts。

实现可课堂演示的中文 UI：
- Dashboard
- Information 列表
- Information 详情（必须能追溯原始 Message）
- Message 列表
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

不要做登录页。
不要做复杂动画。
优先清晰、稳定、信息密度合理。
所有列表有 loading/error/empty。
接口访问集中在 API client。
完成后运行 npm run build 并更新 PROGRESS.md。
