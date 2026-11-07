"""合规质检:确定性词表扫描 + MiMo 质检官评审,违规打回重写(评审循环,≤3 轮)。"""
import json
import re

from .. import knowledge_base as kb
from ..llm import chat, log_action
from . import prompts

# 一对一安全替换词:机械替换不产生病句,直接确定性修复,不消耗评审轮次。
# 语义级替换词(试用/体验/永久/努力)病句风险高,仍走 LLM 重写。
AUTO_FIX = {
    "学习": "阅读",
    "适趣AI阅读": "适趣AI中文",
    "课程": "阅读会员",
    "坚持": "保持",
    "努力": "保持",
}


def auto_fix(text: str) -> tuple:
    """确定性替换安全敏感词,返回 (修复后文本, 替换记录)。"""
    hits = []
    for w, r in AUTO_FIX.items():
        if w in text:
            text = text.replace(w, r)
            hits.append({"type": "敏感词", "original": w, "suggestion": f"替换为「{r}」"})
    return text, hits


def scan(text: str) -> list:
    """确定性扫描:敏感词/绝对词/过度承诺。返回违规清单。"""
    rules = kb.qc_rules()
    violations = []
    for item in rules.get("sensitive_replacements", []):
        w = item["word"]
        if w in text:
            violations.append({
                "type": "敏感词", "original": w,
                "suggestion": f"替换为「{item['replacement']}」",
            })
    for w in rules.get("banned_absolute", []):
        if w in text:
            violations.append({
                "type": "绝对词", "original": w,
                "suggestion": "删除绝对化表述,改为客观描述",
            })
    for w in rules.get("banned_overpromise", []):
        if w in text:
            violations.append({
                "type": "过度承诺", "original": w,
                "suggestion": "移除承诺,按 21天/15天/7天 使用权限口径说明",
            })
    return violations


def llm_review(text: str) -> list:
    """MiMo 质检官二审:态度、退费规范、语义级违规。"""
    rules = kb.qc_rules()
    proc = "\n".join(rules.get("process_rules", []))
    raw = chat(
        prompts.service(prompts.T_COMPLIANCE_REVIEW),
        f"质检过程规则:\n{proc}\n\n待审话术:\n{text}",
        max_tokens=600, temperature=0.0, agent="服务运营·审核",
    )
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
        return data.get("violations", []) if not data.get("pass", True) else []
    except json.JSONDecodeError:
        return []


def review_loop(text: str, context: str = "", max_rounds: int = 3,
                use_llm_review: bool = True) -> tuple:
    """评审循环:检查 → 打回重写 → 再检查,最多 max_rounds 轮。

    返回 (最终话术, 轮次, 全部违规记录)。
    """
    history = []
    current = text
    for rnd in range(1, max_rounds + 1):
        current, fixes = auto_fix(current)
        if fixes:
            log_action("评审循环", f"第{rnd}轮确定性替换",
                       f"{[f['original'] for f in fixes]} → 自动修复", status="FIX")
            history.append({"round": rnd, "violations": fixes, "auto_fixed": True})
        violations = scan(current)
        if use_llm_review and not violations:
            violations = llm_review(current)
        if not violations:
            log_action("评审循环", f"第{rnd}轮检查", "通过", status="PASS")
            return current, rnd, history

        history.append({"round": rnd, "violations": violations})
        log_action("评审循环", f"第{rnd}轮检查",
                   f"打回:{[v['original'] for v in violations]}", status="REJECT")
        fix_prompt = (
            f"原话术:\n{current}\n\n违规清单:\n"
            + json.dumps(violations, ensure_ascii=False, indent=1)
            + (f"\n\n业务上下文:\n{context}" if context else "")
        )
        current = chat(prompts.service(prompts.T_REWRITE), fix_prompt,
                       agent="服务运营·修复", input_summary="按违规清单重写")

    log_action("评审循环", f"{max_rounds}轮未完全通过", "输出最终版本并标记待人工复核",
               status="WARN")
    return current, max_rounds, history
