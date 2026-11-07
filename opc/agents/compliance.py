"""Fail-closed review of the exact content proposed for delivery."""
import hashlib
import json

from .. import knowledge_base as kb
from ..llm import chat, log_action
from . import prompts


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def scan(text: str) -> list:
    rules = kb.qc_rules()
    violations = []
    for item in rules.get("sensitive_replacements", []):
        if item["word"] in text:
            violations.append({"type": "敏感词", "original": item["word"],
                               "suggestion": f"替换为「{item['replacement']}」"})
    for key, label in (("banned_absolute", "绝对词"), ("banned_overpromise", "过度承诺")):
        for word in rules.get(key, []):
            if word in text:
                violations.append({"type": label, "original": word, "suggestion": "移除违规表述"})
    return violations


def llm_review(text: str) -> list:
    rules = kb.qc_rules()
    raw = chat(prompts.COMPLIANCE, f"质检过程规则:\n{chr(10).join(rules.get('process_rules', []))}\n\n待审话术:\n{text}",
               max_tokens=600, temperature=0.0, agent=prompts.SERVICE_AGENT)
    data = json.loads(raw)
    if not isinstance(data, dict) or type(data.get("pass")) is not bool or not isinstance(data.get("violations"), list):
        raise ValueError("审核结果字段无效")
    violations = data["violations"]
    if any(not isinstance(v, dict) or any(not isinstance(v.get(k), str) or not v[k].strip()
           for k in ("type", "original", "suggestion")) for v in violations):
        raise ValueError("违规记录字段无效")
    if data["pass"] != (len(violations) == 0):
        raise ValueError("审核结论与违规记录矛盾")
    return violations


def review_loop(text: str, context: str = "", max_rounds: int = 3,
                use_llm_review: bool = True) -> dict:
    """Every returned version is reviewed; failures cannot be approved automatically."""
    current, history = text, []
    reason = "未完成审核"
    for rnd in range(1, max_rounds + 1):
        try:
            violations = scan(current)
            if not current.strip():
                raise ValueError("内容为空")
            if not violations:
                if not use_llm_review:
                    raise ValueError("未执行语义审核")
                violations = llm_review(current)
        except Exception as exc:
            reason = f"审核不可用或结果无效: {exc}"
            break
        history.append({"round": rnd, "violations": violations, "content_hash": content_hash(current)})
        if not violations:
            log_action(prompts.SERVICE_AGENT, f"第{rnd}轮检查", "通过", status="PASS")
            return {"content": current, "status": "PASS", "violations": [], "review_rounds": rnd,
                    "reviewed_content_hash": content_hash(current), "reason": "审核通过", "history": history}
        reason = "达到审核轮次上限，仍有违规"
        log_action(prompts.SERVICE_AGENT, f"第{rnd}轮检查", "发现违规", status="REJECT")
        if rnd == max_rounds:
            break
        try:
            current = chat(prompts.REWRITE, f"原话术:\n{current}\n\n违规清单:\n"
                           + json.dumps(violations, ensure_ascii=False) + f"\n\n业务上下文:\n{context}",
                           agent=prompts.SERVICE_AGENT, input_summary="按违规清单重写")
        except Exception as exc:
            reason = f"重写失败: {exc}"
            break
    log_action(prompts.SERVICE_AGENT, "审核未通过", reason, status="REVIEW_REQUIRED")
    return {"content": current, "status": "REVIEW_REQUIRED",
            "violations": history[-1]["violations"] if history else [], "review_rounds": len(history),
            "reviewed_content_hash": history[-1]["content_hash"] if history else None,
            "reason": reason, "history": history}
