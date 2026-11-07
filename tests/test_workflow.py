import tempfile
import unittest
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from opc import workflow
from opc.agents import compliance

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = workflow.connect(self.tmp.name + '/test.sqlite')
        workflow.seed_demo(self.db)
    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()
    def test_segments_are_reproducible_and_respect_consent(self):
        a = workflow.analyze(self.db)
        self.assertEqual(a, workflow.analyze(self.db))
        self.assertEqual(a['total'], 30)
        plan = workflow.plan(self.db)
        self.assertTrue(any(t['action'] == '暂停触达' for t in plan['tasks']))
        self.assertTrue(any(t['action'] == '温和提醒' for t in plan['tasks']))
    def test_consent_changes_require_evidence_and_revoke_eligibility(self):
        customer = 'demo-001'
        with self.assertRaises(ValueError):
            workflow.change_consent(self.db, customer, True, '  ')
        workflow.change_consent(self.db, customer, False, '家长撤销')
        row = self.db.execute('SELECT * FROM consent_changes WHERE customer_id=?', (customer,)).fetchone()
        self.assertEqual((row['consent'], row['source']), (0, '家长撤销'))
        self.assertFalse(next(c for c in workflow.analyze(self.db)['customers'] if c['customer_id'] == customer)['consent'])
        with self.assertRaises(ValueError):
            workflow.change_consent(self.db, customer, 'true', '无效类型')

    @patch('opc.workflow.compliance.review_loop')
    @patch('opc.workflow.chat', return_value='温和提醒')
    def test_two_roles_keep_review_as_separate_gate(self, chat, review):
        review.return_value = {'status': 'REVIEW_REQUIRED', 'content': '温和提醒', 'reviewed_content_hash': None}
        plan = workflow.plan(self.db)
        self.assertEqual({t['owner'] for t in plan['tasks']}, {'数据增长 Agent'})
        artifact = workflow.create_content(self.db, plan['batch_id'])['artifact_id']
        steps = [(r['owner'], r['action']) for r in self.db.execute('SELECT * FROM trace WHERE run_id=?', (plan['batch_id'],))]
        self.assertIn(('数据增长 Agent', '计算分层'), steps)
        self.assertIn(('服务运营 Agent', '生成内容'), steps)
        self.assertIn(('服务运营 Agent', '审核内容'), steps)
        with self.assertRaises(ValueError):
            workflow.approve(self.db, plan['batch_id'], artifact, 'APPROVED')
    @patch('opc.workflow.compliance.review_loop')
    @patch('opc.workflow.chat', return_value='温和提醒')
    def test_review_approval_and_feedback(self, chat, review):
        review.return_value = {'status': 'PASS', 'content': '温和提醒', 'reviewed_content_hash': compliance.content_hash('温和提醒')}
        batch = workflow.plan(self.db)['batch_id']
        artifact = workflow.create_content(self.db, batch)['artifact_id']
        workflow.approve(self.db, batch, artifact, 'SIMULATED_APPROVAL')
        with self.assertRaises(ValueError): workflow.queue_drafts(self.db, batch, artifact)
        workflow.approve(self.db, batch, artifact, 'APPROVED')
        self.db.execute('UPDATE artifacts SET content=? WHERE id=?', ('被修改', artifact))
        self.db.commit()
        with self.assertRaises(ValueError): workflow.queue_drafts(self.db, batch, artifact)
        self.db.execute('UPDATE artifacts SET content=? WHERE id=?', ('温和提醒', artifact))
        self.db.commit()
        self.assertGreater(workflow.queue_drafts(self.db, batch, artifact), 0)
        draft = self.db.execute('SELECT id FROM drafts LIMIT 1').fetchone()[0]
        workflow.simulate_receipt(self.db, draft)
        with self.assertRaises(ValueError): workflow.simulate_receipt(self.db, draft)
        self.assertEqual(self.db.execute("SELECT count(*) FROM events WHERE type='simulated_delivery'").fetchone()[0], 1)
    @patch('opc.workflow.compliance.review_loop')
    @patch('opc.workflow.chat', return_value='违规')
    def test_failed_review_never_reaches_approval(self, chat, review):
        review.return_value = {'status': 'REVIEW_REQUIRED', 'content': '违规', 'reviewed_content_hash': None}
        batch = workflow.plan(self.db)['batch_id']
        artifact = workflow.create_content(self.db, batch)['artifact_id']
        with self.assertRaises(ValueError): workflow.approve(self.db, batch, artifact, 'APPROVED')

    @patch('opc.workflow.compliance.review_loop')
    @patch('opc.workflow.chat', return_value='提醒')
    def test_approval_checks_viewed_material_inside_transaction(self, chat, review):
        review.return_value = {'status': 'PASS', 'content': '提醒', 'reviewed_content_hash': compliance.content_hash('提醒')}
        batch = workflow.plan(self.db)['batch_id']
        artifact = workflow.create_content(self.db, batch)['artifact_id']
        digest = workflow.material(self.db, batch, artifact)[2]
        task = next(t['id'] for t in workflow.tasks(self.db, batch) if t['status'] == 'WAITING_CONTENT')
        with self.db: self.db.execute("UPDATE tasks SET status='PAUSED' WHERE id=?", (task,))
        with self.assertRaises(ValueError): workflow.approve(self.db, batch, artifact, 'APPROVED', expected_hash=digest)
        self.assertIsNone(self.db.execute('SELECT * FROM approvals WHERE batch_id=?', (batch,)).fetchone())
    @patch('opc.workflow.compliance.review_loop')
    @patch('opc.workflow.chat', return_value='提醒')
    def test_revoked_consent_blocks_draft(self, chat, review):
        review.return_value = {'status': 'PASS', 'content': '提醒', 'reviewed_content_hash': compliance.content_hash('提醒')}
        batch = workflow.plan(self.db)['batch_id']
        artifact = workflow.create_content(self.db, batch)['artifact_id']
        workflow.approve(self.db, batch, artifact, 'APPROVED')
        customer = next(t['customer_id'] for t in workflow.tasks(self.db, batch) if t['action'] == '温和提醒')
        self.db.execute('UPDATE customers SET consent=0 WHERE id=?', (customer,))
        with self.assertRaises(ValueError): workflow.queue_drafts(self.db, batch, artifact)

    @patch('opc.workflow.compliance.review_loop')
    @patch('opc.workflow.chat', return_value='提醒')
    def test_receipt_rechecks_consent_and_cross_batch_limit(self, chat, review):
        review.return_value = {'status': 'PASS', 'content': '提醒', 'reviewed_content_hash': compliance.content_hash('提醒')}
        drafts = []
        for _ in range(3):
            batch = workflow.plan(self.db)['batch_id']
            artifact = workflow.create_content(self.db, batch)['artifact_id']
            workflow.approve(self.db, batch, artifact, 'APPROVED')
            workflow.queue_drafts(self.db, batch, artifact)
            drafts.append(self.db.execute('SELECT d.id FROM drafts d JOIN tasks t ON t.id=d.task_id WHERE t.batch_id=? AND t.customer_id=?', (batch, 'demo-003')).fetchone()[0])
        self.db.execute('UPDATE customers SET consent=0 WHERE id=?', ('demo-003',))
        self.db.commit()
        with self.assertRaises(ValueError): workflow.simulate_receipt(self.db, drafts[0])
        self.db.execute('UPDATE customers SET consent=1 WHERE id=?', ('demo-003',))
        self.db.commit()
        workflow.simulate_receipt(self.db, drafts[0])
        workflow.simulate_receipt(self.db, drafts[1])
        with self.assertRaises(ValueError): workflow.simulate_receipt(self.db, drafts[2])
        self.assertEqual(self.db.execute("SELECT count(*) FROM events WHERE customer_id='demo-003' AND type='simulated_delivery'").fetchone()[0], 2)

    @patch('opc.workflow.compliance.review_loop')
    @patch('opc.workflow.chat', return_value='提醒')
    def test_concurrent_receipts_are_serialized(self, chat, review):
        review.return_value = {'status': 'PASS', 'content': '提醒', 'reviewed_content_hash': compliance.content_hash('提醒')}
        drafts = []
        for _ in range(2):
            batch = workflow.plan(self.db)['batch_id']
            artifact = workflow.create_content(self.db, batch)['artifact_id']
            workflow.approve(self.db, batch, artifact, 'APPROVED')
            workflow.queue_drafts(self.db, batch, artifact)
            drafts.append(self.db.execute('SELECT d.id FROM drafts d JOIN tasks t ON t.id=d.task_id WHERE t.batch_id=? AND t.customer_id=?', (batch, 'demo-003')).fetchone()[0])
        self.db.execute('UPDATE customers SET contact_limit=1 WHERE id=?', ('demo-003',))
        self.db.commit()

        def concurrently(ids):
            barrier = threading.Barrier(2)
            def run(draft):
                db = workflow.connect(self.tmp.name + '/test.sqlite')
                try:
                    barrier.wait(timeout=5)
                    workflow.simulate_receipt(db, draft)
                    return 'ok'
                except ValueError:
                    return 'blocked'
                finally:
                    db.close()
            with ThreadPoolExecutor(max_workers=2) as pool:
                return list(pool.map(run, ids))

        # Two workers racing on the same draft can only create one receipt.
        self.assertCountEqual(concurrently([drafts[0], drafts[0]]), ['ok', 'blocked'])
        self.assertEqual(self.db.execute("SELECT count(*) FROM events WHERE customer_id='demo-003' AND type='simulated_delivery'").fetchone()[0], 1)
        # Two distinct batches compete for one remaining slot.
        with self.db:
            self.db.execute("DELETE FROM events WHERE customer_id='demo-003' AND type='simulated_delivery'")
            self.db.execute("UPDATE drafts SET status='DRAFT' WHERE id=?", (drafts[0],))
        self.assertCountEqual(concurrently(drafts), ['ok', 'blocked'])
        self.assertEqual(self.db.execute("SELECT count(*) FROM events WHERE customer_id='demo-003' AND type='simulated_delivery'").fetchone()[0], 1)

    @patch('opc.workflow.compliance.review_loop')
    @patch('opc.workflow.chat', return_value='提醒')
    def test_queue_observes_concurrent_revocation(self, chat, review):
        review.return_value = {'status': 'PASS', 'content': '提醒', 'reviewed_content_hash': compliance.content_hash('提醒')}
        for revoked in ('approval', 'consent'):
            batch = workflow.plan(self.db)['batch_id']
            artifact = workflow.create_content(self.db, batch)['artifact_id']
            workflow.approve(self.db, batch, artifact, 'APPROVED')
            customer = next(t['customer_id'] for t in workflow.tasks(self.db, batch) if t['status'] == 'WAITING_CONTENT')
            ready = threading.Event()
            proceed = threading.Event()
            started = threading.Event()
            def queue():
                db = workflow.connect(self.tmp.name + '/test.sqlite')
                try:
                    ready.set()
                    proceed.wait(timeout=5)
                    started.set()
                    workflow.queue_drafts(db, batch, artifact)
                    return 'queued'
                except ValueError:
                    return 'blocked'
                finally:
                    db.close()
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(queue)
                self.assertTrue(ready.wait(timeout=5))
                self.db.execute('BEGIN IMMEDIATE')
                if revoked == 'approval':
                    self.db.execute("UPDATE approvals SET status='REJECTED' WHERE batch_id=?", (batch,))
                else:
                    self.db.execute('UPDATE customers SET consent=0 WHERE id=?', (customer,))
                proceed.set()
                self.assertTrue(started.wait(timeout=5))
                self.db.commit()
                self.assertEqual(future.result(timeout=10), 'blocked')
            self.assertEqual(self.db.execute('SELECT count(*) FROM drafts d JOIN tasks t ON t.id=d.task_id WHERE t.batch_id=?', (batch,)).fetchone()[0], 0)
            if revoked == 'consent':
                with self.db: self.db.execute('UPDATE customers SET consent=1 WHERE id=?', (customer,))

    @patch('opc.agents.frontdesk.handle')
    def test_inbound_records_result_and_deduplicates(self, handle):
        handle.return_value = {'id': 'ticket-1', 'risk_level': 'L2', 'review': {'status': 'PASS'},
                               'human_task': {'id': 'human-1', 'status': 'PENDING'}}
        result = workflow.inbound(self.db, 'demo-001', '需要帮助', 'message-1', auto=True)
        self.assertEqual(result['status'], 'HUMAN_REVIEW')
        self.assertEqual(self.db.execute('SELECT count(*) FROM trace WHERE run_id=?', (result['run_id'],)).fetchone()[0], 3)
        with self.assertRaises(Exception): workflow.inbound(self.db, 'demo-001', '需要帮助', 'message-1')
        self.assertEqual(handle.call_count, 1)

    @patch('opc.agents.frontdesk.handle', side_effect=RuntimeError('offline'))
    def test_inbound_failure_is_persisted(self, handle):
        result = workflow.inbound(self.db, 'demo-001', '需要帮助')
        self.assertEqual(result['status'], 'REVIEW_REQUIRED')
        self.assertEqual(self.db.execute('SELECT status FROM runs WHERE id=?', (result['run_id'],)).fetchone()[0], 'REVIEW_REQUIRED')

    def test_stage_change_is_audited_and_excludes_finished_customer(self):
        workflow.change_stage(self.db, 'demo-003', '已结束', '人工确认完成')
        self.assertEqual(self.db.execute('SELECT count(*) FROM state_changes').fetchone()[0], 1)
        self.assertFalse(any(t['customer_id'] == 'demo-003' for t in workflow.plan(self.db)['tasks']))

    def test_concurrent_stage_changes_form_a_contiguous_history(self):
        barrier = threading.Barrier(2)
        def change(stage):
            db = workflow.connect(self.tmp.name + '/test.sqlite')
            try:
                barrier.wait(timeout=5)
                workflow.change_stage(db, 'demo-003', stage, '人工确认')
            finally:
                db.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(change, ['承接期', '已结束']))
        changes = self.db.execute('SELECT old_stage, new_stage FROM state_changes WHERE customer_id=? ORDER BY rowid', ('demo-003',)).fetchall()
        self.assertEqual(changes[0]['old_stage'], '训练营')
        self.assertEqual(changes[1]['old_stage'], changes[0]['new_stage'])
        self.assertEqual(self.db.execute('SELECT stage FROM customers WHERE id=?', ('demo-003',)).fetchone()[0], changes[1]['new_stage'])

    @patch('opc.agents.sop_pipeline.daily_package')
    def test_sop_records_per_item_reviews(self, daily):
        daily.return_value = {'tasks': [{'task': {'source': 'sop/1'}, 'review': {'content': 'x', 'status': 'PASS'}}],
                              'gate4': 'SIMULATED_APPROVAL', 'path': 'draft.md', 'status': 'PENDING_APPROVAL'}
        result = workflow.sop_run(self.db, 'D4', auto=True)
        self.assertEqual(result['status'], 'PENDING_APPROVAL')
        self.assertEqual(self.db.execute('SELECT count(*) FROM trace WHERE run_id=?', (result['run_id'],)).fetchone()[0], 4)

if __name__ == '__main__': unittest.main()
