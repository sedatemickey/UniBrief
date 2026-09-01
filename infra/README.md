# infra

本目录只保存课程报告与数据库审阅所需的静态导出材料，不负责安装或启动 MySQL，也不包含 Docker Compose。

- `schema.sql`：由 Alembic offline SQL 导出的当前完整 schema，包含 16 表、seed 字典和高级对象；应用环境仍必须通过 `alembic upgrade head` 创建。
- `statistics.sql`：4 个 View、Trigger 和 Stored Procedure 的便于阅读副本；权威定义仍是 migration。

重新导出 schema：

```powershell
Push-Location backend
.\.venv\Scripts\python.exe -m alembic upgrade head --sql | Set-Content -Encoding utf8 ..\infra\schema.sql
Pop-Location
```
