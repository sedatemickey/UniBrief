阅读 AGENTS.md 和 docs/ 下全部设计文件。只完成 ROADMAP Phase 0。
不要提前实现业务表。
要求完成仓库骨架、用户自备 MySQL 8.x 的连接配置、后端 FastAPI health、前端 React/Vite/Ant Design 最小首页、环境变量模板和 README 启动步骤。不要创建 Docker Compose，也不要安装或管理 MySQL；通过 `DATABASE_URL` 验证用户提供的数据库连接。Vite 必须把 `/api` 和 `/health` 代理到 FastAPI，前端使用相对路径和 Cookie。
完成后实际运行可执行的检查，并更新 docs/PROGRESS.md。
