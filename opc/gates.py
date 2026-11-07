"""人工闸门:不可逆/对外动作必须老板拍板(全蓝图 9.2 闸门总表)。"""
from .llm import log_action
from .agents.compliance import content_hash

GATES = {
    1: "做什么生意",
    2: "定名;合规红项",
    3: "卖什么、承诺范围",
    4: "对外公开发布",
    5: "价格与条款",
    6: "真实收付款",
    7: "投诉/退款/舆情/法律",
    8: "周报决策、对外催款",
    9: "下一步战略",
}


def gate(no: int, materials: str, auto: bool = False, detail: str = "") -> dict:
    """仅明确批准有效；模拟批准带独立状态，且绑定材料哈希。"""
    title = GATES.get(no, "未知事项")
    print(f"\n🚦 人工闸门 {no}:{title}")
    if detail:
        print(f"   {detail}")
    print(f"   材料: {' '.join(materials.split())[:200]}")

    if auto:
        status = "SIMULATED_APPROVAL"
        print("   ⏩ 模拟批准（非真实授权）")
        log_action(f"闸门{no}", title, status, status=status)
        return {"status": status, "content_hash": content_hash(materials)}

    try:
        ans = input("   👉 老板拍板 [y=放行 / n=打回]: ").strip().lower()
    except (EOFError, TimeoutError):
        ans = ""
    status = "APPROVED" if ans in ("y", "yes") else "REJECTED" if ans in ("n", "no") else "PENDING"
    log_action(f"闸门{no}", title, status, status="GATE")
    print(f"   {status}")
    return {"status": status, "content_hash": content_hash(materials)}


def approved(decision: dict, materials: str) -> bool:
    """只有真实审批且内容未变才能用于真实交付。"""
    return decision.get("status") == "APPROVED" and decision.get("content_hash") == content_hash(materials)
