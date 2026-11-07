"""客服值守(样例 #7 人机协作):应答 → 合规 → 风控定级 → 自动结案 / 升级闸门⑦。"""
import json
import os
import re
import time

from .. import config, gates, knowledge_base as kb
from ..llm import chat, log_action
from . import compliance, prompts


def handle(message: str, parent: str = "家长", auto: bool = False,
           naive_draft: str | None = None) -> dict:
    """处理一条家长消息,返回工单 dict。naive_draft 用于演示『打回重跑』。"""
    qa_hits = kb.search_qa(message)
    qa_ctx = "\n\n".join(
        f"【异议 {it['id']}】{it['question']}\n参考应答:{it['answer'][:400]}" for it in qa_hits
    ) or "(无直接匹配,按人设与红线自由应答)"

    # 1) 前台客服起草(或使用指定的初稿,用于失败重跑演示)
    if naive_draft:
        draft = naive_draft
        log_action("服务运营·起草", message, "使用指定初稿(演示用)", status="DRAFT")
    else:
        draft = chat(
            prompts.service(prompts.T_DRAFT_REPLY),
            f"家长消息:{message}\n\n知识库参考:\n{qa_ctx}\n\n{prompts.banlist_block()}",
            agent="服务运营·起草", input_summary=message, temperature=0.2,
        )

    # 2) 合规评审循环(样例 #3:不合格打回重写,≤3 轮)
    final, rounds, history = compliance.review_loop(
        draft, context=f"家长消息:{message}\n{qa_ctx}"
    )

    # 3) 风控定级(只看家长输入;应答中的退费规范解释不构成风险信号)
    level, reason = _risk_level(message)
    action = {"L1": "自动结案", "L2": "转专家坐席", "L3": "升级老板"}[level]
    status = {"L1": "已结案", "L2": "转专家待跟进", "L3": "待老板处置"}[level]

    ticket = {
        "id": f"T{time.strftime('%Y%m%d%H%M%S')}",
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "parent": parent, "message": message,
        "draft": draft, "reply": final,
        "review_rounds": rounds, "review_history": history,
        "risk_level": level, "risk_reason": reason,
        "action": action, "status": status,
    }

    # 4) 高风险 → 升级官出处置建议 → 人工闸门⑦
    if level == "L3":
        advice = chat(
            prompts.service(prompts.T_ESCALATION),
            f"家长消息:{message}\n已拟应答:{final}\n风险:{reason}",
            agent="服务运营·升级建议", input_summary=message,
        )
        ticket["escalation"] = advice
        passed = gates.gate(7, advice, auto=auto,
                            detail=f"风险:{reason}")
        ticket["gate7"] = "放行" if passed else "打回待人工处理"
        if not passed:
            ticket["status"] = "打回待人工处理"
        log_action("服务运营·升级建议", message, f"闸门7:{ticket['gate7']}", status="GATE")

    # 5) 工单归档
    os.makedirs(os.path.join(config.OUTPUT_DIR, "tickets"), exist_ok=True)
    path = os.path.join(config.OUTPUT_DIR, "tickets", ticket["id"] + ".json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(ticket, f, ensure_ascii=False, indent=2)
    log_action("工单", ticket["id"],
               f"{level}/{action} | 家长:{message[:40]} | 应答轮次:{rounds}", status="OK")
    return ticket


def resolve(ticket_id: str, decision: str, auto: bool = False) -> dict:
    """老板拍板处置工单(L3 闭环):首响官生成对外回应 → 合规评审 → 写回闭环。"""
    tid = os.path.basename(ticket_id).removesuffix(".json")
    path = os.path.join(config.OUTPUT_DIR, "tickets", f"{tid}.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"工单不存在: {tid}")
    with open(path, encoding="utf-8") as f:
        ticket = json.load(f)
    if ticket.get("status") == "已闭环":
        log_action("老板拍板", tid, "工单已闭环,忽略重复处置", status="WARN")
        return ticket

    # 1) 首响官:按老板拍板生成对外回应
    draft = chat(
        prompts.service(prompts.T_FIRST_RESPONSE),
        f"家长消息:{ticket['message']}\n风险:{ticket.get('risk_reason', '')}\n"
        f"升级官处置建议:\n{ticket.get('escalation', '')[:1200]}\n\n"
        f"老板拍板:{decision}",
        agent="服务运营·首响", input_summary=f"{tid} 首响",
    )
    # 2) 对外回应必须过合规评审循环
    final, rounds, _ = compliance.review_loop(
        draft, context=f"家长消息:{ticket['message']}"
    )

    ticket.update({
        "status": "已闭环",
        "decision": decision,
        "first_response": final,
        "first_response_rounds": rounds,
        "closed_time": time.strftime("%Y-%m-%d %H:%M:%S"),
    })
    with open(path, "w", encoding="utf-8") as f:
        json.dump(ticket, f, ensure_ascii=False, indent=2)
    log_action("老板拍板", tid,
               f"{decision} | 首响合规 {rounds} 轮 | 工单闭环", status="OK")
    return ticket


def _risk_level(text: str) -> tuple:
    rules = kb.qc_rules().get("risk_keywords", {})
    for kw in rules.get("crisis", []):
        if kw in text:
            return "L3", f"命中危机关键词「{kw}」"
    for kw in rules.get("hard", []):
        if kw in text:
            return "L2", f"命中疑难关键词「{kw}」"
    return "L1", "普通咨询"
