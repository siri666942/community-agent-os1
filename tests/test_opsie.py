"""Focused checks for the demo's data and message boundaries."""
import unittest
import copy
from datetime import timedelta
from unittest.mock import patch

from opsie import ai, auth, dashboard, profile
from opsie.db import now


class ProfileTests(unittest.TestCase):
    def test_reading_minutes_and_exact_high_threshold(self):
        values = {day: {"是否阅读": "是" if i < 4 else "否",
                        "阅读时长": "17分30秒" if i < 4 else 0}
                  for i, day in enumerate(profile.DAYS)}
        result = profile.build({"daily_reading": values})["activity"]
        self.assertEqual(result["active_days"], 4)
        self.assertEqual(result["avg_minutes"], 10)
        self.assertEqual(result["level"], "高")
        self.assertAlmostEqual(profile.minutes("12分16秒"), 12 + 16 / 60)

    def test_missing_is_not_low_and_rounding_does_not_cross_threshold(self):
        values = {day: {"是否阅读": "是" if i < 4 else "否",
                        "阅读时长": "17分29秒" if i < 4 else 0}
                  for i, day in enumerate(profile.DAYS)}
        self.assertEqual(profile.build({"daily_reading": values})["activity"]["level"], "中")
        values.pop(profile.DAYS[-1])
        self.assertEqual(profile.build({"daily_reading": values})["activity"]["level"], "数据不足")


class AuthTests(unittest.TestCase):
    def test_password_hash_and_unique_tokens(self):
        stored = auth.hash_password("example password")
        self.assertNotIn("example password", stored)
        self.assertTrue(auth.verify_password("example password", stored))
        self.assertFalse(auth.verify_password("wrong", stored))
        self.assertNotEqual(auth.token_hash("one"), auth.token_hash("two"))


class QualityTests(unittest.TestCase):
    def test_red_promise_and_channel_privacy(self):
        self.assertEqual(ai.quick_review("报名后可以随时退款", "direct")["status"], "red")
        self.assertEqual(ai.quick_review("请把成绩单发在群里", "group")["status"], "red")
        self.assertNotEqual(ai.quick_review("请把成绩单发给我", "direct")["status"], "red")

    def test_confirmed_rule_level_overrides_default(self):
        from opsie import policy
        doc = copy.deepcopy(policy.load())
        doc['policies']['qc.price_promises']['status'] = 'confirmed'
        doc['policies']['qc.price_promises']['value'] = {'level': 'red'}
        with patch('opsie.ai.policy.load', return_value=doc):
            self.assertEqual(ai.quick_review('今天给您锁价', 'direct')['status'], 'red')

    def test_candidate_qc_failure_is_visible_and_red_stays_red(self):
        drafts = [
            {'variant': 'A', 'text': '您好', 'qc': {'status': 'green', 'risks': [], 'suggestion': None}},
            {'variant': 'B', 'text': '可以随时退款', 'qc': {'status': 'red', 'risks': [], 'suggestion': '修改'}},
        ]
        with patch('opsie.ai.call_model', side_effect=RuntimeError('offline')):
            result = ai.review_candidates(drafts, 'direct')
        self.assertEqual([d['qc']['status'] for d in result], ['pending', 'red'])

    def test_candidate_variants_are_matched_by_identity(self):
        from service.assistant import normalize_model_drafts
        payload = {'drafts': [{'variant': 'C', 'text': '关心'}, {'variant': 'A', 'text': '事实'}, {'variant': 'B', 'text': '下一步'}]}
        result = normalize_model_drafts(payload, lambda _: {'status': 'green'})
        self.assertEqual([(d['variant'], d['text']) for d in result], [('A', '事实'), ('B', '下一步'), ('C', '关心')])

    def test_denial_goes_to_semantic_review(self):
        response = {"status": "green", "risks": [], "suggestion": ""}
        with patch("opsie.ai.call_model", return_value=response) as model:
            self.assertEqual(ai.review_outbound("我不承诺随时退款，具体规则先核实。", "direct")["status"], "green")
            model.assert_called_once()

    def test_intent_filters_wrong_author_old_message_and_rejection(self):
        def msg(uid, role, text, age):
            return {"id": text, "sender_id": uid, "sender_role": role, "text": text,
                    "time": now() - timedelta(days=age), "type": "text"}
        items = [msg("1", "teacher", "会员价格多少钱", 0), msg("1", "parent", "试听", 4),
                 msg("1", "parent", "不报名，也不需要资料", 0), msg("1", "parent", "请问价格是多少", 0)]
        version = __import__('opsie.policy', fromlist=['load']).load()['runtime_version']
        reviews = {m['id']: {'status': 'complete', 'policy_version': version,
                             'details': {'intent_signals': ['问价'] if m['text'] == '请问价格是多少' else []}}
                   for m in items}
        result = dashboard.intent(items, "1", reviews)
        self.assertEqual(result["level"], "中")
        self.assertEqual(len(result["signals"]), 1)

    def test_unprocessed_messages_not_misreported_as_low_intent(self):
        items = [{"id": "m:1", "sender_id": "1", "sender_role": "parent", "text": "请问价格", "time": now(), "type": "text"}]
        self.assertEqual(dashboard.intent(items, "1", {})["level"], "待识别")


if __name__ == "__main__":
    unittest.main()
