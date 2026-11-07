#!/usr/bin/env python3
"""OPC · 一人公司 CLI —— JUNCTION CHINA 2026 人工智能赛道。

用法:
  python3 run.py ingest                 # 素材 → Context Hub + 知识库
  python3 run.py service "家长消息"      # 客服值守(应答+合规+风控+闸门⑦)
  python3 run.py sop --day D4           # 当日运营包(流水线+闸门④)
  python3 run.py report                 # 一页纸经营周报
  python3 run.py demo [--simulate-approval] # 模拟审批演示
"""
import argparse

from opc import ingest
from opc.agents import frontdesk, report, sop_pipeline


def main() -> None:
    p = argparse.ArgumentParser(description="OPC · 一人公司(MiMo Agent 团队)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("ingest", help="摄取素材")

    s = sub.add_parser("service", help="客服值守")
    s.add_argument("message", help="家长消息")
    s.add_argument("--parent", default="家长")
    s.add_argument("--simulate-approval", action="store_true", help="模拟审批，不构成真实授权")

    s = sub.add_parser("sop", help="当日运营包")
    s.add_argument("--day", required=True, help="营期日,如 D4 / 承接期D1")
    s.add_argument("--simulate-approval", action="store_true", help="模拟审批，不构成真实授权")

    sub.add_parser("report", help="经营周报")

    s = sub.add_parser("demo", help="完整演示")
    s.add_argument("--simulate-approval", action="store_true", help="模拟审批，不构成真实授权")

    args = p.parse_args()

    if args.cmd == "ingest":
        print(ingest.ingest())
    elif args.cmd == "service":
        t = frontdesk.handle(args.message, parent=args.parent,
                             auto=args.simulate_approval)
        print(f"\n【应答】\n{t['reply'] or '[未获准交付]'}\n审核状态: {t['review']['status']}\n")
        print(f"风险 {t['risk_level']} / {t['action']} / 合规 {t['review_rounds']} 轮"
              + (f" / 闸门⑦:{t['gate7']}" if "gate7" in t else ""))
    elif args.cmd == "sop":
        pkg = sop_pipeline.daily_package(args.day, auto=args.simulate_approval)
        print(f"\n{pkg['content']}\n")
        print(f"→ {pkg['path']}(状态 {pkg['status']},闸门④:{pkg['gate4']})")
    elif args.cmd == "report":
        print(report.weekly_report())
    elif args.cmd == "demo":
        from opc.demo import run
        run(auto=args.simulate_approval)


if __name__ == "__main__":
    main()
