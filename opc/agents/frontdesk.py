"""客服值守(样例 #7 人机协作):应答 → 合规 → 风控定级 → 自动结案 / 升级闸门⑦。"""
import json
import os
import re
import time
import uuid

from .. import config, gates, knowledge_base as kb
from ..llm import chat, log_action
from . import compliance, prompts


def handle(message: str, parent: str = "家长", auto: bool = False,
           naive_draft: str | None = None, workflow_run_id: str | None = None) -> dict:
    """处理一条家长消息,返回工单 dict。naive_draft 用于演示『打回重跑』。"""
    qa_hits = kb.search_qa(message)
    qa_ctx = "\n\n".join(
        f"【异议 {it['id']}】{it['question']}\n参考应答:{it['answer'][:400]}" for it in qa_hits
    ) or "(无直接匹配,按人设与红线自由应答)"

    # 风险只根据家长原始消息判断，不能被生成回复中的措辞改变。
    level, reason = _risk_level(message)

    # 1) 前台客服起草(或使用指定的初稿,用于失败重跑演示)
    draft = ''
    try:
        if naive_draft:
            draft = naive_draft
            log_action(prompts.SERVICE_AGENT, message, "使用指定初稿(演示用)", status="DRAFT")
        else:
            draft = chat(
                prompts.FRONTDESK,
                f"家长消息:{message}\n\n知识库参考:\n{qa_ctx}",
                agent=prompts.SERVICE_AGENT, input_summary=message,
            )
        # 审核失败及生成异常均须留工单供人处理。
        review = compliance.review_loop(draft, context=f"家长消息:{message}\n{qa_ctx}")
    except Exception as exc:
        review = {"content": draft, "status": "REVIEW_REQUIRED", "review_rounds": 0,
                  "history": [], "violations": [], "reviewed_content_hash": None,
                  "reason": f"生成或审核异常: {exc}"}
    final, rounds, history = review["content"], review["review_rounds"], review["history"]

    # 3) 风控定级
    action = {"L1": "待发送草稿", "L2": "等待专家处理", "L3": "升级老板"}[level]
    if review["status"] != "PASS":
        action = "待人工复核，禁止交付"

    ticket = {
        "id": f"T{time.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}",
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "parent": parent, "message": message,
        "knowledge_sources": [{"id": item.get("id"), "question": item.get("question")} for item in qa_hits],
        "draft": draft, "reply": final if review["status"] == "PASS" else "",
        "review_candidate": final, "review": review,
        "review_rounds": rounds, "review_history": history,
        "risk_level": level, "risk_reason": reason, "action": action,
        "delivery_status": "NOT_SENT", "customer_state": "未更新（缺少授权的客户档案）",
    }
    if workflow_run_id:
        ticket['workflow_run_id'] = workflow_run_id

    if level in ("L2", "L3") or review["status"] != "PASS":
        reasons = ([reason] if level in ("L2", "L3") else [])
        if review["status"] != "PASS":
            reasons.append(f"审核未通过：{review.get('reason', '需人工复核')}")
        ticket["human_task"] = {"id": f"H{uuid.uuid4().hex[:12]}",
                                "status": "PENDING", "owner": "老板" if level == "L3" else "专家" if level == "L2" else "质检人员",
                                "reason": '；'.join(reasons)}
        # 高风险和疑难工单均不直接提供可交付回复。
        ticket["reply"] = ""

    # 4) 高风险 → 升级官出处置建议 → 人工闸门⑦
    if level == "L3":
        try:
            advice = chat(
                prompts.ESCALATION,
                f"家长消息:{message}\n已拟应答:{final}\n风险:{reason}",
                agent=prompts.SERVICE_AGENT, input_summary=message,
            )
            ticket["escalation"] = advice
            approval_materials = json.dumps({"reply": final, "advice": advice}, ensure_ascii=False, sort_keys=True)
            decision = gates.gate(7, approval_materials, auto=auto, detail=f"风险:{reason}")
            ticket["gate7"] = decision["status"]
            ticket["gate7_decision"] = decision
        except Exception as exc:
            ticket['gate7'] = 'REVIEW_REQUIRED'
            ticket['gate7_decision'] = {'status': 'REVIEW_REQUIRED', 'content_hash': None}
            ticket['human_task']['reason'] += f'；升级建议或审批异常：{exc}'
            ticket["reply"] = ""
            ticket["action"] = "待人工处理，禁止交付"
        if ticket['gate7'] != 'APPROVED':
            ticket['reply'] = ''
            ticket['action'] = '待人工处理，禁止交付'
        log_action(prompts.SERVICE_AGENT, message, f"闸门7:{ticket['gate7']}", status="GATE")

    # 5) 工单归档
    os.makedirs(os.path.join(config.OUTPUT_DIR, "tickets"), exist_ok=True)
    path = os.path.join(config.OUTPUT_DIR, "tickets", ticket["id"] + ".json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(ticket, f, ensure_ascii=False, indent=2)
    log_action("工单", ticket["id"],
               f"{level}/{ticket['action']} | 家长:{message[:40]} | 应答轮次:{rounds}", status="OK")
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
