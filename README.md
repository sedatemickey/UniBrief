# Campus Message Intelligence - Codex Bootstrap Pack

这是给 Codex 使用的项目开发约束与分阶段提示词包。

推荐用法：
1. 把本目录内容复制到新的 Git 仓库根目录；
2. 打开 Codex；
3. 先提交这些设计文档作为 baseline；
4. 使用 `prompts/01_phase0_bootstrap.md` 开始；
5. 每完成一个阶段再发送下一阶段提示词；
6. 或使用 `PROJECT_PROMPT.md` 作为总提示词，让 Codex 从 `docs/PROGRESS.md` 自动判断下一阶段。

建议不要一开始就让 Codex“一口气写完全项目”；分 Phase 更容易检查数据库设计和避免返工。

## v2 关键变化

- 删除运行时 MockAIProvider；
- 强制接入真实 OpenAI-compatible API；
- 增加真实模型列表、手工模型 ID、模型选择、测试连接设计；
- 新增 `docs/AI_INTEGRATION.md`；
- 新增 `docs/COURSE_REQUIREMENTS.md`，把 2026 课程 PPT 的硬性要求和评分项直接写入 Codex 上下文。
