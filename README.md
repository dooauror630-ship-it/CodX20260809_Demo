# 综合农牧业管理系统

当前 V1 面向家庭农场、小型合作社和单一经营主体，优先解决少量人员在电脑与手机上共同记清生产、库存、销售和利润的问题，不以大型集团多公司核算为当前目标。系统已完成账号与角色隔离、基础资料、采购库存闭环和库存分析。阶段 4 已具备生猪批次、存栏流水、物料领退、入栏/人工/公共费用归集、健康/防疫/用药、称重、ADG、农场趋势、死亡率、生产成本和批次对比；负责人和操作员可登记，查看员只读。系统采用 Vue 3 模块化前端、Flask 模块化单体后端、MySQL、Waitress 和 Nginx。

详细需求、架构、数据库与分阶段计划见 [V1 开发文档](docs/综合农牧业管理系统开发文档-v1.md)。

## 当前交付状态

- 当前代码目标迁移版本：`0021_sales_returns`。
- 正式数据库版本：`0011_livestock_production`；`0012` 至 `0021` 仅在隔离库验证，正式升级按约定留到其余功能完成后统一执行，日常业务账号仍仅保留业务读写权限。
- 阶段 3 状态：已完成采购入库、采购退货、仓库调拨、生产领退料、库存盘点、效期预警、库存趋势和生产净耗用排行。
- 阶段 4 状态：进行中；批次、存栏、物料领退、健康/用药、称重、ADG、批次关闭后仍可追溯的估算 FCR、直接物料成本、入栏/人工/公共费用、批次生产成本、单批次趋势、农场趋势、死亡率和最近 10 批对比已完成，并已通过完整模拟批次对账；销售结算联动仍待经营核算阶段闭环。
- 阶段 5.1 状态：已完成最小纵向切片；种植周期、地块面积校验、重叠周期占用约束、状态流转、农场权限和前端列表/创建已交付。
- 阶段 5.2 状态：农事操作切片已完成；支持整地、播种、移栽、灌溉、施肥、用药、除草和其他操作登记、查询，记录作业面积、人工/机械工时、人工/服务费用，并校验活动周期、日期和面积。
- 阶段 5.3A 状态：已完成种植周期库存成本对象接入；生产领退料支持按活动/采收中种植周期归集，校验农场、状态和业务日期，并在库存流水中可追溯。
- 阶段 5 状态：已完成；种植周期、农事操作、多投入品与成本、采收、烟草烘烤、分级、亩产/成本/等级综合分析和周期关闭门禁均已交付。
- 阶段 6 状态：已完成；肉鸡复用养殖批次完整生产链路，大蒜、水稻和油菜具备关键作业模板、周期建议和登记预填，种植分析支持最近 20 个周期按各自计量单位横向对比。
- 阶段 7 状态：已完成；已交付客户档案、库存物料销售单、销售过账出库、收款应收汇总、销售详情、销售退货、库存回补和按销售单利润分析。
- V1 核心交付总进度：约 88%；阶段 1–3、阶段 5–7 已完成，阶段 4 约 85%，阶段 8–9 尚待开发，智能体保持只读试验状态。
- 最近正式升级前备份：`backups/agriculture_management-before-0012-release-20260903-001740.sql`，SHA256 为 `B46DF3DEAAC868676179C7AC294DD2C8EBF10DBE68C766400298AC99CF46A01E`。
- 当前质量门禁：Ruff、pytest 52 项通过、1 项按配置跳过，销售专项覆盖详情、退货、幂等和超量拦截；ESLint、Vitest 4 项、Vue 类型检查和 Vite 构建通过。`0020 → 0021` 迁移已加入，正式库仍停在 `0011`，不使用当前代码启动正式服务。

## 后续优化优先级

1. 继续阶段 7，建设销售退货、活体/采收批次销售和成本分摊。
2. 完成客户、销售、收付款和经营核算，闭合“采购—生产—销售—利润”。
3. 取得真实出栏/死亡重量后，将当前估算 FCR 升级为实算口径。
4. 优化手机快速录入，并按实际使用反馈评估 PWA、微信入口或弱网能力。
5. 增加 Excel 导入导出、备份恢复、审计查询和经营周期归档。
6. 其余功能完成后使用一次性 DDL 账号统一升级正式库，并完成结构检查、对账和发布回归。

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
