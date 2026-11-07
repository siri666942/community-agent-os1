"""经营周报(样例 #8 跨系统操盘的本地版):日志 + 产出 → 一页纸周报。"""
import json
import os
from collections import Counter

from .. import config
from ..llm import chat
from . import prompts


def weekly_report() -> str:
    log_text = ""
    if os.path.exists(config.LOG_FILE):
        with open(config.LOG_FILE, encoding="utf-8") as f:
            lines = f.readlines()
        log_text = "".join(lines[-200:])

    stats, table = _ticket_stats()
    pkg_dir = os.path.join(config.OUTPUT_DIR, "sop_packages")
    pkgs = sorted(os.listdir(pkg_dir)) if os.path.isdir(pkg_dir) else []

    summary = (
        f"工单统计(系统统计,数字以此为准,勿自行计数):\n{stats}\n\n"
        f"工单明细:\n| 工单 | 时间 | 风险 | 处置 | 状态 | 家长消息 |\n"
        f"|---|---|---|---|---|---|\n{table}\n\n"
        f"运营包:{len(pkgs)} 份({', '.join(pkgs)})\n\n"
        f"动作日志(最近):\n{log_text[-6000:]}"
    )
    report = chat(prompts.growth(prompts.T_REPORT), summary,
                  agent="数据增长·周报", input_summary="生成经营周报")

    out = os.path.join(config.HUB_DIR, "08-review.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write("# 08 · 经营周报\n\n" + report + "\n")
    return report


def _ticket_stats() -> tuple:
    """从工单 JSON 做确定性汇总,杜绝周报数字对不上账。"""
    tickets_dir = os.path.join(config.OUTPUT_DIR, "tickets")
    rows = []
    if os.path.isdir(tickets_dir):
        for fn in sorted(os.listdir(tickets_dir)):
            if not fn.endswith(".json"):
                continue
            try:
                with open(os.path.join(tickets_dir, fn), encoding="utf-8") as f:
                    t = json.load(f)
            except (OSError, json.JSONDecodeError):
                rows.append({"id": fn[:-5], "time": "?", "risk_level": "?",
                             "action": "?", "status": "读取失败", "message": ""})
                continue
            rows.append({
                "id": t.get("id", fn[:-5]), "time": t.get("time", ""),
                "risk_level": t.get("risk_level", "?"),
                "action": t.get("action", "?"),
                "status": t.get("status", "?"),
                "message": " ".join(t.get("message", "").split())[:30],
            })

    dist = Counter(r["risk_level"] for r in rows)
    stat_dist = Counter(r["status"] for r in rows)
    closed = sum(1 for r in rows if r["status"] == "已闭环")
    stats = (
        f"- 总数:{len(rows)} 张\n"
        f"- 风险分布:{' / '.join(f'{k}×{v}' for k, v in sorted(dist.items())) or '无'}\n"
        f"- 处置状态:{' / '.join(f'{k}×{v}' for k, v in sorted(stat_dist.items())) or '无'}\n"
        f"- 闭环率:{closed}/{len(rows)}"
    )
    table = "\n".join(
        f"| {r['id']} | {r['time']} | {r['risk_level']} | {r['action']} "
        f"| {r['status']} | {r['message']} |"
        for r in rows
    ) or "| (无) | | | | | |"
    return stats, table
