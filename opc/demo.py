"""3 分钟演示脚本(对齐全蓝图 §11):跑通闭环 + 一次失败重跑 + 人机闸门 + 周报。"""
from . import ingest, knowledge_base as kb
from .agents import frontdesk, report, sop_pipeline
from .llm import log_action

NAIVE_DRAFT = (
    "xx妈妈您好!我们这个课程效果特别好,百分百有效果,21天绝对能认识500个字,"
    "孩子一定会喜欢的!现在报名还送试用期内随时退款的保障,长期会员绘本永久可看,"
    "两年下来孩子绝对能认识3000字,不满意全额退款!赶紧下单吧~"
)


def run(auto: bool = False) -> None:
    print("=" * 60)
    print("🏢 一人公司演示 · AI 社群代运营(OPC × MiMo Agent 团队)")
    print("=" * 60)

    if not kb.qa_items():
        print("\n📦 [0] 摄取真实素材 → Context Hub …")
        print(ingest.ingest())

    print("\n── 🎯 案例A:家长价格异议(流水线 + 自动结案)──")
    t1 = frontdesk.handle("两年的阅读时间太长,可不可以一个月一个月的买?", auto=auto)
    print(f"\n【家长】{t1['message']}\n【服务运营 Agent · 客服】{t1['reply']}")
    print(f"→ 风险:{t1['risk_level']}({t1['risk_reason']})/ {t1['action']} / 合规 {t1['review']['status']}")

    print("\n── 💥 案例B:违规初稿被打回 → 自动修复(评审循环)──")
    print(f"\n【初稿 v1(违规)】\n{NAIVE_DRAFT}")
    t2 = frontdesk.handle("你们这个价格太贵了,也担心孩子坚持不下来", auto=auto,
                          naive_draft=NAIVE_DRAFT)
    for h in t2["review_history"]:
        print(f"  ✂ 第{h['round']}轮打回:{[v['original'] for v in h['violations']]}")
    print(f"\n【审核结果 {t2['review']['status']}】\n{t2['reply'] or '[未获准交付]'}")

    print("\n── 🚨 案例C:退费危机 → 服务运营 Agent 升级建议 + 人工闸门⑦ ──")
    t3 = frontdesk.handle("我要退款,你们这个就是骗钱的,不退我就去投诉曝光", auto=auto)
    print(f"\n【家长】{t3['message']}\n【服务运营 Agent · 客服】{t3['reply']}")
    print(f"→ 风险:{t3['risk_level']} / {t3['action']} / 闸门⑦:{t3.get('gate7')}")
    print(f"\n【服务运营 Agent · 处置建议】\n{t3.get('escalation', '')[:500]}")

    print("\n── 📅 案例D:当日运营包(SOP 流水线 + 闸门④)──")
    pkg = sop_pipeline.daily_package("D4", auto=auto)
    print(f"\n{pkg['content'][:600]}")
    print(f"\n→ 状态 {pkg['status']} / 闸门④:{pkg['gate4']}")

    print("\n── 📊 案例E:一键经营周报 ──")
    rep = report.weekly_report()
    print(f"\n{rep[:600]}")

    log_action("COO", "演示", "演示流程结束，请检查各项审批状态", status="OK")
    print("\n演示流程结束；请检查各项审核和审批状态。")
    print("   全部留痕见 logs/07-log.md,交付物见 output/,公司大脑见 hub/")
