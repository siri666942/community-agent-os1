import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from opc import gates
from opc.agents import compliance, sop_pipeline, frontdesk


class SafetyTests(unittest.TestCase):
    @patch('opc.gates.log_action')
    @patch('opc.agents.sop_pipeline.compliance.review_loop')
    @patch('opc.agents.sop_pipeline.chat', return_value='合规草稿')
    @patch('opc.agents.sop_pipeline.kb.search_sop')
    def test_sop_rejection_and_simulation_have_matching_status(self, search, chat, review, log):
        search.return_value = {'Day4': [{'time': '9', 'scene': '群', 'target': 'all', 'scripts': []}]}
        review.return_value = {'content': '合规草稿', 'status': 'PASS', 'review_rounds': 1,
                               'history': [], 'reviewed_content_hash': compliance.content_hash('合规草稿')}
        with tempfile.TemporaryDirectory() as tmp, patch('opc.agents.sop_pipeline.config.OUTPUT_DIR', tmp):
            with patch('builtins.input', return_value='n'):
                rejected = sop_pipeline.daily_package('D4')
            simulated = sop_pipeline.daily_package('D4', auto=True)
            for result, expected in ((rejected, 'REJECTED'), (simulated, 'SIMULATED_APPROVAL')):
                self.assertEqual(result['status'], expected)
                self.assertEqual(result['gate4'], expected)
                with open(result['path'], encoding='utf-8') as f: self.assertIn('状态: ' + expected, f.read())
                with open(result['path'] + '.json', encoding='utf-8') as f: data = json.load(f)
                self.assertEqual(data['decision']['status'], expected)
                self.assertFalse(data['deliverable'])

    def test_model_failures_preserve_l3_ticket_and_human_task(self):
        for failure in ('generation', 'review', 'escalation'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as tmp, \
                 patch('opc.agents.frontdesk.config.OUTPUT_DIR', tmp), \
                 patch('opc.agents.frontdesk.log_action'), \
                 patch('opc.agents.frontdesk.kb.search_qa', return_value=[]), \
                 patch('opc.agents.frontdesk._risk_level', return_value=('L3', '投诉')), \
                 patch('opc.agents.frontdesk.chat') as chat, \
                 patch('opc.agents.frontdesk.compliance.review_loop') as review, \
                 patch('opc.agents.frontdesk.gates.gate', return_value={'status': 'PENDING', 'content_hash': 'hash'}):
                review.return_value = {'content': '回复', 'status': 'PASS', 'review_rounds': 1, 'history': [], 'reason': '通过'}
                if failure == 'generation': chat.side_effect = [RuntimeError('生成失败'), '建议']
                elif failure == 'review':
                    chat.side_effect = ['回复', '建议']
                    review.side_effect = RuntimeError('审核失败')
                else: chat.side_effect = ['回复', RuntimeError('升级失败')]
                ticket = frontdesk.handle('我要投诉', workflow_run_id='run-1')
                with open(tmp + '/tickets/' + ticket['id'] + '.json', encoding='utf-8') as f:
                    saved = json.load(f)
                self.assertEqual(saved['message'], '我要投诉')
                self.assertEqual(saved['workflow_run_id'], 'run-1')
                self.assertEqual(saved['human_task']['status'], 'PENDING')
                self.assertEqual(saved['reply'], '')
                self.assertEqual(saved['delivery_status'], 'NOT_SENT')
                if failure == 'escalation': self.assertEqual(saved['gate7'], 'REVIEW_REQUIRED')
                else: self.assertEqual(saved['review']['status'], 'REVIEW_REQUIRED')

    @patch('opc.agents.frontdesk.log_action')
    @patch('opc.agents.frontdesk.kb.search_qa', return_value=[])
    @patch('opc.agents.frontdesk._risk_level', return_value=('L1', '普通咨询'))
    @patch('opc.agents.frontdesk.compliance.review_loop')
    def test_failed_l1_review_creates_human_task(self, review, risk, qa, log):
        review.return_value = {'content': '候选', 'status': 'REVIEW_REQUIRED', 'review_rounds': 0,
                               'history': [], 'reason': '审核服务不可用'}
        with tempfile.TemporaryDirectory() as tmp, patch('opc.agents.frontdesk.config.OUTPUT_DIR', tmp):
            ticket = frontdesk.handle('你好', naive_draft='候选', workflow_run_id='run-1')
            with open(tmp + '/tickets/' + ticket['id'] + '.json', encoding='utf-8') as f:
                stored = json.load(f)
        self.assertEqual(ticket['human_task']['status'], 'PENDING')
        self.assertIn('审核服务不可用', ticket['human_task']['reason'])
        self.assertEqual(ticket['reply'], '')
        self.assertEqual(stored['workflow_run_id'], 'run-1')

    @patch('opc.agents.sop_pipeline.gates.gate')
    @patch('opc.agents.sop_pipeline.compliance.review_loop')
    @patch('opc.agents.sop_pipeline.chat')
    @patch('opc.agents.sop_pipeline.kb.search_sop')
    def test_concurrent_sop_runs_keep_independent_matching_artifacts(self, search, chat, review, gate):
        search.return_value = {'Day4': [{'time': '9', 'scene': '群', 'target': 'all', 'scripts': []}]}
        chat.side_effect = ['first', 'second']
        review.side_effect = lambda text, **kw: {'content': text, 'status': 'PASS', 'review_rounds': 1,
                                                 'history': [], 'reviewed_content_hash': compliance.content_hash(text)}
        gate.side_effect = lambda no, materials, **kw: {'status': 'PENDING', 'content_hash': compliance.content_hash(materials)}
        with tempfile.TemporaryDirectory() as tmp, patch('opc.agents.sop_pipeline.config.OUTPUT_DIR', tmp):
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda _: sop_pipeline.daily_package('D4'), range(2)))
            self.assertNotEqual(results[0]['path'], results[1]['path'])
            for result in results:
                with open(result['path'], encoding='utf-8') as f:
                    self.assertIn(result['content'], f.read())
                with open(result['path'] + '.json', encoding='utf-8') as f:
                    data = json.load(f)
                self.assertEqual(data['tasks'][0]['review']['content'], result['tasks'][0]['review']['content'])
                self.assertEqual(data['decision']['content_hash'], compliance.content_hash(result['content']))

    @patch("opc.agents.compliance.log_action")
    @patch("opc.agents.compliance.scan", return_value=[])
    @patch("opc.agents.compliance.chat", return_value="not json")
    def test_invalid_semantic_review_is_not_pass(self, _chat, _scan, _log):
        self.assertEqual(compliance.review_loop("draft")["status"], "REVIEW_REQUIRED")

    @patch("opc.agents.compliance.log_action")
    @patch("opc.agents.compliance.chat", return_value="bad")
    @patch("opc.agents.compliance.scan", return_value=[{"type": "禁词", "original": "bad", "suggestion": "删除"}])
    def test_retry_exhaustion_cannot_pass(self, _scan, _chat, _log):
        result = compliance.review_loop("bad", max_rounds=3)
        self.assertEqual(result["status"], "REVIEW_REQUIRED")
        self.assertEqual(result["review_rounds"], 3)
        self.assertEqual(result["reviewed_content_hash"], compliance.content_hash(result["content"]))

    @patch("opc.gates.log_action")
    def test_approval_requires_explicit_input_and_exact_content(self, _log):
        with patch("builtins.input", return_value=""):
            self.assertEqual(gates.gate(4, "draft")["status"], "PENDING")
        with patch("builtins.input", side_effect=EOFError):
            self.assertEqual(gates.gate(4, "draft")["status"], "PENDING")
        with patch("builtins.input", side_effect=TimeoutError):
            self.assertEqual(gates.gate(4, "draft")["status"], "PENDING")
        with patch("builtins.input", return_value="y"):
            decision = gates.gate(4, "draft")
        self.assertTrue(gates.approved(decision, "draft"))
        self.assertFalse(gates.approved(decision, "changed"))
        self.assertFalse(gates.approved(gates.gate(4, "draft", auto=True), "draft"))

    @patch("opc.agents.sop_pipeline.gates.gate")
    @patch("opc.agents.sop_pipeline.compliance.review_loop")
    @patch("opc.agents.sop_pipeline.chat", return_value="draft")
    @patch("opc.agents.sop_pipeline.kb.search_sop")
    def test_incomplete_package_cannot_reach_gate(self, search, _chat, review, gate):
        search.return_value = {"Day4": [{"time": "9", "scene": "群", "target": "all", "scripts": []},
                                       {"time": "10", "scene": "私聊", "target": "one", "scripts": []}]}
        review.side_effect = [
            {"content": "ok", "status": "PASS", "review_rounds": 1, "history": [], "reviewed_content_hash": compliance.content_hash("ok")},
            {"content": "bad", "status": "REVIEW_REQUIRED", "reason": "违规", "review_rounds": 1, "history": [], "reviewed_content_hash": None},
        ]
        with tempfile.TemporaryDirectory() as tmp, patch("opc.agents.sop_pipeline.config.OUTPUT_DIR", tmp):
            result = sop_pipeline.daily_package("D4", auto=True)
            self.assertEqual(result["status"], "INCOMPLETE")
            self.assertEqual(len(result["tasks"]), 2)
            gate.assert_not_called()
            with open(result["path"] + ".json", encoding="utf-8") as f:
                self.assertFalse(json.load(f)["deliverable"])

    @patch("opc.agents.sop_pipeline.gates.gate")
    @patch("opc.agents.sop_pipeline.compliance.review_loop")
    @patch("opc.agents.sop_pipeline.chat", return_value="draft")
    def test_real_day4_maps_each_sop_entry(self, _chat, review, gate):
        review.return_value = {"content": "ok", "status": "PASS", "review_rounds": 1,
                               "history": [], "reviewed_content_hash": compliance.content_hash("ok")}
        gate.side_effect = lambda no, materials, **kwargs: {"status": "APPROVED", "content_hash": compliance.content_hash(materials)}
        with tempfile.TemporaryDirectory() as tmp, patch("opc.agents.sop_pipeline.config.OUTPUT_DIR", tmp):
            result = sop_pipeline.daily_package("D4")
        self.assertEqual(len(result["tasks"]), 10)
        self.assertEqual(len({t["task"]["source"] for t in result["tasks"]}), 10)
        self.assertEqual(result["status"], "READY")


if __name__ == "__main__":
    unittest.main()
