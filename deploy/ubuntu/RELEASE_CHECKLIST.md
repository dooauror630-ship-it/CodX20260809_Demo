# Ubuntu 发布检查清单

1. 使用独立的 `_test` 数据库执行 `scripts/mysql-migration-drill.ps1` 对应的迁移与恢复演练，并保留输出。
2. 确认正式数据库备份和附件目录备份均可恢复，记录 SHA-256。
3. 生产环境设置 `AGRI_ALLOW_SELF_REGISTRATION=0`、强随机 `AGRI_SECRET_KEY`，HTTPS 终止后设置 `AGRI_COOKIE_SECURE=1`。
4. 使用迁移账号执行 `flask db upgrade`，再使用应用账号执行 `schema-check`、`inventory-reconcile` 和 `trade-reconcile`。
5. 执行 `scripts/security-scan.ps1`、`scripts/release-check.ps1`，保存测试输出和版本号。
6. 只读检查 `/api/health`、登录、农场列表、库存分析和销售经营页面；确认正式库仍未被测试数据污染。
7. 发布失败时停止服务，按备份恢复演练步骤恢复，不直接手工修改业务表。
