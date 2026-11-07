# 伴学管家 OPC · 一人公司 × 双 Agent 团队

JUNCTION CHINA 2026「OPC · 一人公司」赛题作品。一个人类经营者借助两个业务 Agent，管理儿童阅读训练营的客服、数据、增长、内容和质检。现有知识库包含群聊素材、逐日 SOP、异议应答和质检规则；使用真实语料前需核查隐私和访问权限。

## 启动本地控制台

在 `junction` 目录安装 Python 依赖，确保本机 Magpie 已配置 SophNet，然后启动：

```bash
cd junction
pip install -r requirements.txt
python -m web_api.main
```

打开 <http://127.0.0.1:8765/>。前端为免构建静态页（`web/`：index.html / app.js / style.css / assets），由 Python 服务直接托管，无需 npm。控制台提供工单、运营包、审批、经营分析和双 Agent 跟进演示。服务只监听本机，是单机演示工具，没有登录或远程访问控制；不要直接暴露到公网。模型调用失败、截断或输出为空时进入待复核，不会伪造成功。

默认使用 `http://127.0.0.1:3425/v1/responses` 和 `sophnet/DeepSeek-V4.1-Flash-1017`。可通过 `OPC_MAGPIE_BASE_URL`、`OPC_MAGPIE_TOKEN`、`OPC_MAGPIE_ACTOR_TOKEN` 和 `OPC_MODEL` 覆盖配置；不要将真实密钥写入仓库。需要 MiMo 时设置 `OPC_LLM_PROVIDER=mimo`、`ANTHROPIC_BASE_URL` 和 `ANTHROPIC_AUTH_TOKEN`，可选设置 `OPC_MODEL`。

原命令行入口仍可使用：

```bash
python run.py ingest                 # 导入素材
python run.py service "我要退款"      # 客服工单和风险升级
python run.py sop --day D4           # 按 SOP 条目生成并审核
python run.py report                 # 近七日结构化工单周报
python run.py demo                   # 示例流程
```

审批默认需要明确决定；`--simulate-approval` 只记录模拟批准，不构成真实授权。`ingest` 的素材路径可通过 `OPC_MATERIAL_DIR` 配置。详见 [工作流说明](WORKFLOW.md) 和 [网页接口说明](web_api/README.md)。

## 两个 Agent 如何协作

| 岗位 | 职责与当前实现 |
|---|---|
| 服务运营 Agent | 合并原客服、内容运营和质检：检索知识、起草回复、生成运营内容、独立审核和创建工单；疑难及高风险问题进入人工待办 |
| 数据增长 Agent | 合并原数据分析与增长：确定性计算用户分层及依据，根据互动、同意和触达频次生成跟进任务 |

COO 是受约束的 Python 编排器，负责固定流程、任务与状态。增长演示按「数据增长 Agent 分层与规划 → 服务运营 Agent 生成 → 独立合规审核 → 老板批准正文和名单 → 服务运营 Agent 创建本地草稿 → 模拟回执 → 数据反馈」执行。角色合并后，审核仍是单独调用和强制前置步骤，并非生成后自动通过；老板仍负责人工决策。历史记录保留原角色名，不改写旧审计数据。入站消息和 SOP 也能登记共享运行记录；人工确认的客户阶段变更有单独留痕。

`output/workflow.sqlite3` 保存客户、事件、跟进任务、产物、审批、草稿、运行记录及轨迹。示例客户和行为是**模拟数据**，不是实际阅读或服务成果；三天未互动不代表流失，跟进前后变化也不能直接归因于系统。客服工单与 SOP 内容仍保存在本地文件中，其运行结果和轨迹可登记在共享状态里。

## 审核与边界

审核失败、服务异常或模型输出截断均不能视为通过。SOP 按条目生成和审核，缺项时运营包不能进入发布审批。审批绑定内容版本；增长批次还绑定完整名单，触达条件变化会阻止草稿或模拟回执。模拟批准不能当作真实批准。

工单、运营包和草稿是本地记录；系统不向真实家长发送消息，也不执行退款。当前没有正式 CRM、授权消息渠道、自动定时、真实转化漏斗或对照实验。九类人工闸门中现有流程主要接入第 4 类发布与第 7 类投诉/退款；父目录的 `claw-ctx` 尚未接入本业务运行时。历史产物可能采用旧版逻辑，不能作为当前审批凭证。

周报由近七日结构化工单计算，缺少审核记录的旧工单不纳入审核率分母。控制台其他统计以页面标明的本地记录和口径为准。

## 主要目录

```text
run.py                 原有命令行入口
opc/workflow.py        共享状态与双 Agent 受控编排
opc/agents/            客服、内容、质检与周报
opc/knowledge_base.py  知识检索
opc/gates.py           人工审批闸门
web/                   控制台前端（免构建静态页：index.html/app.js/style.css/assets）
web_api/               本地网页服务与接口
knowledge/             SOP、QA、质检规则和群聊素材
hub/                   业务卷宗和周报
output/                本地工单、运营包和工作流数据库
tests/                 业务和安全测试
```

在 `junction` 目录运行 `python -m unittest discover -s tests -v` 验证 Python 流程。
