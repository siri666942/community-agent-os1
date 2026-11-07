"""成交与交付(全蓝图阶段 4 · 「第一单」最短路径)。

报价官 → 闸门⑤(价格条款)→ 合同法务 → 收银员(模拟收款)→ 闸门⑥(资金动作)
→ 交付调度 → 订单入账(hub/06-finance.md)
"""
import json
import os
import time

from .. import config, gates
from ..llm import chat, log_action
from . import compliance, prompts


def first_order(customer: str = "适趣AI中文", auto: bool = False,
                package: str = "社群代运营服务包 · 标准版") -> dict:
    date = time.strftime("%Y%m%d")
    finance = os.path.join(config.HUB_DIR, "06-finance.md")
    seq = 1
    if os.path.exists(finance):
        with open(finance, encoding="utf-8") as f:
            seq = f.read().count(f"ORD{date}-") + 1
    order_id = f"ORD{date}-{seq:03d}"
    outdir = os.path.join(config.OUTPUT_DIR, "first_order")
    os.makedirs(outdir, exist_ok=True)
    result = {"order_id": order_id, "customer": customer, "package": package}

    # 1) 报价官:报价单 + 单位经济
    quote = chat(
        prompts.growth(prompts.T_QUOTE),
        f"客户:{customer}\n服务包:{package}\n"
        "交付物:每日运营包(群/私聊/朋友圈)、家长应答工单、质检报告、每周经营周报;覆盖 3 个训练营群。\n"
        "要求:按月服务费报价,给出单位经济(token 成本+人工闸门时间)测算。\n\n"
        + prompts.banlist_block(),
        agent="数据增长·报价", input_summary=f"{customer} {package}",
    )
    # 报价单也要过合规(不得绝对化承诺)
    quote, qr, _ = compliance.review_loop(quote, context="报价单,注意不过度承诺服务效果")
    result["quote_rounds"] = qr
    with open(os.path.join(outdir, "01-报价单.md"), "w", encoding="utf-8") as f:
        f.write(f"# 报价单 · {order_id}\n\n{quote}\n")

    # 2) 闸门⑤:价格与条款
    if not gates.gate(5, quote, auto=auto, detail=f"{customer} {package} 报价与条款"):
        result["status"] = "闸门⑤打回,待修订报价"
        log_action("订单员", order_id, result["status"], status="GATE")
        return result

    # 3) 合同法务:协议要点
    legal = chat(
        prompts.growth(prompts.T_LEGAL), f"报价单:\n{quote}",
        agent="数据增长·合同", input_summary=f"{order_id} 协议要点",
    )
    with open(os.path.join(outdir, "02-服务协议要点.md"), "w", encoding="utf-8") as f:
        f.write(f"# 服务协议要点 · {order_id}\n\n{legal}\n")

    # 4) 收银员:模拟收款凭证
    receipt = chat(
        prompts.growth(prompts.T_CASHIER),
        f"订单号:{order_id}\n付款方:{customer}\n报价单:\n{quote[:800]}",
        agent="数据增长·收款", input_summary=f"{order_id} 模拟收款",
    )
    with open(os.path.join(outdir, "03-收款凭证.md"), "w", encoding="utf-8") as f:
        f.write(f"# 收款凭证(模拟) · {order_id}\n\n{receipt}\n")

    # 5) 闸门⑥:资金动作
    if not gates.gate(6, receipt, auto=auto, detail="模拟收款,资金动作须老板执行/确认"):
        result["status"] = "闸门⑥打回,待老板执行收款"
        log_action("订单员", order_id, result["status"], status="GATE")
        return result

    # 6) 交付调度:核对交付物,出回执
    checklist = _collect_deliverables()
    delivery = chat(
        prompts.growth(prompts.T_DELIVERY),
        f"订单号:{order_id}\n服务包:{package}\n已有交付物:\n{checklist}",
        agent="数据增长·交付", input_summary=f"{order_id} 交付回执",
    )
    with open(os.path.join(outdir, "04-交付回执.md"), "w", encoding="utf-8") as f:
        f.write(f"# 交付回执 · {order_id}\n\n{delivery}\n")

    # 7) 订单记录 + 入账
    order = {
        "order_id": order_id, "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "customer": customer, "package": package, "type": "模拟交易",
        "stages": {"quote": "ok", "gate5": "放行", "legal": "ok",
                   "receipt": "ok", "gate6": "放行", "delivery": "ok"},
        "files": ["01-报价单.md", "02-服务协议要点.md", "03-收款凭证.md", "04-交付回执.md"],
    }
    with open(os.path.join(outdir, "order.json"), "w", encoding="utf-8") as f:
        json.dump(order, f, ensure_ascii=False, indent=2)
    _write_finance(order, quote)

    result["status"] = "第一单闭环完成(模拟)"
    result["outdir"] = outdir
    log_action("COO", order_id, "第一单闭环:报价→闸门⑤→合同→模拟收款→闸门⑥→交付→入账",
               status="OK")
    return result


def _collect_deliverables() -> str:
    lines = []
    for sub in ("tickets", "sop_packages", "first_order"):
        d = os.path.join(config.OUTPUT_DIR, sub)
        if os.path.isdir(d):
            for fn in sorted(os.listdir(d)):
                lines.append(f"- output/{sub}/{fn}")
    hub_report = os.path.join(config.HUB_DIR, "08-review.md")
    if os.path.exists(hub_report):
        lines.append("- hub/08-review.md(经营周报)")
    return "\n".join(lines) or "(暂无,待产出)"


def _write_finance(order: dict, quote: str) -> None:
    path = os.path.join(config.HUB_DIR, "06-finance.md")
    entry = (
        f"\n## 订单入账 · {order['order_id']}\n\n"
        f"- 时间:{order['time']}\n"
        f"- 客户:{order['customer']}\n"
        f"- 服务包:{order['package']}\n"
        f"- 类型:{order['type']}\n"
        f"- 状态:首单已收(模拟),待开票\n\n"
        f"### 报价摘要\n\n{quote[:600]}\n"
    )
    header = "# 06 · 财务经营\n\n> 订单、收款、成本与毛利台账\n"
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            f.write(header + entry)
    else:
        with open(path, "a", encoding="utf-8") as f:
            f.write(entry)
