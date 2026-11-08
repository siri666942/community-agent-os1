"""Exercise local SQLite as a shared, persistent multi-user application backend."""
import json
import os
import shutil
import sqlite3
import tempfile
import threading
import time
import unittest
from contextlib import closing
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from opsie import ai, auth
from opsie.api import Handler, ThreadingHTTPServer
from opsie.setup_demo import setup_sqlite

ROOT = Path(__file__).resolve().parents[1]


def fake_model(system, data, max_tokens=0):
    if '候选回复质检员' in system:
        return {'reviews': [{'variant': v, 'status': 'green', 'risks': [], 'suggestion': ''} for v in 'ABC']}
    if '发送前质检' in system:
        return {'status': 'green', 'risks': [], 'suggestion': ''}
    if '业务敏感主题标准' in system:
        return {'sensitive': False, 'topics': [], 'reason': '', 'intent_signals': []}
    return {'drafts': [{'variant': v, 'text': '我们可以一起看看孩子喜欢的阅读内容。'} for v in 'ABC']}


class SQLiteBootstrapTests(unittest.TestCase):
    def test_first_run_uses_seed_and_second_run_preserves_user_data(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'OPSIE_DB_BACKEND': 'sqlite', 'OPSIE_SQLITE_PATH': str(Path(folder) / 'local.sqlite')}):
            credentials = {name: 'sample-password' for name in ['teacher', 'parent1', 'parent2', 'parent3', 'parent4']}
            setup_sqlite(credentials)
            path = Path(folder) / 'local.sqlite'
            with closing(sqlite3.connect(path)) as conn, conn:
                self.assertEqual(conn.execute('SELECT COUNT(*) FROM messages').fetchone()[0], 128)
                stored = conn.execute("SELECT password_hash FROM opsie_accounts WHERE username='teacher'").fetchone()[0]
                self.assertTrue(auth.verify_password('sample-password', stored))
                conn.execute("INSERT INTO messages(conversation_id,sender_user_id,source_system,message_type,body,created_at) VALUES(4,201,'opsie_live','text','保留测试消息','2026-01-01 10:00:00')")
            setup_sqlite(credentials)
            with closing(sqlite3.connect(path)) as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM messages WHERE body='保留测试消息'").fetchone()[0], 1)


class SQLiteIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory()
        cls.path = Path(cls.folder.name) / 'runtime.sqlite3'
        shutil.copyfile(ROOT / 'data' / 'opsie-demo.sqlite3', cls.path)
        with closing(sqlite3.connect(cls.path)) as db, db:
            db.execute('UPDATE opsie_accounts SET password_hash=?', (auth.hash_password('integration-password'),))
        cls.env = patch.dict(os.environ, {'OPSIE_DB_BACKEND': 'sqlite', 'OPSIE_SQLITE_PATH': str(cls.path)})
        cls.env.start()
        cls.model = patch.object(ai, 'call_model', side_effect=fake_model)
        cls.model.start()
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = 'http://127.0.0.1:' + str(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        cls.model.stop()
        cls.env.stop()
        cls.folder.cleanup()

    def request(self, path, token=None, body=None):
        headers = {'Content-Type': 'application/json'}
        if token: headers['Authorization'] = 'Bearer ' + token
        req = urllib.request.Request(self.base + path, headers=headers,
                                     data=json.dumps(body, ensure_ascii=False).encode() if body is not None else None)
        try:
            with urllib.request.urlopen(req, timeout=20) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as exc:
            return exc.code, json.load(exc)

    def login(self, username):
        status, result = self.request('/api/v1/login', body={'username': username, 'password': 'integration-password'})
        self.assertEqual(status, 200)
        return result['token']

    def test_seed_chat_ai_permissions_and_persistence(self):
        teacher, parent, other = self.login('teacher'), self.login('parent1'), self.login('parent2')
        _, conversations = self.request('/api/v1/conversations', parent)
        group = next(c['id'] for c in conversations['items'] if c['type'] == 'group')
        direct = next(c['id'] for c in conversations['items'] if c['type'] == 'direct')
        self.assertEqual(self.request('/api/v1/messages/' + direct, other)[0], 403)
        self.assertEqual(self.request('/api/v1/library', parent)[0], 403)
        self.assertEqual(len(self.request('/api/v1/messages/' + group + '?all=1', parent)[1]['items']), 64)
        self.assertEqual(len(self.request('/api/v1/messages/' + direct, parent)[1]['items']), 16)
        body = {'conversation_id': group, 'text': '请问如何培养孩子的阅读兴趣？', 'client_message_id': 'sqlite-test-unique-parent'}
        with ThreadPoolExecutor(max_workers=2) as pool:
            replies = list(pool.map(lambda _: self.request('/api/v1/messages', parent, body), range(2)))
        self.assertEqual([x[0] for x in replies], [200, 200])
        message_id = replies[0][1]['message_id']
        self.assertEqual(message_id, replies[1][1]['message_id'])
        self.assertTrue(any(m['id'] == 'm:' + message_id for m in self.request('/api/v1/messages/' + group, other)[1]['items']))
        _, job = self.request('/api/v1/drafts/auto', teacher, {'conversation_id': group, 'target_message_id': 'm:' + message_id})
        self.assertTrue(job['job_id'])
        for _ in range(100):
            _, status = self.request('/api/v1/jobs/' + job['job_id'], teacher)
            if status['status'] not in ('queued', 'running'): break
            time.sleep(.05)
        self.assertEqual(status['status'], 'succeeded', status)
        self.assertEqual(len(status['result']['drafts']), 3)
        self.assertFalse(status['stale'])
        _, entry = self.request('/api/v1/library', teacher, {'kind': 'standard', 'title': '测试口径', 'content': '先了解情况'})
        _, stale = self.request('/api/v1/jobs/' + job['job_id'], teacher)
        self.assertTrue(stale['stale'])
        self.assertEqual(self.request('/api/v1/library', teacher, {'id': entry['id'], 'delete': True})[0], 200)
        status, sent = self.request('/api/v1/messages', teacher, {'conversation_id': group, 'text': '我们可以一起看看孩子喜欢的阅读内容。', 'client_message_id': 'sqlite-test-unique-teacher'})
        self.assertEqual(status, 200, sent)
        self.assertIsNone(self.request('/api/v1/drafts/auto', teacher, {'conversation_id': group, 'target_message_id': 'm:' + message_id})[1]['job_id'])
        for _ in range(100):
            _, inbound = self.request('/api/v1/inbound/' + group, teacher)
            review = next((x for x in inbound['items'] if x['message_key'] == 'm:' + message_id), None)
            if review and review['status'] not in ('pending', 'running'): break
            time.sleep(.05)
        self.assertEqual(review['status'], 'complete')
        with closing(sqlite3.connect(self.path)) as reopened:
            self.assertEqual(reopened.execute('SELECT COUNT(*) FROM messages WHERE message_id=?', (message_id,)).fetchone()[0], 1)
            self.assertEqual(reopened.execute('SELECT COUNT(*) FROM messages WHERE message_id=?', (sent['message_id'],)).fetchone()[0], 1)
