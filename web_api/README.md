# OPC Mission Control 本地服务

先在 `junction/web` 执行 `npm install && npm run build`，再到 `junction` 目录运行 `python -m web_api.main`，打开 <http://127.0.0.1:8765/>。开发时可使用 `npm run dev` 从 <http://127.0.0.1:5173/> 访问 React 工作台，Vite 自动代理 `/api`。服务使用 Python 标准库，默认连接本机 Magpie 中的 SophNet，模型和可选 MiMo 配置见 `junction/README.md`。没有模型连接时，模型任务会返回错误或待复核，不会伪造成功。

服务只监听本机；客服、运营包和增长任务在独立进程运行，进度通过 `/api/jobs/{id}` 查询。进程内任务列表在服务重启后清空，业务产物和增长流程状态仍保存在 `output`。审批会校验所展示的材料哈希及审核状态；批准只更新本地产物，不会向家长发送消息或执行退款。增长示例数据及送达回执均明确标为模拟。

审批与人工处理的文件写入有持久化恢复记录；服务重启或下一次读取时会重放尚未完成的写入。网页发起的运行在超时或服务重启后标记为中断，需重新发起；命令行任务不受此恢复机制影响。

中断后迟到或无法与运行记录核对的工单和运营包保留为隔离记录，不进入常规审批或统计。控制台可从原消息或营期日重新运行；隔离文件保留以便排查。

接口包括 `GET /api/state`、`GET /api/workflow`、`POST /api/service`、`POST /api/sop`、`POST /api/report`、`POST /api/approvals` 和 `/api/workflow/{seed,plan,content,approve,queue,receipt}`。后者及生成任务返回任务编号，轮询任务结果。该服务是单机演示工具，不提供用户登录或远程部署的访问控制。按当前配置，任意网页来源都可以访问本机接口；只在信任的浏览环境中使用。


## 前端资源服务

Python 本地服务只提供 `web/dist/` 中的 React 构建产物（`index.html` 与 `assets/`），不执行 JSX 转译。若尚未构建，首页会返回 503 及构建说明。开发时启动 Vite 即可获得热更新。不要直接暴露 Python 本地 HTTP 服务到公网。
