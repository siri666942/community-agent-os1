#!/usr/bin/env python3
"""OPC · 一人公司 CLI —— JUNCTION CHINA 2026 人工智能赛道。

用法:
  python3 run.py ingest                 # 素材 → Context Hub + 知识库
  python3 run.py service "家长消息"      # 客服值守(应答+合规+风控+闸门⑦)
  python3 run.py resolve T<id> --decision "处置决定"   # 老板拍板,L3 工单闭环
  python3 run.py sop --day D4           # 当日运营包(流水线+闸门④)
  python3 run.py deal                   # 第一单成交(报价→闸门⑤→合同→收款→闸门⑥→交付→入账)
  python3 run.py report                 # 一页纸经营周报
  python3 run.py demo [--no-auto]       # 3 分钟完整演示
"""
import argparse

from opc import ingest
from opc.agents import deal, frontdesk, growth, report, sop_pipeline


def main() -> None:
    p = argparse.ArgumentParser(description="OPC · 一人公司(MiMo Agent 团队)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("ingest", help="摄取素材")

    s = sub.add_parser("service", help="客服值守")
    s.add_argument("message", help="家长消息")
    s.add_argument("--parent", default="家长")
    s.add_argument("--no-auto", action="store_true", help="闸门需人工拍板")

    s = sub.add_parser("resolve", help="老板拍板处置工单(L3 闭环)")
    s.add_argument("ticket_id", help="工单号,如 T20261107112027")
    s.add_argument("--decision", required=True, help="处置决定,如:全额退款并安抚挽留")

    s = sub.add_parser("sop", help="当日运营包")
    s.add_argument("--day", required=True, help="营期日,如 D4 / 承接期D1")
    s.add_argument("--no-auto", action="store_true")

    s = sub.add_parser("deal", help="第一单成交(报价→合同→模拟收款→交付→入账)")
    s.add_argument("--customer", default="适趣AI中文")
    s.add_argument("--package", default="社群代运营服务包 · 标准版")
    s.add_argument("--no-auto", action="store_true", help="闸门⑤⑥需人工拍板")

    s = sub.add_parser("growth", help="家长分层与跟进任务(数据增长 Agent)")
    s.add_argument("--scripts", action="store_true", help="生成跟进要点话术(调用模型)")

    sub.add_parser("report", help="经营周报")

    s = sub.add_parser("demo", help="完整演示")
    s.add_argument("--no-auto", action="store_true", help="闸门需人工拍板")

    args = p.parse_args()

    if args.cmd == "ingest":
        print(ingest.ingest())
    elif args.cmd == "service":
        t = frontdesk.handle(args.message, parent=args.parent,
                             auto=not args.no_auto)
        print(f"\n【应答】\n{t['reply']}\n")
        print(f"风险 {t['risk_level']} / {t['action']} / 合规 {t['review_rounds']} 轮"
              + (f" / 闸门⑦:{t['gate7']}" if "gate7" in t else ""))
    elif args.cmd == "resolve":
        t = frontdesk.resolve(args.ticket_id, args.decision)
        print(f"\n【首响(已过合规 {t['first_response_rounds']} 轮)】\n{t['first_response']}\n")
        print(f"→ 工单 {t['id']} 已闭环(拍板:{t['decision']})")
    elif args.cmd == "sop":
        pkg = sop_pipeline.daily_package(args.day, auto=not args.no_auto)
        print(f"\n{pkg['content']}\n")
        print(f"→ {pkg['path']}(合规 {pkg['review_rounds']} 轮,闸门④:{'放行' if pkg['gate4'] else '打回'})")
    elif args.cmd == "deal":
        r = deal.first_order(args.customer, auto=not args.no_auto,
                             package=args.package)
        print(f"\n→ {r['order_id']} {r['status']}")
        if "outdir" in r:
            print(f"→ 交付物:{r['outdir']}")
    elif args.cmd == "growth":
        r = growth.segment(with_scripts=args.scripts)
        print(f"\n→ {r['path']}")
        s = r["summary"]
        print(f"→ 家长 {s['total_parents']} 人,分层 {s['tier_counts']},跟进任务 {len(r['tasks'])} 条")
    elif args.cmd == "report":
        print(report.weekly_report())
    elif args.cmd == "demo":
        from opc.demo import run
        run(auto=not args.no_auto)


if __name__ == "__main__":
    main()
