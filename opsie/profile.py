"""Convert the imported 21-day profile into explainable reading indicators."""
import json
import re
from . import policy

DAYS = ["第十五天", "第十六天", "第十七天", "第十八天", "第十九天", "第二十天", "第二十一天"]


def minutes(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value) if value == 0 else None
    if isinstance(value, str):
        match = re.fullmatch(r"\s*(\d+)分(\d+)秒\s*", value)
        if match:
            return int(match.group(1)) + int(match.group(2)) / 60
    return None


def build(raw):
    data = json.loads(raw) if isinstance(raw, str) else (raw or {})
    daily = data.get("daily_reading") or {}
    rows = []
    for key in DAYS:
        entry = daily.get(key)
        duration = minutes(entry.get("阅读时长")) if isinstance(entry, dict) else None
        read = entry.get("是否阅读") if isinstance(entry, dict) else None
        rows.append({"day": key, "minutes": duration,
                     "read": True if read == "是" else False if read == "否" else None})
    missing = any(x["minutes"] is None or x["read"] is None for x in rows)
    active_days = sum(1 for x in rows if x["read"] is True)
    total = sum(x["minutes"] or 0 for x in rows)
    avg = total / 7
    conf = policy.load()["policies"]["activity.thresholds"]["value"]
    days_ok = active_days >= conf["high_active_days_min"]
    minutes_ok = avg >= conf["high_avg_reading_minutes_min"]
    level = "数据不足" if missing else "高" if days_ok and minutes_ok else "中" if days_ok or minutes_ok else "低"
    for row in rows:
        if row["minutes"] is not None:
            row["minutes"] = round(row["minutes"], 2)
    return {"activity": {"level": level, "active_days": active_days, "avg_minutes": round(avg, 2),
                         "total_minutes": round(total, 2), "window": "营期末 7 天阅读", "missing": missing,
                         "daily": rows},
            "tested": data.get("tested"), "test_result": data.get("test_result"),
            "signup": data.get("signup"), "member_link_clicks": data.get("member_link_clicks"),
            "baby_age": data.get("baby_age")}
