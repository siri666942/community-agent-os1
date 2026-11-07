"""Agent Service 单元 + 链路测试(确定性,不依赖 LLM 与真实数据)。"""
import json
import os
import sys
import threading
import unittest
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from service import analyst, assistant, profile as profile_mod, qc, sop  # noqa: E402
from service import config  # noqa: E402

config.DB_PATH = ":memory:"  # 测试隔离


class TestQC(unittest.TestCase):
    def test_green(self):
        r = qc.check("妈妈您好,每天 15-20 分钟阅读,逐步积累,因人而异。")
        self.assertEqual(r["status"], "green")

    def test_red_refund(self):
        r = qc.check("可以随时退,不满意全额退款。")
        self.assertEqual(r["status"], "red")
        self.assertIn("退费承诺", [x["type"] for x in r["risks"]])

    def test_red_score_promise(self):
        self.assertEqual(qc.check("保证提分,一定进重点班")["status"], "red")

    def test_red_privacy(self):
        self.assertEqual(qc.check("把孩子的成绩单和家庭情况发群里")["status"], "red")

    def test_yellow_teacher(self):
        r = qc.check("我们全部是重点校在职名师。")
        self.assertEqual(r["status"], "yellow")

    def test_yellow_price(self):
        self.assertEqual(qc.check("今天最低价,给你锁价")["status"], "yellow")

    def test_yellow_competitor(self):
        self.assertEqual(qc.check("我们比某某机构强多了")["status"], "yellow")

    def test_gate(self):
        self.assertFalse(qc.is_sendable("red", confirmed=True))
        self.assertFalse(qc.is_sendable("yellow", confirmed=False))
        self.assertTrue(qc.is_sendable("yellow", confirmed=True))
        self.assertTrue(qc.is_sendable("green"))

    def test_effect_number_yellow(self):
        self.assertEqual(qc.check("21天认识500个字")["status"], "yellow")


class TestProfile(unittest.TestCase):
    def _cust(self, daily):
        return {"uid": "u1", "child_nickname": "豆豆", "signup": "两年",
                "tag_list": [], "daily": daily}

    def test_activity_high(self):
        # 6 天活跃、日均 20 分钟 → 高
        daily = [[1, 20]] * 6 + [[0, 0]]
        a = profile_mod.activity_score(daily)
        self.assertEqual(a["level"], "高")

    def test_activity_mid(self):
        # 6 天活跃但日均 5 分钟 → 中(只满足其一)
        daily = [[1, 5]] * 6 + [[0, 0]]
        self.assertEqual(profile_mod.activity_score(daily)["level"], "中")

    def test_activity_low(self):
        self.assertEqual(profile_mod.activity_score([[0, 0]] * 7)["level"], "低")

    def test_intent_high_two_signals(self):
        hits = profile_mod.detect_intents(["多少钱?", "能试听吗?"])
        self.assertEqual(profile_mod.intent_level(hits)["level"], "高")

    def test_intent_low(self):
        self.assertEqual(profile_mod.intent_level({})["level"], "低")

    def test_segment_s1(self):
        self.assertEqual(profile_mod.segment("高", "高")["tier"], "S1")

    def test_segment_s3(self):
        self.assertEqual(profile_mod.segment("低", "低", has_interaction=False)["tier"], "S3")

    def test_segment_s2(self):
        self.assertEqual(profile_mod.segment("高", "低")["tier"], "S2")

    def test_build_profile_evidence(self):
        p = profile_mod.build_profile(
            self._cust([[1, 23]] * 6 + [[0, 0]]), ["班型有哪些?", "老师背景?"])
        self.assertEqual(p["activity"]["level"], "高")
        self.assertEqual(p["intent"]["level"], "高")
        self.assertEqual(p["tier"], "S1")
        self.assertIn("近7日活跃 6 天", p["activity"]["evidence"])


class TestAssistant(unittest.TestCase):
    def test_three_drafts_positions(self):
        cust = {"uid": "u2", "child_nickname": "小明", "parent_role": "妈妈",
                "tag_list": [], "daily": [[1, 15]] * 7}
        r = assistant.draft_three(cust, "班型多少钱?")
        self.assertEqual([d["variant"] for d in r["drafts"]], ["A", "B", "C"])
        positions = [d["position"] for d in r["drafts"]]
        self.assertIn("标准口径", positions)
        self.assertIn("推进型", positions)
        self.assertIn("关系型", positions)
        for d in r["drafts"]:
            self.assertIn("qc", d)
            self.assertNotEqual(d["qc"]["status"], "red")  # 模板稿必须无红线

    def test_send_gate_red_locked(self):
        g = assistant.send_gate("保过,保证提分", "A", True, "T01")
        self.assertFalse(g["sendable"])
        self.assertEqual(g["qc_status"], "red")


class TestSOP(unittest.TestCase):
    def test_board_timeout(self):
        entry = sop.board_entry("u", {"stage": "need",
                                      "entered_at": "2026-11-01T00:00:00"})
        self.assertTrue(entry["timeout"])

    def test_advance(self):
        self.assertEqual(sop.advance_on_message("welcome", "这个班型多少钱?"), "price")

    def test_change_scope(self):
        e = sop.change_scope({"field": "stay_limit_hours", "scope": "once"})
        self.assertIn("created_at", e)


class TestAPI(unittest.TestCase):
    """起真实 HTTP 服务走全链路:出稿 → 质检 → 发送留痕。"""

    @classmethod
    def setUpClass(cls):
        from service import repository  # noqa: PLC0415
        from service import app as app_mod  # noqa: PLC0415
        repository._repo = repository.SQLiteRepository(":memory:")
        repo = repository._repo
        repo.con.execute(
            "INSERT INTO customers(uid,group_no,phone_masked,child_nickname,child_age,"
            "avg_read_minutes,channel,tags,parent_role,added_by,signup,signup_amount,"
            "expire_date,order_review,link_clicks,tested,test_result,learning_tags,"
            "total_read_days,daily_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("u100", "D1879", "133****8888", "豆豆", 5, 20.0, "抖音", "高意向",
             "妈妈", "T01", "两年", 2000, "2028-01-01", "好评", 3, "已测字",
             "300", "无变动", 12, json.dumps([[1, 20]] * 7)))
        repo.con.commit()
        cls.server = app_mod.ThreadingHTTPServer(("127.0.0.1", 0), app_mod.Handler)
        cls.port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def _req(self, path, data=None):
        url = f"http://127.0.0.1:{self.port}{path}"
        if data is None:
            r = urllib.request.urlopen(url)
        else:
            req = urllib.request.Request(url, data=json.dumps(data).encode(),
                                         headers={"Content-Type": "application/json"})
            r = urllib.request.urlopen(req)
        return r.status, json.loads(r.read())

    def test_healthz(self):
        st, d = self._req("/healthz")
        self.assertEqual(st, 200)
        self.assertTrue(d["ok"])

    def test_full_flow(self):
        # 1) 家长消息 → 三备选
        st, d = self._req("/api/v1/drafts",
                          {"uid": "u100", "message": "班型多少钱?能试听吗?"})
        self.assertEqual(st, 200)
        self.assertEqual(len(d["drafts"]), 3)
        self.assertEqual(d["customer_snapshot"]["tier"], "S1")
        cid = d["cid"]
        # 2) 质检:红色文本被拦
        st, d2 = self._req("/api/v1/qc", {"text": "可以随时退款"})
        self.assertEqual(d2["status"], "red")
        self.assertFalse(d2["sendable"])
        # 3) 发送红色 → 409
        try:
            self._req("/api/v1/send", {"cid": cid, "text": "可以随时退款",
                                       "variant": "A", "sender": "T01"})
            self.fail("红色应 409")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 409)
        # 4) 发送合规稿 → 留痕
        st, d3 = self._req("/api/v1/send",
                           {"cid": cid, "text": "以价目表为准,可约免费测评。",
                            "variant": "B", "sender": "T01", "edited": True})
        self.assertTrue(d3["ok"])
        self.assertTrue(d3["gate"]["edited"])
        # 5) 回放留痕
        st, d4 = self._req(f"/api/v1/messages/{cid}")
        roles = [m["role"] for m in d4["messages"]]
        self.assertIn("parent", roles)
        self.assertIn("teacher", roles)

    def test_profile_endpoint(self):
        st, d = self._req("/api/v1/profile/u100")
        self.assertEqual(d["tier"], "S1")
        self.assertEqual(d["phone_masked"], "133****8888")

    def test_growth_daily(self):
        st, d = self._req("/api/v1/growth/daily?limit=10")
        self.assertEqual(d["total_customers"], 1)
        self.assertEqual(d["segments"][0]["tier"], "S1")

    def test_sop_change_log(self):
        st, d = self._req("/api/v1/sop/change",
                          {"field": "stay_limit_hours", "old_value": "24",
                           "new_value": "48", "scope": "default",
                           "reason": "客户决策周期长", "editor": "T01"})
        self.assertTrue(d["ok"])
        self.assertEqual(d["change"]["scope"], "default")


if __name__ == "__main__":
    unittest.main(verbosity=2)
