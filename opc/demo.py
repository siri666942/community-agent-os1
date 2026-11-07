"""3 分钟演示脚本(对齐全蓝图 §11):跑通闭环 + 一次失败重跑 + 人机闸门 + 周报。"""
from . import ingest, knowledge_base as kb
from .agents import frontdesk, report, sop_pipeline
from .llm import log_action

NAIVE_DRAFT = (
    "xx妈妈您好!我们这个课程效果特别好,百分百有效果,21天绝对能认识500个字,"
    "孩子一定会喜欢的!现在报名还送试用期内随时退款的保障,长期会员绘本永久可看,"
    "两年下来孩子绝对能认识3000字,不满意全额退款!赶紧下单吧~"
)


def run(auto: bool = True) -> None:
    print("=" * 60)
    print("🏢 一人公司演示 · AI 社群代运营(OPC × MiMo Agent 团队)")
    print("   双 Agent 编制:服务运营 Agent(对外服务)· 数据增长 Agent(经营增长)")
    print("=" * 60)

    if not kb.qa_items():
        print("\n📦 [0] 摄取真实素材 → Context Hub …")
        print(ingest.ingest())

    print("\n── 🎯 案例A:家长价格异议(服务运营·起草→审核→工单)──")
    t1 = frontdesk.handle("两年的阅读时间太长,可不可以一个月一个月的买?", auto=auto)
    print(f"\n【家长】{t1['message']}\n【前台客服】{t1['reply']}")
    print(f"→ 风险:{t1['risk_level']}({t1['risk_reason']})/ {t1['action']} / 合规 {t1['review_rounds']} 轮通过")

    print("\n── 💥 案例B:违规初稿被打回 → 自动修复(服务运营·审核/修复)──")
    print(f"\n【初稿 v1(违规)】\n{NAIVE_DRAFT}")
    t2 = frontdesk.handle("你们这个价格太贵了,也担心孩子坚持不下来", auto=auto,
                          naive_draft=NAIVE_DRAFT)
    for h in t2["review_history"]:
        tag = "🔧 自动替换" if h.get("auto_fixed") else "✂ 打回"
        print(f"  {tag} 第{h['round']}轮:{[v['original'] for v in h['violations']]}")
    print(f"\n【修复后 v{len(t2['review_history']) + 1}(合规)】\n{t2['reply']}")

    print("\n── 🚨 案例C:退费危机 → 风险分流 + 人工待办 + 闸门⑦(服务运营)──")
    t3 = frontdesk.handle("我要退款,你们这个就是骗钱的,不退我就去投诉曝光", auto=auto)
    print(f"\n【家长】{t3['message']}\n【前台客服】{t3['reply']}")
    print(f"→ 风险:{t3['risk_level']} / {t3['action']} / 闸门⑦:{t3.get('gate7')}")
    print(f"\n【升级官处置建议】\n{t3.get('escalation', '')[:500]}")

    print("\n── 📅 案例D:当日运营内容(服务运营·运营包 + 闸门④)──")
    pkg = sop_pipeline.daily_package("D4", auto=auto)
    print(f"\n{pkg['content'][:600]}")
    print(f"\n→ 合规 {pkg['review_rounds']} 轮(发现违规 {pkg['violations_found']} 处)/ 闸门④:{'放行' if pkg['gate4'] else '打回'}")

    print("\n── 👥 案例E:家长分层与跟进任务(数据增长·确定性计算)──")
    from .agents import growth
    g = growth.segment()
    s = g["summary"]
    print(f"\n→ 快照 {s['ref_date']} | 家长 {s['total_parents']} 人 | 分层 {s['tier_counts']}")
    for t in g["tasks"]:
        print(f"  - {t['tier']}({t['count']} 人):{t['action']}")
    print(f"→ 依据与任务清单:{g['path']}")

    print("\n── 💰 案例F:第一单成交(数据增长·报价→闸门⑤→合同→收款→闸门⑥→交付→入账)──")
    from .agents import deal
    r = deal.first_order(auto=auto)
    print(f"\n→ {r['order_id']} {r['status']}")
    if "outdir" in r:
        print(f"→ 交付物:{r['outdir']}(报价单/协议要点/收款凭证/交付回执)")

    print("\n── 📊 案例G:一键经营周报(数据增长·复盘)──")
    rep = report.weekly_report()
    print(f"\n{rep[:600]}")

    log_action("COO", "完整演示", "完整闭环跑通:A/B/C/D/E/F/G(服务运营 A-D,数据增长 E-G)", status="OK")
    print("\n✅ 演示完成:人类老板 + 双 AI 员工(服务运营 Agent / 数据增长 Agent),")
    print("   跑通「获客应答 → 质检 → 风险分流 → 内容交付 → 分层跟进 → 成交入账 → 复盘」完整价值链闭环。")
    print("   全部留痕见 logs/07-log.md,交付物见 output/,公司大脑见 hub/")
