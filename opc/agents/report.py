"""由结构化工单计算可复核的近七日指标。"""
import json
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta

from .. import config


def weekly_report() -> str:
    folder = os.path.join(config.OUTPUT_DIR, "tickets")
    now = datetime.now()
    records, skipped = [], []
    run_status = {}
    try:
        db_path = os.path.join(config.OUTPUT_DIR, 'workflow.sqlite3')
        if os.path.isfile(db_path):
            with closing(sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)) as db:
                run_status = {row[0]: (row[1], row[2]) for row in db.execute('SELECT id,status,result FROM runs')}
    except sqlite3.Error:
        # Fail closed for workflow-bound artifacts if state cannot be verified.
        run_status = {}
    for name in sorted(os.listdir(folder) if os.path.isdir(folder) else []):
        if not name.endswith(".json"):
            continue
        path = os.path.join(folder, name)
        try:
            with open(path, encoding="utf-8") as f:
                ticket = json.load(f)
            run_id = ticket.get('workflow_run_id')
            if run_id:
                run = run_status.get(run_id)
                try:
                    saved = json.loads(run[1]) if run else None
                except (ValueError, TypeError):
                    saved = None
                if not run or run[0] in ('RUNNING', 'INTERRUPTED') or not isinstance(saved, dict) or saved.get('id') != ticket.get('id'):
                    skipped.append(name)
                    continue
            created = datetime.strptime(ticket["time"], "%Y-%m-%d %H:%M:%S")
            if now - timedelta(days=7) <= created <= now:
                records.append((name, ticket))
        except (ValueError, KeyError, TypeError, OSError):
            skipped.append(name)
    reviews = [t["review"] for _, t in records if isinstance(t.get("review"), dict)]
    total = len(reviews)
    first = sum(bool(r.get("history")) and not r["history"][0].get("violations") and r.get("status") == "PASS" for r in reviews)
    final = sum(r.get("status") == "PASS" for r in reviews)
    def pending_human(t):
        task = t.get('human_task')
        if isinstance(task, dict):
            return task.get('status') != 'COMPLETED'
        # Older records predate explicit human tasks; retain their original
        # conservative review and approval interpretation.
        return t.get('review', {}).get('status') != 'PASS' or t.get('gate7') in ('PENDING', 'REJECTED', 'SIMULATED_APPROVAL')
    pending = sum(pending_human(t) for _, t in records)
    rate = lambda n: f"{n}/{total} ({n / total:.1%})" if total else "无可统计审核记录"
    lines = ["# 经营周报（近七日）", "", f"会话数：{len(records)}",
             *[f"{level}：{sum(t.get('risk_level') == level for _, t in records)}" for level in ("L1", "L2", "L3")],
             f"首轮通过率：{rate(first)}", f"最终通过率：{rate(final)}",
             f"平均审核轮次：{sum(r.get('review_rounds', 0) for r in reviews) / total:.2f}" if total else "平均审核轮次：无可统计审核记录",
             f"人工待办数：{pending}", f"缺少结构化审核记录：{len(records) - total}",
             "", "## 数据来源", *[f"- [工单 {name}](../output/tickets/{name})" for name, _ in records],
             "", f"无法读取的工单：{', '.join(skipped) if skipped else '无'}",
             "", "口径：近七日工单；通过率与平均轮次仅计算有结构化审核记录的工单。模拟批准不计为真实授权。"]
    result = "\n".join(lines) + "\n"
    out = os.path.join(config.HUB_DIR, "08-review.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write(result)
    return result
