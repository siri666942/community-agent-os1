"""端到端流程验证:起真实服务 + 真实数据,走 OPSIE 核心链路。

验证五件事:
1. 三备选出稿(A/B/C 定位不同 + 逐条风险标注);
2. 质检三态(绿/黄/红;红锁发送、黄需确认);
3. 发送留痕(选用备选/是否改写/质检状态,可回放);
4. 画像硬规则(依据可解释)+ 分层;
5. 今日跟进名单 + SOP 看板。

用法:python3 -I scripts/flow_verify.py
"""
import json
import os
import sys
import threading
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from service import app as app_mod  # noqa: E402
from service import repository  # noqa: E402

PASS, FAIL = "\033[32m✅\033[0m", "\033[31m❌\033[0m"
results = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok))
    print(f"  {PASS if ok else FAIL} {name}" + (f"  — {detail}" if detail else ""))


def main() -> None:
    repo = repository.get_repository()   # 真实 SQLite(Excel 导入)
    server = app_mod.ThreadingHTTPServer(("127.0.0.1", 0), app_mod.Handler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{port}"

    def req(path, data=None):
        url = base + path
        if data is None:
            r = urllib.request.urlopen(url)
        else:
            r = urllib.request.urlopen(urllib.request.Request(
                url, data=json.dumps(data).encode(),
                headers={"Content-Type": "application/json"}))
        return json.loads(r.read())

    # 取一个活跃真实用户(近 7 日有阅读)
    sample = None
    for c in repo.list_customers(limit=500):
        if sum(1 for d in c.get("daily", [])[-7:] if d and d[0]) >= 4:
            sample = c
            break
    if not sample:
        sample = repo.list_customers(limit=1)[0]
    uid = sample["uid"]
    print(f"\n🎯 流程验证 · 样本用户 uid={uid}({sample['child_nickname']})")

    print("\n── ① 三备选出稿(运营助手)──")
    d = req("/api/v1/drafts", {"uid": uid, "message": "想了解一下班型和价格,能先试听吗?"})
    variants = [(x["variant"], x["position"], x["qc"]["status"]) for x in d["drafts"]]
    check("返回 A/B/C 三备选", [v[0] for v in variants] == ["A", "B", "C"], str(variants))
    check("三定位不同", len({v[1] for v in variants}) == 3)
    check("逐条带质检结果", all("qc" in x for x in d["drafts"]))
    check("客户快照含分层", d["customer_snapshot"]["tier"] in ("S1", "S2", "S3"),
          d["customer_snapshot"]["tier"])
    cid = d["cid"]

    print("\n── ② 质检三态 ──")
    g = req("/api/v1/qc", {"text": "每天 15-20 分钟阅读,逐步积累,因人而异。"})
    check("绿:合规文本通过", g["status"] == "green" and g["sendable"])
    y = req("/api/v1/qc", {"text": "我们全部是重点校在职名师,今天最低价给你锁价。"})
    check("黄:命中提示规则", y["status"] == "yellow" and not y["sendable"])
    y2 = req("/api/v1/qc", {"text": "师资以官方介绍为准,优惠需核对当期活动。",
                            "confirmed": True})
    check("黄+勾选确认 → 可发", y2["sendable"])
    r = req("/api/v1/qc", {"text": "保证提分,不满意随时全额退款。"})
    check("红:禁止词拦截", r["status"] == "red" and not r["sendable"],
          "/".join(x["type"] for x in r["risks"]))

    print("\n── ③ 发送闸门 + 留痕 ──")
    try:
        req("/api/v1/send", {"cid": cid, "text": "保证提分,随时退款。",
                             "variant": "A", "sender": "流程验证"})
        check("红色发送被拒绝(409)", False)
    except urllib.error.HTTPError as e:
        check("红色发送被拒绝(409)", e.code == 409)
    ok = req("/api/v1/send", {"cid": cid,
                              "text": "您好,班型按阅读节奏分档,价格以价目表为准,"
                                      "可以先约 15 分钟免费测评。",
                              "variant": "B", "edited": True, "confirmed": False,
                              "sender": "流程验证"})
    check("合规发送成功并留痕", ok["ok"] and ok["gate"]["edited"])
    replay = req(f"/api/v1/messages/{cid}")
    check("会话可回放(家长+老师)", [m["role"] for m in replay["messages"]] == ["parent", "teacher"],
          f"{len(replay['messages'])} 条")

    print("\n── ④ 画像硬规则(依据可解释)──")
    p = req(f"/api/v1/profile/{uid}")
    check("活跃度带依据", "阈值" in p["activity"]["evidence"], p["activity"]["evidence"])
    check("意向度带信号", "推进信号" in p["intent"]["evidence"], p["intent"]["evidence"])
    check("分层可解释", p["segment"]["tier"] in ("S1", "S2", "S3"),
          f"{p['segment']['name']} · 活跃{p['activity']['level']} · 意向{p['intent']['level']}")
    check("手机号脱敏", "*" in (p.get("phone_masked") or "***"),
          p.get("phone_masked") or "(空)")

    print("\n── ⑤ 增值分析师:今日名单 + SOP 看板 ──")
    g = req("/api/v1/growth/daily?limit=30")
    check("名单按 S1/S2/S3 分组", [s["tier"] for s in g["segments"]] == ["S1", "S2", "S3"])
    check("每层带专属话术", all(s["script"] for s in g["segments"]))
    b = req("/api/v1/sop/board?limit=5")
    check("SOP 看板返回推进状态", all("status" in row for row in b["board"]),
          f"{len(b['board'])} 位客户")
    ch = req("/api/v1/sop/change", {"field": "stay_limit_hours", "old_value": "24",
                                     "new_value": "48", "scope": "default",
                                     "reason": "流程验证", "editor": "流程验证"})
    check("SOP 调整留痕(默认规则)", ch["ok"] and ch["change"]["scope"] == "default")

    server.shutdown()
    passed = sum(1 for _, ok in results if ok)
    print(f"\n{'=' * 56}\n🏁 流程验证:{passed}/{len(results)} 通过")
    print("   链路:家长消息 → 三备选 → 三态质检 → 人工发送留痕 → 画像 → 名单/SOP")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
