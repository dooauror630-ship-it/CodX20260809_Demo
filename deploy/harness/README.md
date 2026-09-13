# Harness 农业工具集成

当前阶段启用六个只读工具、三个受控草稿工具和三个受控确认工具：当前用户、可访问农场、采购基础选项、管理员用户列表、库存概览、养殖概览，以及采购入库、库存盘点、仓库调拨草稿和对应的确认过账。Harness 不连接数据库，草稿只创建 DRAFT 业务单据；正式过账必须提交后端签发的短时确认挑战，后端仍二次校验用户角色、农场范围、库存快照和单据版本。

生产集成使用 gateway/index.ts：它为每个项目登录用户启动一个独立 Harness runtime。网关会把后端返回的当前用户、角色和可访问农场作为可信上下文注入每轮对话；Harness 只收到网关作用域的随机工具凭证，网关在进程外保存后端短时用户令牌，并把工具请求限制为登记的只读、草稿和确认路径；后端仍会重新校验用户权限。删除、批量写入和无人值守自动过账仍保持关闭。

从 Harness 仓库根目录启动网关（需要 Node 22+ 和 `tsx`）：

```powershell
$env:AGRI_HARNESS_ROOT = 'G:/deepseek-harness-master/deepseek-harness-master'
$env:AGRI_HARNESS_WORKSPACE = 'G:/deepseek-harness-master/deepseek-harness-master'
$env:AGRI_HARNESS_PATCH = 'D:/zongheguanlixitong/deploy/harness/cordis.patch.yml'
$env:AGRI_BACKEND_BASE_URL = 'http://127.0.0.1:5000'
pnpm exec tsx 'D:/zongheguanlixitong/deploy/harness/gateway/index.ts'
```

网关默认只监听 `127.0.0.1:15100`，前端开发服务器已代理 `/agent-gateway`。生产环境应让 Nginx 反向代理同一路径，不要把网关直接暴露到公网。

在 Harness 仓库根目录启动 Web UI 前设置临时测试配置：

```powershell
$env:AGRI_HARNESS_PLUGIN_PATH = 'G:/deepseek-harness-master/deepseek-harness-master/packages/extensions/agri-agent-tools/src/index.ts'
$env:AGRI_AGENT_BASE_URL = 'http://127.0.0.1:15000'
$env:AGRI_AGENT_API_KEY = '<测试环境 API Key>'
pnpm dsh web --patch 'D:/zongheguanlixitong/deploy/harness/cordis.patch.yml'
```

不要将 API Key 写入仓库或生产命令历史。确认工具只接受草稿响应中的短时签名挑战，不能仅凭自然语言“确认”触发；删除、批量写入、结算和无人值守自动过账仍不会启用。
