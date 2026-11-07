"""SOP 日度运营包流水线(样例 #1 串行流水线 + #3 评审循环)。

SOP 检索 → 话术生成 → 合规评审 → 闸门④(对外发布)→ 交付包。
"""
import os

from .. import config, gates, knowledge_base as kb
from ..llm import chat
from . import compliance, prompts


def daily_package(day: str, auto: bool = False) -> dict:
    sop = kb.search_sop(day=day)
    if not sop:
        raise ValueError(f"未找到营期日「{day}」的 SOP,可选:{list(kb.sop_days().keys())}")
    day_label, entries = next(iter(sop.items()))

    sop_text = "\n".join(
        f"- [{e['time']}] {e['scene']}/{e['target']}:{' ; '.join(e['scripts'])[:300]}"
        + (f" (物料:{' ; '.join(e['materials'])[:150]})" if e["materials"] else "")
        for e in entries
    )

    # 1) 话术生成
    draft = chat(
        prompts.service(prompts.T_SOP_PACKAGE),
        f"营期日:{day_label}\n当日 SOP 条目:\n{sop_text}\n\n{prompts.banlist_block()}",
        agent="服务运营·运营内容", input_summary=day_label, temperature=0.2,
    )

    # 2) 合规评审循环
    final, rounds, history = compliance.review_loop(
        draft, context=f"当日 SOP:\n{sop_text[:800]}"
    )

    # 3) 对外发布闸门④
    passed = gates.gate(4, final, auto=auto, detail=f"{day_label} 运营包(群/私聊/朋友圈)")

    # 4) 交付包落盘
    os.makedirs(os.path.join(config.OUTPUT_DIR, "sop_packages"), exist_ok=True)
    path = os.path.join(config.OUTPUT_DIR, "sop_packages", f"{day_label.replace(' ', '_')}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# {day_label} · 运营包\n\n")
        f.write(f"> 合规评审:{rounds} 轮 | 闸门④:{'放行' if passed else '打回'}\n\n")
        f.write(final + "\n\n---\n\n## 原始 SOP 条目\n\n" + sop_text + "\n")
    return {
        "day": day_label, "path": path, "content": final,
        "review_rounds": rounds, "gate4": passed,
        "violations_found": sum(len(h["violations"]) for h in history),
    }
