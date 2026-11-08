"""运营助手 Agent(OPSIE 2.1):读 SOP 与画像 → 出三个备选 → 标风险;
老师发送后写摘要、登记记忆。在线逐条触发,只出稿不发送。

备选三定位:A 标准口径(事实零风险)/ B 推进型(明确下一步)/ C 关系型(先解顾虑)。
LLM 不可用或关闭时降级为确定性模板稿,保证链路可测试、可演示。
"""
from __future__ import annotations

import uuid

from . import config, profile as profile_mod, qc, sop

# ── 确定性模板(降级路径;LLM 开启时走 MiMo 生成) ──────────────────
TEMPLATES = {
    "A": ("标准口径",
          "{name}您好，关于您问的{topic}，我按官方口径给您说明一下：{facts}。"
          "具体以我们的价目表与课程服务协议为准，有任何不清楚的随时问我。"),
    "B": ("推进型",
          "{name}您好，{topic}的情况我给您梳理好了：{facts}。"
          "建议咱们下一步就约一次免费测评，看看孩子当前水平，我把可选时间发您挑一个？"),
    "C": ("关系型",
          "{name}您好，特别理解您的顾虑。{topic}确实需要多了解一些再决定，"
          "我把相关的资料先发您看看，不着急定，有任何疑问随时找我聊。"),
}

FACTS_BY_SIGNAL = {
    "问价": "阅读会员按年规划，含 App 阅读识字、伴学老师陪伴与每日任务提醒，价格分档以价目表为准",
    "问班型": "我们有不同阅读节奏的班型，按孩子识字水平动态推荐绘本，课时安排可弹性调整",
    "约试听": "可以先做 15 分钟免费测评，先看孩子识字水平和兴趣，再决定是否安排试听",
    "要资料": "我可以发您学情资料清单和阶段学习建议，方便您整体了解",
    "问师资": "老师资质以官方师资介绍为准，伴学老师会跟进孩子的每日阅读情况",
}
DEFAULT_TOPIC = "阅读会员"
DEFAULT_FACTS = "App 会先测识字量再动态推荐绘本，每天 15-20 分钟，伴学老师全程跟进"

# 信号名 → 自然话题名(避免「您问的问价」这类生硬拼接)
TOPIC_NAMES = {
    "问价": "价格", "问班型": "班型安排", "约试听": "试听",
    "要资料": "学习资料", "问师资": "老师资质",
}


def _topic_and_facts(message: str) -> tuple[str, str]:
    # 敏感话题优先贴题回应(退费规范 / 效果口径),不绕开家长的问题
    if any(k in message for k in ("退", "退款", "退费")):
        return "退费", ("退费以您签署的课程服务协议为准，我先把正式退费规则发给您确认，"
                        "不同订单情况会不一样，我按您的订单逐项核对")
    if any(k in message for k in ("保证", "效果", "提高", "提分", "识字量")):
        return "效果", ("内容按孩子识字水平动态推荐、逐步积累，效果因人而异、需要时间，"
                        "我们不做幅度与见效时间的承诺")
    for signal, kws in profile_mod.INTENT_SIGNALS.items():
        if any(k in message for k in kws):
            return TOPIC_NAMES[signal], FACTS_BY_SIGNAL[signal]
    return DEFAULT_TOPIC, DEFAULT_FACTS


def _template_drafts(name: str, message: str) -> list[dict]:
    topic, facts = _topic_and_facts(message)
    out = []
    for variant in ("A", "B", "C"):
        position, tpl = TEMPLATES[variant]
        out.append({
            "variant": variant, "position": position,
            "text": tpl.format(name=name, topic=topic, facts=facts),
        })
    return out


def _llm_drafts(name: str, message: str, profile_summary: str) -> list[dict] | None:
    """MiMo 生成三备选(失败返回 None 走模板)。"""
    if not config.LLM_ENABLED:
        return None
    try:
        from opc import llm  # noqa: PLC0415
        from opc.agents import prompts  # noqa: PLC0415
        task = prompts.T_DRAFT_REPLY + (
            f"\n附加任务:同一场景输出**三条**定位不同的备选,严格按 JSON 数组输出:"
            f'[{{"variant":"A","position":"标准口径","text":"…"}},'
            f'{{"variant":"B","position":"推进型","text":"…"}},'
            f'{{"variant":"C","position":"关系型","text":"…"}}]'
            f"\n家长称呼:{name};画像:{profile_summary}"
        )
        raw = llm.chat(prompts.service(task), f"家长消息:{message}",
                       max_tokens=1200, temperature=0.4,
                       agent="运营助手", input_summary="三备选出稿")
        import json  # noqa: PLC0415
        data = json.loads(raw[raw.index("["):raw.rindex("]") + 1])
        if isinstance(data, list) and len(data) >= 3:
            return [{"variant": d.get("variant", "ABC"[i]),
                     "position": d.get("position", ""),
                     "text": d["text"]} for i, d in enumerate(data[:3])]
    except Exception:  # noqa: BLE001 降级不阻塞
        return None
    return None


def draft_three(customer: dict, parent_message: str,
                recent_messages: list[str] | None = None) -> dict:
    """出三个备选并逐条质检。返回 drafts + 客户快照 + SOP 状态。"""
    msgs = list(recent_messages or []) + [parent_message]  # 当前消息计入意向信号
    prof = profile_mod.build_profile(customer, msgs)
    name = (customer.get("parent_role") or "妈妈")
    if name not in ("妈妈", "爸爸"):
        name = "妈妈"
    name = (customer.get("child_nickname") or "xx") + name

    drafts = _llm_drafts(name, parent_message, prof["summary"]) \
        or _template_drafts(name, parent_message)
    for d in drafts:
        d["id"] = "DR" + uuid.uuid4().hex[:10]
        d["qc"] = qc.check(d["text"])

    state = sop.advance_on_message("price", parent_message)  # 默认阶段由会话携带
    return {
        "drafts": drafts,
        "customer_snapshot": {
            "uid": customer.get("uid"), "nickname": prof["nickname"],
            "tier": prof["tier"], "summary": prof["summary"],
            "activity": prof["activity"]["level"], "intent": prof["intent"]["level"],
        },
        "sop_hint": state,
    }


def send_gate(draft_text: str, variant: str, confirmed: bool,
              sender: str, edited: bool = False) -> dict:
    """人工发送闸门:记录选用备选/是否改写/质检状态(全程留痕)。"""
    result = qc.check(draft_text)
    sendable = qc.is_sendable(result["status"], confirmed)
    return {
        "message_id": "MSG" + uuid.uuid4().hex[:10],
        "variant": variant, "edited": edited, "confirmed": confirmed,
        "sender": sender, "qc_status": result["status"],
        "qc_risks": result["risks"], "sendable": sendable,
    }
