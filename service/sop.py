"""SOP 流程:标准五阶段状态机 + 超时提醒 + 人工调整留痕(OPSIE 六)。"""
from __future__ import annotations

from datetime import datetime

# 标准五阶段(顺序即推进顺序);hours = 停留上限,超时即提醒
STAGES = [
    {"key": "welcome", "name": "欢迎破冰", "goal": "新家长入群/首次私聊:确认年级、科目、当前分数段",
     "first_response_hours": 2, "stay_limit_hours": 24,
     "suggest": "确认年级与科目，发学情诊断表"},
    {"key": "need", "name": "需求识别", "goal": "家长说出年级与薄弱点:先发诊断/测评，不急报价",
     "first_response_hours": 0.2, "stay_limit_hours": 24,
     "suggest": "发学情诊断表或测评，24 小时内推进下一步"},
    {"key": "price", "name": "课程与价格", "goal": "问班型、课时、师资:按价目表分档说明，不承诺提分",
     "first_response_hours": 0.1, "stay_limit_hours": 72,
     "suggest": "发送班型对比与当期政策（以价目表为准）"},
    {"key": "trial", "name": "试听与测评", "goal": "犹豫、比价:约免费测评或试听课",
     "first_response_hours": 24, "stay_limit_hours": 24,
     "suggest": "试听后 24 小时内跟进反馈"},
    {"key": "silent", "name": "沉默激活", "goal": "3 天无互动、试听未转化:补资料+学情分析",
     "first_response_hours": 72, "stay_limit_hours": 72,
     "suggest": "低压力资料触达，3 天内最多 2 次"},
]

STAGE_BY_KEY = {s["key"]: s for s in STAGES}

# 家长输入 → 推进到的阶段(简化状态机:按意图信号推进)
ADVANCE_HINTS = {
    "welcome": ["你好", "在吗", "刚进群", "孩子几岁"],
    "need": ["薄弱", "成绩", "不爱读", "识字量", "跟不上", "几年级"],
    "price": ["多少钱", "价格", "课时", "班型", "费用", "优惠"],
    "trial": ["试听", "试课", "体验", "测评", "先试试"],
}


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def stay_hours(entered_at: str, now: datetime | None = None) -> float:
    try:
        t = datetime.fromisoformat(entered_at)
    except (ValueError, TypeError):
        return 0.0
    return round(((now or datetime.now()) - t).total_seconds() / 3600, 1)


def board_entry(uid: str, state: dict | None, nickname: str = "") -> dict:
    """工作台 SOP 推进看板一行:阶段 / 已停留 / 超时 / 建议动作。"""
    state = state or {}
    key = state.get("stage", "welcome")
    stage = STAGE_BY_KEY.get(key, STAGES[0])
    hours = stay_hours(state.get("entered_at", ""))
    timeout = hours > stage["stay_limit_hours"]
    if key == "silent" and state.get("silent_hits", 0) >= 2:
        return {"uid": uid, "nickname": nickname, "stage": stage["name"],
                "stayed_hours": hours, "status": "已停止", "timeout": False,
                "suggest": "超过 2 次触达自动停止，家长明确拒绝则结案"}
    return {
        "uid": uid, "nickname": nickname, "stage": stage["name"],
        "stayed_hours": hours,
        "status": "超时" if timeout else "正常",
        "timeout": timeout,
        "suggest": stage["suggest"],
    }


def advance_on_message(current_stage: str, parent_message: str) -> str | None:
    """家长消息命中下一阶段意图时返回目标阶段 key,否则 None。"""
    order = [s["key"] for s in STAGES]
    try:
        idx = order.index(current_stage)
    except ValueError:
        idx = 0
    for key in order[idx + 1:] + order[:idx]:   # 只允许向前推进
        if any(h in parent_message for h in ADVANCE_HINTS.get(key, [])):
            if order.index(key) > idx:
                return key
    return None


def change_scope(entry: dict) -> dict:
    """人工调整的三种生效范围(OPSIE 6.2),写变更记录。"""
    scope = entry.get("scope", "once")
    assert scope in ("once", "default", "log_only")
    entry.setdefault("created_at", now_iso())
    return entry
