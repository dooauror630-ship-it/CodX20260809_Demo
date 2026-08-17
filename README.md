# 综合农牧业管理系统

当前 V1 已完成账号与角色隔离、农场和成员权限、圈舍、地块、仓库、业务字典、物料档案、当前农场切换，以及基于真实账号数据的 ECharts 管理看板。阶段 3 已交付完整采购库存闭环和库存分析。阶段 4 已交付首个生猪基础闭环，包括批次入栏、转舍、死亡、淘汰、出栏、圈舍分布、当前存栏、自动结批和五类追加式流水；负责人和操作员可登记，查看员只读。农场业务查询在服务端按成员关系隔离，普通用户只能访问所属农场。系统采用 Vue 3 模块化前端、Flask 模块化单体后端、MySQL、Waitress 和 Nginx。

详细需求、架构、数据库与分阶段计划见 [V1 开发文档](docs/综合农牧业管理系统开发文档-v1.md)。

## 当前交付状态

- 正式 MySQL 迁移版本：`0010_livestock`。
- 阶段 3 状态：已完成采购入库、采购退货、仓库调拨、生产领退料、库存盘点、效期预警、库存趋势和生产净耗用排行。
- 阶段 4 状态：进行中；生猪批次与存栏流水基础闭环完成，饲喂、健康、称重、成本和养殖分析待开发。
- 最近发布前备份：`backups/agriculture_management-before-livestock-20260816-152746.sql`，SHA256 为 `C22613AB465762C2F467B0CA3CD2E25D2FF26BBFEAF01ECF20C8A0E861999832`。
- 当前质量门禁：Ruff、pytest 27 项、MySQL 集成 1 项、ESLint、Vitest 4 项、Vue 类型检查、Vite 构建、桌面与移动 Playwright 6 项、测试库与正式库库存余额对账均通过。

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
