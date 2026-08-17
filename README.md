# 综合农牧业管理系统

当前 V1 面向家庭农场、小型合作社和单一经营主体，优先解决少量人员在电脑与手机上共同记清生产、库存、销售和利润的问题，不以大型集团多公司核算为当前目标。系统已完成账号与角色隔离、基础资料、采购库存闭环和库存分析。阶段 4 已具备生猪批次、存栏流水、饲喂领料与批次成本归集、健康/防疫/用药、称重和 ADG；负责人和操作员可登记，查看员只读。系统采用 Vue 3 模块化前端、Flask 模块化单体后端、MySQL、Waitress 和 Nginx。

详细需求、架构、数据库与分阶段计划见 [V1 开发文档](docs/综合农牧业管理系统开发文档-v1.md)。

## 当前交付状态

- 当前代码目标迁移版本：`0011_livestock_production`。
- 正式数据库仍为 `0010_livestock`；已生成并校验 `0011`，待使用具备 DDL 权限的一次性迁移账号发布，日常业务账号不会被临时提权。
- 阶段 3 状态：已完成采购入库、采购退货、仓库调拨、生产领退料、库存盘点、效期预警、库存趋势和生产净耗用排行。
- 阶段 4 状态：进行中；批次、存栏、饲喂领料、健康/用药、称重、饲料成本和 ADG 已完成，FCR、完整批次成本和趋势分析待开发。
- 最近已验证的升级前备份：`backups/agriculture_management-before-livestock-production-20260817-194445.sql`，SHA256 为 `F9E8501C632735C5013014958EA6F7503236189C13024A68AC549A98211D5A97`。
- 当前质量门禁：Ruff、pytest、ESLint、Vitest、Vue 类型检查和 Vite 构建通过；MySQL 集成、桌面与移动 Playwright 及正式库对账将在 `0011` 正式迁移后复验。

## 后续优化优先级

1. 完成生猪饲喂、健康、称重分析，补齐 FCR 与批次完整成本。
2. 建设客户、销售、收付款和成本核算，闭合“采购—生产—销售—利润”。
3. 优化手机快速录入，并按实际使用反馈评估 PWA、微信入口或弱网能力。
4. 增加 Excel 导入导出、备份恢复、审计查询和经营周期归档。
5. 选择 2–5 个真实家庭农场或小型合作社，持续运行一个完整生产周期并据此收敛功能。

## 项目结构

```text
backend/app/        Flask 应用工厂、核心能力和业务模块
backend/migrations/ Alembic 数据库迁移
frontend/src/       Vue 3 + TypeScript + Element Plus + ECharts
frontend/dist/      Vite 生产构建产物（不提交）
nginx/conf/         反向代理与静态资源配置
tests/              后端单元及 MySQL 集成测试
scripts/test.ps1    统一自动化检查入口
```

## 环境要求

- Python 3.11+
- MySQL 8.0+（本机当前为 MySQL 9.x）
- Node.js 20.19+ 与 npm
- Windows Nginx（项目已包含 `nginx/nginx.exe`）

## 首次安装

```powershell
cd D:\zongheguanlixitong
python -m pip install -r requirements.txt

cd frontend
npm.cmd install
npm.cmd run build
cd ..
```

MySQL 连接保存在 `backend/instance/mysql.json`，也可用 `AGRI_MYSQL_HOST`、`AGRI_MYSQL_PORT`、`AGRI_MYSQL_USER`、`AGRI_MYSQL_PASSWORD`、`AGRI_MYSQL_DATABASE` 和 `AGRI_MYSQL_SSL` 覆盖。`backend/instance/` 中的密钥和数据库配置，以及项目根目录 `backups/` 中的数据库备份，均已被 Git 忽略。

应用账号默认只具备业务读写权限，不应授予建表权限。首次建库或升级结构时使用一次性的迁移账号：

```powershell
$env:AGRI_MYSQL_USER = "具备 DDL 权限的迁移账号"
$env:AGRI_MYSQL_PASSWORD = "迁移账号密码"
$env:AGRI_SKIP_SCHEMA_CHECK = "1"
python -m flask --app backend.wsgi:app db upgrade
Remove-Item Env:AGRI_SKIP_SCHEMA_CHECK
Remove-Item Env:AGRI_MYSQL_PASSWORD
Remove-Item Env:AGRI_MYSQL_USER
python -m flask --app backend.wsgi:app schema-check
```

初始化或重置管理员账号时，通过临时环境变量传入密码，命令不会输出密码：

```powershell
$env:AGRI_BOOTSTRAP_ADMIN_PASSWORD = "请设置管理员密码"
python -m flask --app backend.wsgi:app bootstrap-admin --username admin --display-name "系统管理员"
Remove-Item Env:AGRI_BOOTSTRAP_ADMIN_PASSWORD
```

管理员可以查看全局账户分析并维护所有用户；普通用户只能访问个人工作台和后续生产经营业务。

## 启停服务

```powershell
.\start.ps1
# 浏览器访问 http://localhost:8080
.\stop.ps1
```

`start.ps1` 使用 Waitress 监听 `127.0.0.1:5000`，Nginx 监听 `8080` 并提供同源 `/api/` 反向代理。若使用其他 Nginx，可传入 `-NginxExe`。

## 自动化测试

```powershell
# Ruff、SQLite 后端测试、ESLint、Vitest、生产构建
.\scripts\test.ps1

# MySQL 集成和浏览器测试必须连接隔离测试库
$env:AGRI_MYSQL_DATABASE = "agriculture_management_test"
.\stop.ps1
.\start.ps1
.\scripts\test.ps1 -MySql -E2E
.\stop.ps1
Remove-Item Env:AGRI_MYSQL_DATABASE

# 对当前配置的数据库执行只读库存余额与流水对账
python -m flask --app backend.wsgi:app inventory-reconcile
```

后续每个业务功能除单元与边界测试外，必须补充一组可重复的模拟业务数据，覆盖正常闭环、异常输入和角色协作，并独立核对页面、API、数据库余额与分析结果。写入型模拟测试只允许连接名称以 `_test` 结尾的数据库，不使用正式家庭经营数据。

健康检查：`GET /api/health`。版本化业务接口统一位于 `/api/v1`，旧 `/api/auth` 登录接口暂时保留兼容。
