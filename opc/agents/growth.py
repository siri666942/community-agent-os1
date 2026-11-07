"""数据增长 Agent · 家长分层与跟进任务(确定性计算,依据可核验)。

分层只用给定数据(群聊互动 + 工单进线 + 触达记录),不臆造指标:
- 互动:发言次数、最近互动距今天数;
- 触达频次:我方运营包/工单应答等主动触达记录;
- 同意状态:junction 现阶段未采集授权数据,如实标注「未采集」,不猜测。
"""
import json
import os
import re
from collections import defaultdict

from .. import config
from ..llm import chat, log_action
from . import prompts

# 分层阈值(天,相对数据快照最新互动日)
TIERS = [
    ("活跃", 0, 7, "7 天内有互动"),
    ("正常", 8, 21, "8-21 天未互动"),
    ("沉默", 22, 45, "22-45 天未互动"),
    ("流失风险", 46, 10 ** 9, "45 天以上未互动"),
]

# 分层 → 确定性跟进动作
FOLLOWUP = {
    "活跃": "邀约分享阅读作品到群内,引导晒单与转介绍",
    "正常": "私聊反馈学情(识字量/阅读数据),铺垫长期阅读价值",
    "沉默": "唤醒私聊:关注是否遇到使用困难,给一次轻量帮助",
    "流失风险": "不再常规打扰;移交人工判断是否结营致谢/退出",
}


def _is_parent(sender: str) -> bool:
    return bool(sender) and "老师" not in sender and "适趣" not in sender


def segment(with_scripts: bool = False, auto: bool = True) -> dict:
    """确定性计算家长分层,产出跟进任务清单。with_scripts 时调用数据增长 Agent 撰写要点话术。"""
    # 1) 互动统计(群聊语料)
    stats = defaultdict(lambda: {"messages": 0, "last": "", "groups": set()})
    ref = ""
    chats_path = os.path.join(config.KNOWLEDGE_DIR, "chats.json")
    if os.path.exists(chats_path):
        with open(chats_path, encoding="utf-8") as f:
            chats = json.load(f)
        for msgs in chats.values():
            for m in msgs:
                t = m.get("time", "")
                ref = max(ref, t)
                if not _is_parent(m.get("sender", "")):
                    continue
                s = stats[m["sender"]]
                s["messages"] += 1
                s["last"] = max(s["last"], t)
                s["groups"].add(m.get("group", ""))

    # 2) 工单进线与触达记录
    tickets_dir = os.path.join(config.OUTPUT_DIR, "tickets")
    ticket_n = 0
    if os.path.isdir(tickets_dir):
        ticket_n = len([f for f in os.listdir(tickets_dir) if f.endswith(".json")])
    pkg_dir = os.path.join(config.OUTPUT_DIR, "sop_packages")
    outreach_n = len(os.listdir(pkg_dir)) if os.path.isdir(pkg_dir) else 0

    # 3) 确定性分层(相对数据快照最新互动日)
    import datetime
    ref_day = datetime.date.fromisoformat(ref[:10]) if ref else datetime.date.today()
    rows = []
    for name, s in stats.items():
        last_day = datetime.date.fromisoformat(s["last"][:10])
        days = (ref_day - last_day).days
        tier = next(label for label, lo, hi, _ in TIERS if lo <= days <= hi)
        rows.append({
            "parent": name, "tier": tier,
            "messages": s["messages"], "last": s["last"], "days_since": days,
            "groups": len(s["groups"]),
        })
    rows.sort(key=lambda r: (r["days_since"], -r["messages"]))

    dist = defaultdict(list)
    for r in rows:
        dist[r["tier"]].append(r)

    summary = {
        "ref_date": ref_day.isoformat(),
        "total_parents": len(rows),
        "tier_counts": {label: len(dist.get(label, [])) for label, _, _, _ in TIERS},
        "ticket_inbound": ticket_n, "outreach": outreach_n,
        "consent": "未采集(现阶段无授权数据,不猜测)",
    }

    outdir = os.path.join(config.OUTPUT_DIR, "growth")
    os.makedirs(outdir, exist_ok=True)

    # 4) 跟进任务清单(确定性规则)
    tasks = []
    for label, _, _, basis in TIERS:
        members = dist.get(label, [])
        if not members:
            continue
        tasks.append({
            "tier": label, "basis": basis, "count": len(members),
            "action": FOLLOWUP[label],
            "members": [m["parent"] for m in members[:20]],
        })

    result = {"summary": summary, "rows": rows, "tasks": tasks}

    # 5) 可选:数据增长 Agent 撰写跟进要点话术
    scripts = ""
    if with_scripts:
        data_txt = json.dumps(
            {"分层口径": "互动次数/最近互动距今天数/工单进线/触达记录",
             "快照日期": summary["ref_date"], "任务清单": tasks},
            ensure_ascii=False)
        scripts = chat(
            prompts.growth(prompts.T_GROWTH_TASKS),
            f"家长分层数据(确定性计算结果,数字不得更改):\n{data_txt}\n\n{prompts.banlist_block()}",
            agent="数据增长·跟进任务", input_summary="跟进要点话术",
        )

    # 6) 落盘 + 留痕
    md = _render_md(result, scripts)
    path = os.path.join(outdir, "segmentation.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(md)
    with open(os.path.join(outdir, "followups.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    log_action("数据增长·分层",
               f"快照 {summary['ref_date']} / 家长 {summary['total_parents']} 人",
               f"分层:{summary['tier_counts']} | 任务 {len(tasks)} 条", status="OK")
    result["path"] = path
    result["scripts"] = scripts
    return result


def _render_md(result: dict, scripts: str) -> str:
    s = result["summary"]
    lines = [
        "# 家长分层与跟进任务(数据增长 Agent)",
        "",
        f"> 快照日期:{s['ref_date']}(以语料最新互动日为「今天」) | "
        f"家长 {s['total_parents']} 人 | 工单进线 {s['ticket_inbound']} | 触达 {s['outreach']} | "
        f"同意状态:{s['consent']}",
        "",
        "## 分层与依据(确定性计算)",
        "",
        "| 层级 | 人数 | 依据 |",
        "|---|---|---|",
    ]
    for t in result["tasks"]:
        lines.append(f"| {t['tier']} | {t['count']} | {t['basis']} |")
    lines += ["", "## 跟进任务", ""]
    for t in result["tasks"]:
        lines.append(f"- **{t['tier']}**({t['count']} 人,示例:{'、'.join(t['members'][:5])})")
        lines.append(f"  - 动作:{t['action']}")
    if scripts:
        lines += ["", "## 跟进要点话术(数据增长 Agent 撰写)", "", scripts]
    return "\n".join(lines) + "\n"
