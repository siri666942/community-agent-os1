"""用户画像:两条硬规则 + 一条组合规则(OPSIE 5.1),确定性计算、依据可解释。

活跃度:近 7 日活跃 ≥5 天 且 日均阅读 ≥15 分钟 → 高;满足其一 → 中;均不满足 → 低
意向度:近 3 日推进信号(问价/问班型/约试听/要资料/问师资)任意两项 → 高;一项 → 中
分层:高活跃+高意向 → S1;只满足其一 → S2;无有效互动 → S3

数据来源:Excel 行为数据(逐日阅读列 = 近 7 日活跃)+ 对话意图(随会话传入)。
意向信号在只有行为数据时按「置信度下降」如实标注(OPSIE 十二)。
"""
from __future__ import annotations

from . import config

# 推进信号关键词(近 3 日对话意图识别,命中即记一项)
INTENT_SIGNALS = {
    "问价": ["多少钱", "价格", "费用", "收费", "优惠", "便宜", "学费", "报价", "钱"],
    "问班型": ["班型", "课时", "大班", "小班", "一对一", "上课时间", "一周几", "几节课"],
    "约试听": ["试听", "试课", "体验课", "免费测评", "约测评", "试一试", "先试试"],
    "要资料": ["资料", "清单", "发我", "发一份", "学习计划", "学情", "测评报告"],
    "问师资": ["老师背景", "师资", "哪个老师", "老师资历", "名师", "外教", "老师经验"],
}


def detect_intents(messages: list[str]) -> dict:
    """从近 3 日对话文本提取推进信号,返回 {信号名: [命中句]}。"""
    hits: dict[str, list[str]] = {}
    for msg in messages:
        for name, kws in INTENT_SIGNALS.items():
            if any(k in msg for k in kws):
                hits.setdefault(name, []).append(msg)
    return hits


def activity_score(daily: list[list], avg_fallback: float = 0.0) -> dict:
    """活跃度:daily = 近 7 日 [[是否阅读 0/1, 时长分钟], ...]。

    口径说明:Excel 导出的逐日「阅读时长」列全为 0(仅「是否阅读」有效),
    日均时长改用「平均阅读时长」列兜底(avg_fallback),阈值判定不受影响。
    """
    active_days = sum(1 for d in daily if d and d[0])
    total_minutes = sum((d[1] or 0) for d in daily if d)
    avg_minutes = total_minutes / 7 if daily else 0.0
    if avg_minutes <= 0 < active_days and avg_fallback > 0:
        avg_minutes = avg_fallback  # 逐日时长缺失,以平均阅读时长列为准
    day_ok = active_days >= config.ACTIVITY_DAYS_THRESHOLD
    min_ok = avg_minutes >= config.ACTIVITY_MINUTES_THRESHOLD
    if day_ok and min_ok:
        level = "高"
    elif day_ok or min_ok:
        level = "中"
    else:
        level = "低"
    return {
        "level": level, "active_days": active_days,
        "avg_minutes": round(avg_minutes, 1),
        "evidence": f"近7日活跃 {active_days} 天 / 日均阅读 {avg_minutes:.1f} 分钟"
                    f"(阈值 ≥{config.ACTIVITY_DAYS_THRESHOLD} 天 且 ≥{config.ACTIVITY_MINUTES_THRESHOLD} 分钟)",
    }


def intent_level(intent_hits: dict) -> dict:
    """意向度:推进信号项数 → 高/中/低。"""
    n = len(intent_hits)
    if n >= config.INTENT_SIGNALS_HIGH:
        level = "高"
    elif n == 1:
        level = "中"
    else:
        level = "低"
    return {
        "level": level, "signals": list(intent_hits.keys()),
        "evidence": f"近3日推进信号 {n} 项:{'、'.join(intent_hits) or '无'}",
        "confidence": "high" if intent_hits else "low",  # 无对话数据时置信度下降
    }


def behavior_intents(customer: dict) -> dict:
    """无对话数据时,用行为数据作意向代理信号(置信度低,如实标注)。"""
    hits: dict[str, list[str]] = {}
    if (customer.get("link_clicks") or 0) > 0:
        hits["价格关注(链接点击)"] = ["会员链接点击"]
    tags = customer.get("tag_list") or []
    if any("意向" in t or "挖需" in t for t in tags):
        hits["已标记意向(标签)"] = tags
    if customer.get("tested") == "已测字":
        hits["测评参与(测字)"] = ["已测字"]
    return hits


def segment(activity: str, intent: str, has_interaction: bool = True) -> dict:
    """分层建议:S1 高价值推进 / S2 培育观察 / S3 低压力激活。"""
    if activity == "高" and intent == "高":
        tier = "S1"
    elif not has_interaction or (activity == "低" and intent == "低"):
        tier = "S3"
    else:
        tier = "S2"
    names = {"S1": "S1 高价值推进", "S2": "S2 培育观察", "S3": "S3 低压力激活"}
    return {"tier": tier, "name": names[tier]}


def build_profile(customer: dict, recent_messages: list[str] | None = None) -> dict:
    """画像卡五块内容(OPSIE 5.2)。customer 来自 Repository。"""
    daily_all = customer.get("daily", [])
    # 「近 7 日」取逐日列的最后 7 天(第十五天~第二十一天)
    recent7 = daily_all[-7:] if len(daily_all) >= 7 else daily_all
    act = activity_score(recent7, avg_fallback=float(customer.get("avg_read_minutes") or 0))
    hits = detect_intents(recent_messages or [])
    behavior = not hits
    if behavior:
        hits = behavior_intents(customer)  # 无对话数据 → 行为代理信号
    itn = intent_level(hits)
    if behavior:
        itn["confidence"] = "low"  # 行为代理,置信度下降(无对话意图数据)
    has_interaction = bool(recent_messages) or act["active_days"] > 0
    seg = segment(act["level"], itn["level"], has_interaction)

    # 行为概括:三句话,不堆指标
    nickname = customer.get("child_nickname") or "宝宝"
    signup = customer.get("signup") or "无"
    summary = (
        f"近 7 日活跃 {act['active_days']} 天，日均阅读 {act['avg_minutes']} 分钟；"
        f"宝宝「{nickname}」当前报名状态：{signup}；"
        f"最近关键动作：{('、'.join(itn['signals']) + ' 相关咨询') if itn['signals'] else '暂无推进信号'}。"
    )
    return {
        "uid": customer.get("uid"),
        "nickname": nickname,
        "activity": act,
        "intent": itn,
        "segment": seg,
        "summary": summary,
        "tags_ai": [
            f"{act['level']}活跃度用户（{act['evidence']}）",
            f"{itn['level']}意向" + (f"（{itn['evidence']}）" if itn["signals"] else ""),
        ],
        "tags_manual": customer.get("tag_list", []),
        "tier": seg["tier"],
    }
