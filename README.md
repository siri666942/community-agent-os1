# 伴学管家 OPC · 一人公司 × MiMo Agent 团队

> JUNCTION CHINA 2026 人工智能赛道(Xiaomi MiMo)——「OPC · 一人公司」赛题作品
> 人类老板 1 人 + MiMo Agent 团队,运营一家 **AI 社群代运营公司**,首个客户:适趣AI中文。

## 一句话

真实素材(3 个家长群 1700+ 条消息 + 逐日 SOP + 异议手册 + 质检细则)进,
**合规的每日运营包、家长应答工单、升级处置建议、家长分层跟进、成交交付、经营周报**出,
中间是双 Agent 编制 + COO 编排 + 9 道人工闸门 + 全量留痕。

## 双 Agent 编制

| Agent | 职责(任务模式) | 对应闸门 |
|---|---|---|
| **服务运营 Agent** | 检索知识起草应答、独立合规审核(否决权,失败不放行)、话术修复、运营内容生成、风险分流(L1/L2/L3,疑难高风险进人工待办)、升级建议、首响回应 | ④ 对外发布 ⑦ 投诉/退款 |
| **数据增长 Agent** | 家长分层与跟进任务(互动/触达/同意确定性计算)、报价、合同、模拟收款、交付调度、经营周报 | ⑤ 价格条款 ⑥ 资金动作 ⑧ 周报决策 |

## 运行

```bash
pip install -r requirements.txt
export ANTHROPIC_BASE_URL=...      # MiMo API(Anthropic 兼容端点)
export ANTHROPIC_AUTH_TOKEN=...

python3 run.py ingest              # ① 素材 → Context Hub + 知识库
python3 run.py demo                # ② 完整演示(闭环,含成交)
python3 run.py service "我要退款"   # 客服值守:应答→合规→风控→闸门⑦
python3 run.py resolve T<id> --decision "处置决定"  # 老板拍板,L3 工单闭环
python3 run.py sop --day D4        # 当日运营包:SOP→生成→合规→闸门④
python3 run.py deal                # 第一单成交:报价→闸门⑤→合同→收款→闸门⑥→交付→入账
python3 run.py report              # 一页纸经营周报
# 加 --no-auto 让闸门由老板手动拍板(演示现场推荐)
```

## 编排设计(对应官方样例)

| 样例 | 本项目落点 |
|---|---|
| #1 串行流水线 | SOP 检索 → 话术生成 → 合规 → 闸门④ → 运营包交付 |
| #3 评审循环 | 合规质检官(确定性词表 + MiMo 二审)打回重写,≤3 轮 |
| #7 人机协作 | 风控 L1/L2/L3 定级;退款/投诉/法律升级闸门⑦,老板拍板 |
| #8 跨系统操盘 | 动作日志 + 工单 + 运营包 → 秘书 Agent 一页纸周报 |

底座采用《MiMo-OPC 全流程蓝图》:Context Hub(公司大脑 `hub/00-08`)、
COO 编排、9 道人工闸门(`opc/gates.py`)、全量留痕(`logs/07-log.md`)、安全基线。

## 目录

```
run.py                 CLI 入口
opc/
  ingest.py            素材摄取(xlsx/docx → 知识库 + Hub)
  knowledge_base.py    检索(Context Hub 检索面)
  llm.py               MiMo API 封装 + 留痕
  gates.py             人工闸门 ①–⑨
  agents/
    prompts.py         双 Agent 角色卡(任务模式)+ 红线清单
    compliance.py      独立合规审核(评审循环)
    frontdesk.py       家长应答 + 风险分流 + 工单闭环
    sop_pipeline.py    日度运营内容流水线
    deal.py            第一单成交链路
    growth.py          家长分层与跟进任务(确定性计算)
    report.py          经营周报
  demo.py              完整演示脚本(7 案例,双 Agent 协作)
knowledge/             知识库:SOP / QA / 质检细则 / 群聊语料
hub/                   Context Hub 卷宗 00-charter … 08-review
logs/07-log.md         全量动作日志
output/                交付物:工单 / 运营包
```

## 演示亮点(30 秒)

「一条家长异议进去,合规应答和工单出来;一单退款投诉进去,升级建议弹到老板面前拍板,
首响回应合规后工单闭环;一个营期日进去,当天三线运营包出来;一份报价进去,
合同、模拟收款、交付回执和财务入账出来——全程留痕,违规自动打回重跑。」
