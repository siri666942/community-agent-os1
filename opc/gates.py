"""人工闸门:不可逆/对外动作必须老板拍板(全蓝图 9.2 闸门总表)。"""
from .llm import log_action

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


def gate(no: int, materials: str, auto: bool = False, detail: str = "") -> bool:
    """弹出人工闸门。auto=True 时跳过交互直接放行(演示/无人值守)。"""
    title = GATES.get(no, "未知事项")
    print(f"\n🚦 人工闸门 {no}:{title}")
    if detail:
        print(f"   {detail}")
    print(f"   材料: {' '.join(materials.split())[:200]}")

    if auto:
        print("   ⏩ 自动放行(auto)")
        log_action(f"闸门{no}", title, "自动放行(auto)")
        return True

    try:
        ans = input("   👉 老板拍板 [y=放行 / n=打回]: ").strip().lower()
    except EOFError:
        ans = "y"
    ok = ans in ("y", "yes", "")
    log_action(f"闸门{no}", title, "放行" if ok else "打回", status="GATE")
    print(f"   {'✅ 放行' if ok else '❌ 打回'}")
    return ok
