import json
import tempfile
import unittest
import os
import http.client
import threading
from http.server import ThreadingHTTPServer
from contextlib import closing
from pathlib import Path
from datetime import datetime
from unittest.mock import patch

from opc.agents.compliance import content_hash
from opc.agents import report
from opc.agents import sop_pipeline
from web_api import main
from web_api import worker

original_connect = main.workflow.connect


class WebOriginTests(unittest.TestCase):
    def test_custom_origin_can_read_and_start_jobs(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), main.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with patch.object(main, 'workflow_state', return_value={'analysis': {'total': 0}}), \
                 patch.object(main, 'start_job', return_value={'job_id': 'example'}):
                conn = http.client.HTTPConnection('127.0.0.1', server.server_port)
                origin = 'http://localhost:4173'
                conn.request('OPTIONS', '/api/workflow/seed', headers={'Origin': origin, 'Access-Control-Request-Method': 'POST', 'Access-Control-Request-Headers': 'content-type'})
                response = conn.getresponse()
                self.assertEqual(response.status, 204)
                self.assertEqual(response.getheader('Access-Control-Allow-Origin'), '*')
                response.read()
                conn.request('GET', '/api/workflow', headers={'Origin': origin})
                response = conn.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(response.getheader('Access-Control-Allow-Origin'), '*')
                response.read()
                for path in ('/api/workflow/seed', '/api/service'):
                    conn.request('POST', path, body='{}', headers={'Origin': origin, 'Content-Type': 'application/json'})
                    response = conn.getresponse()
                    self.assertEqual(response.status, 202)
                    self.assertEqual(response.getheader('Access-Control-Allow-Origin'), '*')
                    response.read()
                conn.close()
        finally:
            server.shutdown()
            thread.join()
            server.server_close()


class WebApprovalTests(unittest.TestCase):
    def test_real_worker_job_id_can_be_interrupted_before_writeback(self):
        with tempfile.TemporaryDirectory() as folder:
            db_path = str(Path(folder) / 'workflow.sqlite3')
            job_id = 'a' * 32
            connections = []
            def connect():
                db = original_connect(db_path)
                connections.append(db)
                return db
            def interrupted_package(day, **kwargs):
                self.assertTrue(kwargs['workflow_run_id'].startswith('web-' + job_id + '-sop-'))
                main.interrupt_runs(job_id)
                directory = Path(folder) / 'output' / 'sop_packages'
                directory.mkdir(parents=True, exist_ok=True)
                path = directory / 'late.md'
                path.write_text('迟到的运营包', encoding='utf-8')
                path.with_suffix('.md.json').write_text(json.dumps({'day': day, 'workflow_run_id': kwargs['workflow_run_id'],
                                                                   'decision': {'status': 'PENDING', 'content_hash': 'x'}}), encoding='utf-8')
                return {'status': 'PENDING_APPROVAL', 'tasks': [], 'gate4': 'PENDING', 'path': str(path)}
            try:
                with patch.dict(os.environ, {'OPC_WEB_JOB_ID': job_id}), patch.object(main, 'ROOT', Path(folder)), patch.object(worker.workflow, 'connect', side_effect=connect), patch.object(sop_pipeline, 'daily_package', side_effect=interrupted_package):
                    result = worker.execute('sop', {'day': 'D1'})
                    self.assertEqual(result['status'], 'INTERRUPTED')
                    view = main.state()
                    self.assertEqual(view['packages'], [])
                    self.assertEqual(view['interrupted_artifacts'][0]['day'], 'D1')
                    with closing(connect()) as db:
                        row = db.execute('SELECT id,status FROM runs').fetchone()
                        self.assertEqual(row['status'], 'INTERRUPTED')
                        self.assertTrue(row['id'].startswith('web-' + job_id + '-sop-'))
                        self.assertEqual(db.execute("SELECT COUNT(*) FROM trace WHERE status='APPROVED'").fetchone()[0], 0)
            finally:
                for db in connections: db.close()

    def test_file_journal_recovers_second_write_failure_and_commit_failure(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(main, 'ROOT', Path(folder)), patch.object(main, 'log_action'):
            root = Path(folder)
            db_path = str(root / 'workflow.sqlite3')
            connect = lambda: original_connect(db_path)
            directory = root / 'output' / 'sop_packages'
            directory.mkdir(parents=True)
            content = '## 任务 1 · 早 / 群 / 家长\n来源: sop#1 | 审核: PASS\n\n合规内容'
            digest = content_hash(content)
            header = '# 标题\n\n> 状态: PENDING_APPROVAL | 覆盖: 1/1 | 闸门④: PENDING\n\n'
            md, sidecar = directory / 'D1.md', directory / 'D1.md.json'
            package = {'decision': {'status': 'PENDING', 'content_hash': digest}, 'deliverable': False,
                       'tasks': [{'task': {'time': '早', 'channel': '群', 'audience': '家长', 'source': 'sop#1'},
                                  'review': {'status': 'PASS', 'content': '合规内容', 'reviewed_content_hash': content_hash('合规内容')}}]}
            md.write_text(header + content + '\n', encoding='utf-8')
            sidecar.write_text(json.dumps(package, ensure_ascii=False), encoding='utf-8')
            original_write = main._atomic_text
            writes = []
            def fail_second(path, text):
                writes.append(path)
                if len(writes) == 2: raise OSError('模拟第二个文件写入失败')
                original_write(path, text)
            with patch.object(main.workflow, 'connect', side_effect=connect), patch.object(main, '_atomic_text', side_effect=fail_second):
                with self.assertRaises(OSError):
                    main.approval({'kind': 'package', 'id': 'D1', 'decision': 'approve', 'content_hash': digest})
            self.assertEqual(json.loads(sidecar.read_text(encoding='utf-8'))['decision']['status'], 'PENDING')
            with patch.object(main.workflow, 'connect', side_effect=connect):
                main.recover_pending()
                self.assertEqual(json.loads(sidecar.read_text(encoding='utf-8'))['decision']['status'], 'APPROVED')
                self.assertIn('状态: READY', md.read_text(encoding='utf-8'))
                with closing(connect()) as db:
                    self.assertEqual(db.execute('SELECT COUNT(*) FROM web_file_journal').fetchone()[0], 0)

            md.write_text(header + content + '\n', encoding='utf-8')
            sidecar.write_text(json.dumps(package, ensure_ascii=False), encoding='utf-8')
            class FailCommit:
                def __init__(self): self.db = connect()
                def __getattr__(self, name): return getattr(self.db, name)
                def __enter__(self): return self
                def __exit__(self, *args):
                    self.db.rollback()
                    if args[0] is None: raise OSError('模拟数据库提交失败')
            with patch.object(main.workflow, 'connect', side_effect=FailCommit):
                with self.assertRaises(OSError):
                    main.approval({'kind': 'package', 'id': 'D1', 'decision': 'approve', 'content_hash': digest})
            self.assertEqual(json.loads(sidecar.read_text(encoding='utf-8'))['decision']['status'], 'PENDING')
            self.assertIn('状态: PENDING_APPROVAL', md.read_text(encoding='utf-8'))
            with closing(connect()) as db:
                self.assertEqual(db.execute('SELECT COUNT(*) FROM web_file_journal').fetchone()[0], 0)

    def test_interrupted_jobs_only_affect_web_runs(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(main.workflow, 'connect', side_effect=lambda: original_connect(str(Path(folder) / 'workflow.sqlite3'))):
            with closing(main.workflow.connect()) as db, db:
                for run_id in ('web-abc-run', 'web-def-run', 'cli-run'):
                    db.execute('INSERT INTO runs(id,type,status,input_ref) VALUES (?,?,?,?)', (run_id, 'DAILY_SOP', 'RUNNING', 'D1'))
            main.interrupt_runs('abc')
            with closing(main.workflow.connect()) as db:
                statuses = dict(db.execute('SELECT id,status FROM runs').fetchall())
                self.assertEqual(statuses, {'web-abc-run': 'INTERRUPTED', 'web-def-run': 'RUNNING', 'cli-run': 'RUNNING'})
            main.interrupt_runs()
            with closing(main.workflow.connect()) as db:
                statuses = dict(db.execute('SELECT id,status FROM runs').fetchall())
                self.assertEqual(statuses['web-def-run'], 'INTERRUPTED')
                self.assertEqual(statuses['cli-run'], 'RUNNING')

    def test_legacy_failed_low_risk_ticket_can_be_resolved(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(main, 'ROOT', Path(folder)), patch.object(main, 'log_action'), patch.object(main.workflow, 'connect', side_effect=lambda: original_connect(str(Path(folder) / 'workflow.sqlite3'))):
            directory = Path(folder) / 'output' / 'tickets'
            directory.mkdir(parents=True)
            ticket = {'id': 'old', 'risk_level': 'L1', 'review': {'status': 'REVIEW_REQUIRED'}, 'reply': ''}
            (directory / 'old.json').write_text(json.dumps(ticket), encoding='utf-8')
            self.assertEqual(main.state()['tickets'][0]['human_task']['status'], 'PENDING')
            result = main.resolve_human_task({'id': 'old', 'result': '人工检查完成'})
            self.assertEqual(result['human_task']['status'], 'COMPLETED')
            self.assertEqual(result['reply'], '')

    def test_escalation_failure_can_be_resolved_without_approval(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(main, 'ROOT', Path(folder)), patch.object(main, 'log_action'), patch.object(main.workflow, 'connect', side_effect=lambda: original_connect(str(Path(folder) / 'workflow.sqlite3'))):
            directory = Path(folder) / 'output' / 'tickets'
            directory.mkdir(parents=True)
            ticket = {'id': 'failed', 'risk_level': 'L3', 'gate7': 'REVIEW_REQUIRED',
                      'human_task': {'status': 'PENDING'}, 'reply': ''}
            (directory / 'failed.json').write_text(json.dumps(ticket), encoding='utf-8')
            result = main.resolve_human_task({'id': 'failed', 'result': '人工接管'})
            self.assertEqual(result['gate7'], 'REVIEW_REQUIRED')
            self.assertEqual(result['human_task']['status'], 'COMPLETED')
            self.assertEqual(result['reply'], '')

    def test_package_rejection_updates_header_and_rejects_tampering(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(main, 'ROOT', Path(folder)), patch.object(main, 'log_action'), patch.object(main.workflow, 'connect', side_effect=lambda: original_connect(str(Path(folder) / 'workflow.sqlite3'))):
            directory = Path(folder) / 'output' / 'sop_packages'
            directory.mkdir(parents=True)
            content = '## 任务 1 · 早 / 群 / 家长\n来源: sop#1 | 审核: PASS\n\n合规内容'
            digest = content_hash(content)
            header = '# 标题\n\n> 状态: PENDING_APPROVAL | 覆盖: 1/1 | 闸门④: PENDING\n\n'
            md = directory / 'D1.md'
            sidecar = directory / 'D1.md.json'
            package = {'decision': {'status': 'PENDING', 'content_hash': digest}, 'deliverable': False,
                       'tasks': [{'task': {'time': '早', 'channel': '群', 'audience': '家长', 'source': 'sop#1'},
                                  'review': {'status': 'PASS', 'content': '合规内容', 'reviewed_content_hash': content_hash('合规内容')}}]}
            sidecar.write_text(json.dumps(package, ensure_ascii=False), encoding='utf-8')
            md.write_text(header + content + '被修改', encoding='utf-8')
            with self.assertRaises(ValueError):
                main.approval({'kind': 'package', 'id': 'D1', 'decision': 'reject', 'content_hash': digest})
            self.assertEqual(json.loads(sidecar.read_text(encoding='utf-8'))['decision']['status'], 'PENDING')
            md.write_text(header + content + '\n', encoding='utf-8')
            main.approval({'kind': 'package', 'id': 'D1', 'decision': 'reject', 'content_hash': digest})
            final = md.read_text(encoding='utf-8')
            self.assertIn('状态: REJECTED | 覆盖: 1/1 | 闸门④: REJECTED', final)
            self.assertEqual(content_hash(final.split('\n\n', 2)[2].rstrip('\n')), digest)

    def test_report_counts_current_human_task_and_legacy_records(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            tickets = root / 'tickets'
            tickets.mkdir()
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            base = {'time': now, 'risk_level': 'L3', 'review': {'status': 'PASS'}, 'gate7': 'REJECTED'}
            current = dict(base, human_task={'status': 'PENDING'})
            (tickets / 'current.json').write_text(json.dumps(current), encoding='utf-8')
            (tickets / 'legacy.json').write_text(json.dumps(base), encoding='utf-8')
            with patch.object(report.config, 'OUTPUT_DIR', str(root)), patch.object(report.config, 'HUB_DIR', str(root)):
                self.assertIn('人工待办数：2', report.weekly_report())
                current['human_task']['status'] = 'COMPLETED'
                (tickets / 'current.json').write_text(json.dumps(current), encoding='utf-8')
                self.assertIn('人工待办数：1', report.weekly_report())

    def test_report_excludes_interrupted_late_ticket(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            tickets = root / 'tickets'
            tickets.mkdir()
            with closing(original_connect(str(root / 'workflow.sqlite3'))) as db, db:
                db.execute('INSERT INTO runs(id,type,status,input_ref) VALUES (?,?,?,?)', ('web-late', 'INBOUND_MESSAGE', 'INTERRUPTED', 'x'))
            ticket = {'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'workflow_run_id': 'web-late',
                      'risk_level': 'L3', 'review': {'status': 'REVIEW_REQUIRED'}, 'human_task': {'status': 'PENDING'}}
            (tickets / 'late.json').write_text(json.dumps(ticket), encoding='utf-8')
            with patch.object(report.config, 'OUTPUT_DIR', str(root)), patch.object(report.config, 'HUB_DIR', str(root)):
                output = report.weekly_report()
                self.assertIn('会话数：0', output)
                self.assertIn('人工待办数：0', output)

    def test_approval_recipients_include_full_batch_over_display_limit(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(main.workflow, 'connect', side_effect=lambda: original_connect(str(Path(folder) / 'workflow.sqlite3'))):
            content = '经过审核的提醒'
            digest = content_hash(content)
            review = {'status': 'PASS', 'reviewed_content_hash': digest}
            with closing(main.workflow.connect()) as db, db:
                for i in range(501):
                    customer = f'customer-{i:03}'
                    db.execute('INSERT INTO customers VALUES (?,?,?,?,?)', (customer, '训练营', 1, 2, '测试'))
                    db.execute('INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?)',
                               (f'task-{i:03}', 'batch-1', customer, '小客', '温和提醒', '测试', 'WAITING_CONTENT', '2026-11-07'))
                db.execute('INSERT INTO artifacts VALUES (?,?,?,?,?)', ('artifact-1', 'batch-1', content, digest, json.dumps(review)))
            state = main.workflow_state()
            self.assertEqual(len(state['tasks']), 500)
            artifact = state['artifacts'][0]
            self.assertEqual(len(artifact['approval_recipients']), 501)
            self.assertEqual(artifact['approval_recipients'][0], 'customer-000')
            self.assertEqual(artifact['approval_recipients'][-1], 'customer-500')
            self.assertTrue(artifact['material_hash'])

    def test_service_creates_safe_customer_and_uses_shared_inbound(self):
        with tempfile.TemporaryDirectory() as folder:
            db_path = str(Path(folder) / 'workflow.sqlite3')
            connections = []
            def connect():
                db = original_connect(db_path)
                connections.append(db)
                return db
            def inbound(db, customer, message):
                row = db.execute('SELECT * FROM customers WHERE id=?', (customer,)).fetchone()
                self.assertEqual((row['consent'], row['contact_limit'], row['stage']), (0, 0, '未确认'))
                return {'run_id': 'inbound-run', 'customer_id': customer}
            try:
                with patch.object(worker.workflow, 'connect', side_effect=connect), patch.object(worker.workflow, 'inbound', side_effect=inbound):
                    result = worker.execute('service', {'message': '你好'})
                    self.assertEqual(result['run_id'], 'inbound-run')
                    self.assertTrue(result['customer_id'].startswith('inbound-'))
                    with self.assertRaises(ValueError):
                        worker.execute('service', {'message': '你好', 'customer_id': 'missing'})
            finally:
                for db in connections: db.close()

    def test_package_status_reflects_actual_gate_decision(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(main, 'ROOT', Path(folder)):
            directory = Path(folder) / 'output' / 'sop_packages'
            directory.mkdir(parents=True)
            cases = [('PENDING', False, 'hash', 'PENDING_APPROVAL'),
                     ('REJECTED', False, 'hash', 'REJECTED'),
                     ('SIMULATED_APPROVAL', False, 'hash', 'SIMULATED_APPROVAL'),
                     ('APPROVED', True, 'hash', 'READY'),
                     ('PENDING', False, None, 'INCOMPLETE'),
                     ('APPROVED', False, 'hash', 'INCOMPLETE')]
            for index, (gate, deliverable, digest, _) in enumerate(cases):
                data = {'day': str(index), 'decision': {'status': gate, 'content_hash': digest},
                        'deliverable': deliverable}
                (directory / f'{index}.md.json').write_text(json.dumps(data), encoding='utf-8')
            result = main.state()
            actual = {item['day']: item['status'] for item in result['packages']}
            self.assertEqual(actual, {str(i): case[3] for i, case in enumerate(cases)})
            self.assertEqual(result['metrics']['pending_approvals'], 1)

    def test_ticket_approval_requires_current_review_and_material(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(main, 'ROOT', Path(folder)), patch.object(main, 'log_action'), patch.object(main.workflow, 'connect', side_effect=lambda: original_connect(str(Path(folder) / 'workflow.sqlite3'))):
            directory = Path(folder) / 'output' / 'tickets'
            directory.mkdir(parents=True)
            reply, advice = '安全回复', '建议人工跟进'
            material = json.dumps({'reply': reply, 'advice': advice}, ensure_ascii=False, sort_keys=True)
            digest = content_hash(material)
            ticket = {'id': 'T1', 'workflow_run_id': 'inbound-1', 'risk_level': 'L3', 'review_candidate': reply, 'escalation': advice,
                      'review': {'status': 'PASS', 'reviewed_content_hash': content_hash(reply)},
                      'human_task': {'status': 'PENDING', 'owner': '老板'},
                      'gate7_decision': {'status': 'PENDING', 'content_hash': digest}, 'gate7': 'PENDING'}
            path = directory / 'T1.json'
            with closing(main.workflow.connect()) as db, db:
                db.execute('INSERT INTO runs(id,type,status,input_ref,result) VALUES (?,?,?,?,?)',
                           ('inbound-1', 'INBOUND_MESSAGE', 'RUNNING', 'message-1', '{}'))
            path.write_text(json.dumps(ticket, ensure_ascii=False), encoding='utf-8')
            with self.assertRaises(ValueError):
                main.approval({'kind': 'ticket', 'id': 'T1', 'decision': 'approve', 'content_hash': digest})
            self.assertEqual(json.loads(path.read_text(encoding='utf-8'))['gate7'], 'PENDING')
            with closing(main.workflow.connect()) as db, db:
                db.execute('UPDATE runs SET status=?, result=? WHERE id=?', ('HUMAN_REVIEW', json.dumps(ticket), 'inbound-1'))
            with self.assertRaises(ValueError):
                main.resolve_human_task({'id': 'T1', 'result': '已经核查'})
            with self.assertRaises(ValueError):
                main.approval({'kind': 'ticket', 'id': 'T1', 'decision': 'approve', 'content_hash': 'stale'})
            ticket['review_candidate'] = '被修改的回复'
            path.write_text(json.dumps(ticket, ensure_ascii=False), encoding='utf-8')
            with self.assertRaises(ValueError):
                main.approval({'kind': 'ticket', 'id': 'T1', 'decision': 'approve', 'content_hash': digest})
            ticket['review_candidate'] = reply
            path.write_text(json.dumps(ticket, ensure_ascii=False), encoding='utf-8')
            result = main.approval({'kind': 'ticket', 'id': 'T1', 'decision': 'approve', 'content_hash': digest})
            self.assertEqual(result['reply'], '')
            self.assertEqual(result['gate7'], 'APPROVED')
            with closing(main.workflow.connect()) as db:
                run = db.execute('SELECT status, result FROM runs WHERE id=?', ('inbound-1',)).fetchone()
                self.assertEqual(run['status'], 'HUMAN_REVIEW')
                self.assertEqual(json.loads(run['result'])['gate7'], 'APPROVED')
                self.assertEqual(json.loads(run['result'])['human_task']['status'], 'PENDING')
                self.assertEqual(db.execute('SELECT status FROM trace WHERE run_id=?', ('inbound-1',)).fetchone()['status'], 'APPROVED')
            with self.assertRaises(ValueError):
                main.approval({'kind': 'ticket', 'id': 'T1', 'decision': 'approve', 'content_hash': digest})
            resolved = main.resolve_human_task({'id': 'T1', 'result': '已核查并线下跟进'})
            self.assertEqual(resolved['human_task']['status'], 'COMPLETED')
            self.assertEqual(resolved['reply'], '')
            with closing(main.workflow.connect()) as db:
                run = db.execute('SELECT status, result FROM runs WHERE id=?', ('inbound-1',)).fetchone()
                self.assertEqual(run['status'], 'RESOLVED')
                self.assertEqual(json.loads(run['result'])['human_task']['result'], '已核查并线下跟进')
                self.assertEqual(db.execute('SELECT status FROM trace WHERE run_id=? ORDER BY seq DESC', ('inbound-1',)).fetchone()['status'], 'COMPLETED')
            with self.assertRaises(ValueError):
                main.resolve_human_task({'id': 'T1', 'result': '再次处理'})

    def test_package_approval_verifies_reviewed_content(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(main, 'ROOT', Path(folder)), patch.object(main, 'log_action'), patch.object(main.workflow, 'connect', side_effect=lambda: original_connect(str(Path(folder) / 'workflow.sqlite3'))):
            directory = Path(folder) / 'output' / 'sop_packages'
            directory.mkdir(parents=True)
            content = '## 任务 1 · 早 / 群 / 家长\n来源: sop#1 | 审核: PASS\n\n合规内容'
            digest = content_hash(content)
            (directory / 'D1.md').write_text('# 标题\n\n> 状态: PENDING_APPROVAL | 覆盖: 1/1 | 闸门④: PENDING\n\n' + content + '\n', encoding='utf-8')
            package = {'workflow_run_id': 'sop-1', 'decision': {'status': 'PENDING', 'content_hash': digest}, 'deliverable': False,
                       'tasks': [{'task': {'time': '早', 'channel': '群', 'audience': '家长', 'source': 'sop#1'},
                                  'review': {'status': 'PASS', 'content': '合规内容', 'reviewed_content_hash': content_hash('合规内容')}}]}
            (directory / 'D1.md.json').write_text(json.dumps(package, ensure_ascii=False), encoding='utf-8')
            with closing(main.workflow.connect()) as db, db:
                original = {'path': str(directory / 'D1.md'), 'content': content, 'gate4': 'PENDING', 'status': 'PENDING_APPROVAL'}
                db.execute('INSERT INTO runs(id,type,status,input_ref,result) VALUES (?,?,?,?,?)',
                           ('sop-1', 'DAILY_SOP', 'RUNNING', 'D1', '{}'))
            with self.assertRaises(ValueError):
                main.approval({'kind': 'package', 'id': 'D1', 'decision': 'approve', 'content_hash': digest})
            with closing(main.workflow.connect()) as db, db:
                db.execute('UPDATE runs SET status=?,result=? WHERE id=?', ('PENDING_APPROVAL', json.dumps(original), 'sop-1'))
            result = main.approval({'kind': 'package', 'id': 'D1', 'decision': 'approve', 'content_hash': digest})
            self.assertTrue(result['deliverable'])
            markdown = (directory / 'D1.md').read_text(encoding='utf-8')
            self.assertIn('状态: READY | 覆盖: 1/1 | 闸门④: APPROVED', markdown)
            self.assertEqual(content_hash(markdown.split('\n\n', 2)[2].rstrip('\n')), digest)
            with closing(main.workflow.connect()) as db:
                run = db.execute('SELECT status, result FROM runs WHERE id=?', ('sop-1',)).fetchone()
                self.assertEqual(run['status'], 'READY')
                self.assertEqual(json.loads(run['result'])['gate4'], 'APPROVED')
                self.assertEqual(db.execute('SELECT status FROM trace WHERE run_id=?', ('sop-1',)).fetchone()['status'], 'APPROVED')


if __name__ == '__main__': unittest.main()
