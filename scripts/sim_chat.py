"""联调模拟:Web Chat(web_api)↔ Agent Service ↔ Excel 数据,模拟真实用户对话。

链路:模拟家长消息 → OS1 web_api /api/agent(代理)→ junction Agent Service
→ SQLite(Excel 导入的 15.7 万真实用户)→ 三备选/质检/画像/名单 原路返回。

用法:
    python3 -I scripts/sim_chat.py            # 三位真实家长,三段对话
    python3 -I scripts/sim_chat.py --uid 703593   # 指定家长
"""
import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time
import urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OS1 = os.path.join(os.path.dirname(BASE), "Community-Agent-OS1")
SERVICE_PORT = int(os.environ.get("OPC_SERVICE_PORT", "8080"))
WEB_API = f"http://127.0.0.1:8765"

sys.path.insert(0, BASE)
from service import config  # noqa: E402


def _http(url, payload=None):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode() if payload is not None else None,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def agent(path, body=None, method=None):
    """经 web_api 代理调用 Agent Service(模拟 Web Chat 的真实请求路径)。

    web_api 的 job 机制是异步的:POST /api/agent 返回 job id,轮询取结果。
    """
    payload = {"path": path, "method": method or ("POST" if body else "GET")}
    if body is not None:
        payload["body"] = body
    job = _http(WEB_API + "/api/agent", payload)
    job_id = job.get("job_id") or job.get("id")
    for _ in range(120):
        job = _http(WEB_API + "/api/jobs/" + job_id)
        if job["status"] == "completed":
            result = job["result"]
            return result["http_status"], result["data"]
        if job["status"] == "failed":
            raise RuntimeError(job.get("error") or "代理任务失败")
        time.sleep(0.5)
    raise RuntimeError("代理任务超时")


def pick_customers(n=3):
    """从 Excel 导入的真实用户里挑三类代表:高活跃/观望/沉默。"""
    con = sqlite3.connect(config.DB_PATH)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT uid, child_nickname, child_age, signup, tags, total_read_days,"
        " avg_read_minutes, link_clicks, daily_json FROM customers"
        " WHERE child_nickname != '' AND avg_read_minutes > 0 LIMIT 4000").fetchall()
    con.close()
    scored = []
    for r in rows:
        daily = json.loads(r["daily_json"] or "[]")
        active7 = sum(1 for d in daily[-7:] if d and d[0])
        scored.append((active7, r))
    scored.sort(key=lambda x: -x[0])
    picks, seen = [], set()
    # 高活跃(近7日活跃多)/ 中等 / 沉默(近7日 0 天)各取一
    for cond in (lambda a: a >= 5, lambda a: 1 <= a <= 3, lambda a: a == 0):
        for a, r in scored:
            if cond(a) and r["uid"] not in seen:
                seen.add(r["uid"])
                picks.append(r)
                break
    return picks[:n]


SCENARIOS = [
    ("想给孩子报个阅读课，你们的班型是怎样的？大概多少钱？", "价格咨询 → 三备选"),
    ("老师说效果挺好的，能保证孩子识字量提高吗？不满意能随时退吗？", "敏感话题 → 质检标注"),
    ("最近孩子不太爱看书，有什么办法吗？", "使用问题 → 关系型"),
]


def show_drafts(data):
    for d in data["drafts"]:
        mark = {"green": "🟢", "yellow": "🟡", "red": "🔴"}[d["qc"]["status"]]
        print(f"  {mark} [{d['variant']}·{d['position']}] {d['text']}")
        for r in d["qc"]["risks"]:
            print(f"      ⚠ 风险:{r['type']}({r['level']})「{r['matched']}」→ {r['suggestion']}")


def collab_loop():
    """双 Agent 协作闭环:分析师圈人 → 助手出稿 → 留痕回流 → 名单刷新。"""
    print(f"{'=' * 62}")
    print("🤝 双 Agent 协作闭环:增值分析师 ⇄ 运营助手")
    print(f"{'=' * 62}")

    # 第 1 步:增值分析师出今日名单,圈定跟进目标
    # (优先挑「高活跃但意向未满」的 S2 → 对话推进后可演示升层 S1)
    st, g = agent("/api/v1/growth/daily?limit=20")
    print("\n【第 1 步 · 增值分析师】出今日跟进名单:")
    for s in g["segments"]:
        who = "、".join(x["nickname"] for x in s["customers"][:3]) or "—"
        print(f"   {s['tier']} {s['name']}(示例 {s['count']} 人):{who}")

    target, from_tier = None, ""
    for s in g["segments"]:
        for x in s["customers"]:
            if x["activity"] == "高" and x["intent"] != "高":
                target, from_tier = x, s["tier"]
                break
        if target:
            break
    if not target:  # 退回 S1 首位,演示证据刷新
        for s in g["segments"]:
            if s["customers"]:
                target, from_tier = s["customers"][0], s["tier"]
                break
    if not target:
        print("   (名单为空,跳过协作演示)")
        return
    uid, nick = target["uid"], target["nickname"]
    print(f"\n   👉 圈定目标:{nick}(uid={uid} · 当前 {from_tier})")
    print(f"      圈人依据:{target['evidence']['activity']}")
    print(f"                {target['evidence']['intent']}")

    # 第 2 步:目标家长发来推进消息(问价 + 约试听 = 2 项推进信号)
    msg = "想问下价格怎么样，另外能约个试听吗？"
    print(f"\n【第 2 步 · 家长】{msg}")

    # 第 3 步:运营助手基于分析师圈定的画像出三备选
    st, data = agent("/api/v1/drafts", {"uid": uid, "message": msg})
    print(f"\n【第 3 步 · 运营助手】基于圈定用户出三备选(分层 {data['customer_snapshot']['tier']})")
    show_drafts(data)

    # 第 4 步:老师选用 B 发送留痕(消息入库,供回流)
    pick = next(d for d in data["drafts"] if d["variant"] == "B")
    final = pick["text"]
    if pick["qc"]["status"] == "yellow":
        final += "（以上信息以官方说明为准）"
    st, sent = agent("/api/v1/send", {
        "cid": data["cid"], "text": final, "variant": "B",
        "edited": final != pick["text"], "confirmed": True, "sender": "模拟老师"})
    print(f"\n【第 4 步 · 老师】发送留痕 → 闸门 {sent['gate']['qc_status']}"
          f" · {sent['gate']['message_id']}")

    # 第 5 步:回流验证 —— 分析师名单刷新,对话信号已计入意向
    st, g2 = agent(f"/api/v1/growth/daily?limit=20&uid={uid}")
    entry = next((x for s in g2["segments"] for x in s["customers"] if x["uid"] == uid), None)
    print("\n【第 5 步 · 回流验证】增值分析师名单刷新:")
    if entry:
        new_tier = next(s["tier"] for s in g2["segments"]
                        for x in s["customers"] if x["uid"] == uid)
        arrow = f"{from_tier} → {new_tier}" if new_tier != from_tier else f"{new_tier} 维持"
        print(f"   分层:{arrow}")
        print(f"   意向证据:{entry['evidence']['intent']}")
        print(f"   活跃证据:{entry['evidence']['activity']}")
        if new_tier != from_tier:
            action = next(s["action"] for s in g2["segments"] if s["tier"] == new_tier)
            print(f"   建议动作已切换:{action}")
    print("\n   🏁 闭环完成:分析师圈人 → 助手出稿 → 人工发送留痕 → 对话回流刷新分层")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--uid", help="指定家长 uid")
    args = ap.parse_args()

    if not os.path.exists(config.DB_PATH):
        sys.exit("请先运行 python3 -I scripts/import_excel.py 导入数据")

    # 1) 起 Agent Service(真实 Excel 数据)
    env = {**os.environ, "OPC_SERVICE_PORT": str(SERVICE_PORT), "PYTHONPATH": BASE}
    svc = subprocess.Popen([sys.executable, "-m", "service.app"], cwd=BASE, env=env,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # 2) 起 web_api,并把代理指向 Agent Service
    web = subprocess.Popen([sys.executable, "-m", "web_api.main"], cwd=OS1,
                           env={**os.environ, "OPC_AGENT_SERVICE_URL": f"http://127.0.0.1:{SERVICE_PORT}"},
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(40):
            try:
                st, d = agent("/healthz")
                if d.get("ok"):
                    break
            except Exception:  # noqa: BLE001
                time.sleep(0.5)
        else:
            sys.exit("Agent Service 启动超时")

        print("=" * 62)
        print("🧪 联调模拟:Web Chat → web_api → Agent Service → Excel 数据")
        print(f"   数据源:{os.path.basename(config.DB_PATH)}")
        print("=" * 62)

        con = sqlite3.connect(config.DB_PATH)
        total = con.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
        con.close()
        st, health = agent("/healthz")
        print(f"\n✅ 链路就绪 · Agent Service LLM={'on' if health['llm'] else 'off(模板稿)'} · 库内 {total} 位家长\n")

        if args.uid:
            picks = [type("R", (), {"uid": args.uid, "child_nickname": "(指定)",
                                    "child_age": "", "signup": "", "tags": "",
                                    "total_read_days": 0, "avg_read_minutes": 0})()]
        else:
            picks = pick_customers()

        for i, c in enumerate(picks, 1):
            uid = c["uid"]
            name = c["child_nickname"]
            print(f"{'─' * 62}")
            print(f"👤 模拟家长 {i}:{name}({c['child_age'] or '?'} 岁 · uid={uid}"
                  f" · 报名:{c['signup'] or '无'} · 总阅读 {int(c['total_read_days'] or 0)} 天)")
            msg, label = SCENARIOS[i - 1] if i <= 3 else SCENARIOS[0]
            print(f"\n【家长】{msg}   ← 场景:{label}")

            st, data = agent("/api/v1/drafts", {"uid": uid, "message": msg})
            print(f"\n【Agent Service · 运营助手三备选】(分层 {data['customer_snapshot']['tier']})")
            show_drafts(data)

            # 模拟老师:选 B 改写后发送(黄色稿需确认)
            pick = next(d for d in data["drafts"] if d["variant"] == "B")
            final = pick["text"]
            if pick["qc"]["status"] == "yellow":
                final += "（以上信息以官方说明为准）"
            st, sent = agent("/api/v1/send", {
                "cid": data["cid"], "text": final, "variant": "B",
                "edited": final != pick["text"], "confirmed": True, "sender": "模拟老师"})
            print(f"\n【老师】(选用 B 改写发送)→ 闸门 {sent['gate']['qc_status']}"
                  f" · 留痕 {sent['gate']['message_id']}")

            # 敏感场景额外演示红灯拦截
            if i == 2:
                st, q = agent("/api/v1/qc", {"text": "可以随时退款，保证提分"})
                print(f"\n【质检演示】「可以随时退款，保证提分」→ {q['status'].upper()}"
                      f" · 发送按钮置灰({q['sendable']}) · 风险:{'、'.join(r['type'] for r in q['risks'])}")

            # 画像与 SOP
            st, prof = agent(f"/api/v1/profile/{uid}")
            print(f"\n【画像】{prof['segment']['name']} · 活跃{prof['activity']['level']}"
                  f"({prof['activity']['active_days']}天/日均{prof['activity']['avg_minutes']}分)"
                  f" · 意向{prof['intent']['level']} · SOP:{prof['sop']['stage']}({prof['sop']['status']})")
            print(f"   概括:{prof['summary']}")
            print()

        collab_loop()
        print(f"\n🏁 联调完成:web_api 代理 → Agent Service → {total} 位真实用户数据,链路全部打通")
        print("=" * 62)
    finally:
        web.terminate()
        svc.terminate()
        web.wait(timeout=5)
        svc.wait(timeout=5)


if __name__ == "__main__":
    main()
