"""逐条生成并审核 SOP，缺项或未审批时禁止交付。"""
import json
import os
import uuid

from .. import config, gates, knowledge_base as kb
from ..llm import chat
from . import compliance, prompts


def daily_package(day: str, auto: bool = False, workflow_run_id: str | None = None) -> dict:
    sop = kb.search_sop(day=day)
    if not sop:
        raise ValueError(f"未找到营期日「{day}」的 SOP")
    day_label, entries = next(iter(sop.items()))
    tasks = []
    for index, entry in enumerate(entries, 1):
        source = f"knowledge/sop.json#{day_label}/{index}"
        task = {"day": day_label, "time": entry.get("time", ""), "channel": entry.get("scene", ""),
                "audience": entry.get("target", ""), "intent": entry.get("scripts", []),
                "source": source}
        context = json.dumps(entry, ensure_ascii=False)
        try:
            draft = chat(prompts.SOP_WRITER + "\n仅完成所给的一项任务，不要生成其他渠道的内容。",
                         f"任务: {json.dumps(task, ensure_ascii=False)}\n原始条目: {context}",
                         agent=prompts.SERVICE_AGENT, input_summary=source)
            review = compliance.review_loop(draft, context=context)
        except Exception as exc:
            review = {"content": "", "status": "REVIEW_REQUIRED", "review_rounds": 0,
                      "violations": [], "history": [], "reviewed_content_hash": None,
                      "reason": f"生成失败: {exc}"}
        tasks.append({"task": task, "review": review})
    passed = sum(t["review"]["status"] == "PASS" and
                 t["review"]["reviewed_content_hash"] == compliance.content_hash(t["review"]["content"])
                 for t in tasks)
    complete = bool(entries) and passed == len(entries)
    content = "\n\n".join(
        f"## 任务 {i} · {t['task']['time']} / {t['task']['channel']} / {t['task']['audience']}\n"
        f"来源: {t['task']['source']} | 审核: {t['review']['status']}\n\n"
        + (t['review']['content'] if t['review']['status'] == 'PASS' else f"[待人工复核: {t['review']['reason']}]")
        for i, t in enumerate(tasks, 1))
    decision = gates.gate(4, content, auto=auto, detail=f"{day_label} 运营包") if complete else {
        "status": "PENDING", "content_hash": None}
    deliverable = complete and gates.approved(decision, content)
    status = ('INCOMPLETE' if not complete else 'READY' if deliverable else
              'REJECTED' if decision['status'] == 'REJECTED' else
              'SIMULATED_APPROVAL' if decision['status'] == 'SIMULATED_APPROVAL' else 'PENDING_APPROVAL')
    folder = os.path.join(config.OUTPUT_DIR, "sop_packages")
    os.makedirs(folder, exist_ok=True)
    # 每次运行独立版本；JSON 是网页发现入口，最后原子发布，避免读到半份产物。
    safe_label = ''.join(c if c.isalnum() or c in '-_' else '_' for c in day_label)
    path = os.path.join(folder, f"{safe_label}-{uuid.uuid4().hex}.md")
    temp_md, temp_json = path + '.tmp', path + '.json.tmp'
    try:
        with open(temp_md, "x", encoding="utf-8") as f:
            f.write(f"# {day_label} · 运营包（草稿）\n\n> 状态: {status} | 覆盖: {passed}/{len(entries)} | 闸门④: {decision['status']}\n\n{content}\n")
        with open(temp_json, "x", encoding="utf-8") as f:
            json.dump({"day": day_label, "tasks": tasks, "decision": decision, "deliverable": deliverable,
                       **({'workflow_run_id': workflow_run_id} if workflow_run_id else {})}, f, ensure_ascii=False, indent=2)
        os.replace(temp_md, path)
        os.replace(temp_json, path + '.json')
    except BaseException:
        for name in (temp_md, temp_json, path):
            if os.path.exists(name):
                os.remove(name)
        raise
    return {"day": day_label, "path": path, "content": content, "tasks": tasks,
            "status": status,
            "gate4": decision["status"], "review_rounds": sum(t["review"]["review_rounds"] for t in tasks),
            "violations_found": sum(len(h["violations"]) for t in tasks for h in t["review"]["history"])}
