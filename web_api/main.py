"""Local web adapter. Start in junction: python -m web_api.main.

This server binds to loopback and never sends messages to parents. Jobs run in
separate processes so CLI approval prompts receive EOF instead of blocking.
"""
import json
import mimetypes
import os
import re
import subprocess
import sys
import threading
import time
import uuid
from contextlib import closing
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from opc import config, knowledge_base, workflow
from opc.agents import compliance
from opc.llm import log_action

ROOT = Path(config.ROOT)
JOBS = {}
LOCK = threading.Lock()


def _read(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


def _legacy_review_task(ticket):
    """Expose old L1 review failures as a pending manual task on read."""
    review = ticket.get('review')
    if (not ticket.get('human_task') and ticket.get('risk_level') == 'L1'
            and isinstance(review, dict) and review.get('status') != 'PASS'):
        ticket['human_task'] = {'id': 'legacy-review-' + ticket.get('id', ''),
                                'status': 'PENDING', 'owner': '人工复核',
                                'reason': '历史工单的回复未通过合规审核'}
    return ticket


def _rows(db, table):
    return [dict(row) for row in db.execute(f'SELECT * FROM {table} ORDER BY rowid DESC LIMIT 500')]


def workflow_state():
    with LOCK:
        recover_pending()
    with closing(workflow.connect()) as db:
        data = {name: _rows(db, name) for name in ('runs', 'trace', 'tasks', 'artifacts', 'approvals', 'drafts', 'events', 'state_changes', 'consent_changes')}
        data['analysis'] = workflow.analyze(db)
        for artifact in data['artifacts']:
            artifact['review'] = json.loads(artifact['review'])
            try:
                _, recipients, digest = workflow.material(db, artifact['batch_id'], artifact['id'])
                artifact['material_hash'] = digest
                artifact['approval_recipients'] = recipients
            except ValueError:
                artifact['material_hash'] = None
                artifact['approval_recipients'] = None
        for event in data['trace']:
            event['details'] = json.loads(event['details'])
    return data


def state():
    with LOCK:
        recover_pending()
    with closing(workflow.connect()) as db:
        runs = {r['id']: dict(r) for r in db.execute('SELECT id,status,result FROM runs')}
    def run_matches(run_id, kind, ident):
        run = runs.get(run_id)
        if not run or run['status'] in ('RUNNING', 'INTERRUPTED'):
            return False
        try: saved = json.loads(run['result'])
        except (TypeError, ValueError): return False
        if not isinstance(saved, dict): return False
        return saved.get('id') == ident if kind == 'ticket' else Path(saved.get('path', '')).name == ident + '.md'
    tickets = []
    interrupted_artifacts = []
    for path in (ROOT / 'output' / 'tickets').glob('*.json'):
        ticket = _read(path)
        if isinstance(ticket, dict):
            run_id = ticket.get('workflow_run_id')
            if run_id and not run_matches(run_id, 'ticket', ticket.get('id')):
                if runs.get(run_id, {}).get('status') != 'RUNNING':
                    interrupted_artifacts.append({'kind': 'ticket', 'id': ticket.get('id'), 'run_id': run_id,
                                                  'message': ticket.get('message', ''), 'customer_id': ticket.get('parent', '')})
                continue
            _legacy_review_task(ticket)
            decision = ticket.get('gate7_decision') or {}
            ticket['content_hash'] = decision.get('content_hash')
            tickets.append(ticket)
    tickets.sort(key=lambda x: x.get('time', ''), reverse=True)
    packages = []
    for path in (ROOT / 'output' / 'sop_packages').glob('*.md.json'):
        package = _read(path)
        if isinstance(package, dict):
            package['id'] = path.name[:-8]
            run_id = package.get('workflow_run_id')
            if run_id and not run_matches(run_id, 'package', package['id']):
                if runs.get(run_id, {}).get('status') != 'RUNNING':
                    interrupted_artifacts.append({'kind': 'package', 'id': package['id'], 'run_id': run_id, 'day': package.get('day', '')})
                continue
            decision = package.get('decision') or {}
            package['content_hash'] = decision.get('content_hash')
            gate_status = decision.get('status')
            if gate_status == 'APPROVED' and package.get('deliverable'):
                package['status'] = 'READY'
            elif gate_status == 'REJECTED':
                package['status'] = 'REJECTED'
            elif gate_status == 'SIMULATED_APPROVAL':
                package['status'] = 'SIMULATED_APPROVAL'
            elif gate_status == 'PENDING' and package['content_hash']:
                package['status'] = 'PENDING_APPROVAL'
            else:
                package['status'] = 'INCOMPLETE'
            packages.append(package)
    report_path = ROOT / 'hub' / '08-review.md'
    report = report_path.read_text(encoding='utf-8') if report_path.exists() else ''
    pending = sum(t.get('gate7') == 'PENDING' for t in tickets) + sum(p['status'] == 'PENDING_APPROVAL' for p in packages)
    with LOCK:
        jobs = list(JOBS.values())[::-1]
    return {'tickets': tickets, 'packages': packages, 'interrupted_artifacts': interrupted_artifacts, 'report': report,
            'metrics': {'tickets': len(tickets), 'pending_approvals': pending, 'packages': len(packages),
                        'risk': {level: sum(t.get('risk_level') == level for t in tickets) for level in ('L1', 'L2', 'L3')}},
            'sop_days': list(knowledge_base.sop_days()), 'jobs': jobs}


def start_job(kind, payload):
    job_id = uuid.uuid4().hex
    job = {'id': job_id, 'kind': kind, 'status': 'running', 'result': None, 'error': None,
           'events': [{'status': 'running', 'time': time.time()}]}
    with LOCK:
        JOBS[job_id] = job
    def run():
        try:
            env = os.environ.copy()
            env['OPC_WEB_JOB_ID'] = job_id
            proc = subprocess.run([sys.executable, '-m', 'web_api.worker', kind], cwd=ROOT,
                                  input=json.dumps(payload, ensure_ascii=False), text=True,
                                  encoding='utf-8', capture_output=True, timeout=1200, env=env)
            if proc.returncode:
                raise RuntimeError(proc.stderr.strip()[-2000:] or '任务失败')
            result = json.loads(proc.stdout)
            if isinstance(result, dict) and result.get('error'):
                raise RuntimeError(result['error'])
            with LOCK:
                job.update(status='completed', result=result)
        except Exception as exc:
            try:
                interrupt_runs(job_id, '网页后台任务已中断或失败')
            except Exception:
                # Preserve the job failure; startup recovery retries interrupted runs.
                pass
            with LOCK:
                job.update(status='failed', error=str(exc))
        with LOCK:
            job['events'].append({'status': job['status'], 'time': time.time()})
    threading.Thread(target=run, daemon=True).start()
    return {'job_id': job_id, 'status': 'running'}


def interrupt_runs(job_id=None, reason='网页服务重启，中断的任务需要重新运行'):
    """Only web-owned running jobs are affected, not CLI or other workflows."""
    prefix = 'web-' + (job_id + '-' if job_id else '')
    with closing(workflow.connect()) as db, db:
        db.execute('BEGIN IMMEDIATE')
        rows = db.execute("SELECT id FROM runs WHERE status='RUNNING' AND substr(id,1,?)=?", (len(prefix), prefix)).fetchall()
        for row in rows:
            db.execute("UPDATE runs SET status='INTERRUPTED', result=? WHERE id=?",
                       (json.dumps({'error': reason}, ensure_ascii=False), row['id']))
            workflow._trace(db, row['id'], '系统', '中断恢复', 'INTERRUPTED', {'reason': reason})


def _atomic_text(path, text):
    tmp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        tmp.write_text(text, encoding='utf-8')
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def _atomic_json(path, data):
    _atomic_text(path, json.dumps(data, ensure_ascii=False, indent=2))


def _journal_init(db):
    db.execute('CREATE TABLE IF NOT EXISTS web_file_journal (id TEXT PRIMARY KEY, files TEXT NOT NULL)')


def _journal(db, files):
    """Stage file writes alongside run updates in one durable DB transaction."""
    entries = [{'path': str(path), 'content': text} for path, text in files]
    db.execute('INSERT INTO web_file_journal VALUES (?,?)', (uuid.uuid4().hex, json.dumps(entries, ensure_ascii=False)))


def recover_pending():
    """Replay committed operations idempotently; keep failed ones for retry."""
    with closing(workflow.connect()) as db:
        _journal_init(db)
        for row in db.execute('SELECT id, files FROM web_file_journal ORDER BY rowid').fetchall():
            for entry in json.loads(row['files']):
                path = Path(entry['path']).resolve()
                if not path.is_relative_to((ROOT / 'output').resolve()):
                    raise ValueError('无效待恢复文件路径')
                _atomic_text(path, entry['content'])
            with db:
                db.execute('DELETE FROM web_file_journal WHERE id=?', (row['id'],))


def approval(payload):
    kind, ident, decision, expected = (payload.get(k) for k in ('kind', 'id', 'decision', 'content_hash'))
    if kind not in ('ticket', 'package') or decision not in ('approve', 'reject') or not expected:
        raise ValueError('审批参数无效')
    # IDs are filenames, not paths supplied by the client.
    if not isinstance(ident, str) or Path(ident).name != ident or ident in ('.', '..'):
        raise ValueError('无效编号')
    path = ROOT / 'output' / ('tickets' if kind == 'ticket' else 'sop_packages') / (ident + ('.json' if kind == 'ticket' else '.md.json'))
    with LOCK:
        recover_pending()
        obj = _read(path)
        if not isinstance(obj, dict):
            raise ValueError('未找到审批事项')
        status = 'APPROVED' if decision == 'approve' else 'REJECTED'
        if kind == 'ticket':
            gate = obj.get('gate7_decision') or {}
            materials = json.dumps({'reply': obj.get('review_candidate'), 'advice': obj.get('escalation')}, ensure_ascii=False, sort_keys=True)
            review = obj.get('review') or {}
            if gate.get('status') != 'PENDING' or gate.get('content_hash') != expected or compliance.content_hash(materials) != expected:
                raise ValueError('审批材料已变化或不再待审批')
            if status == 'APPROVED' and (review.get('status') != 'PASS' or review.get('reviewed_content_hash') != compliance.content_hash(obj.get('review_candidate', ''))):
                raise ValueError('回复未经当前版本合规审核')
            gate['status'] = status
            obj['gate7'] = status
            obj['gate7_decision'] = gate
            needs_human = (obj.get('human_task') or {}).get('status') == 'PENDING'
            obj['reply'] = obj['review_candidate'] if status == 'APPROVED' and not needs_human else ''
            obj['action'] = '已批准，待人工处理' if status == 'APPROVED' else '已打回，禁止交付'
        else:
            # The persisted markdown is the exact material submitted to gate 4.
            gate = obj.get('decision') or {}
            md = path.with_suffix('').read_text(encoding='utf-8')
            parts = md.split('\n\n', 2)
            if len(parts) != 3 or not re.search(r'状态: [A-Z_]+', parts[1]) or not re.search(r'闸门④: [A-Z_]+', parts[1]):
                raise ValueError('运营包状态头格式无效')
            material = parts[2].rstrip('\n')
            tasks = obj.get('tasks') or []
            if gate.get('status') != 'PENDING' or gate.get('content_hash') != expected or compliance.content_hash(material) != expected:
                raise ValueError('审批材料已变化或不再待审批')
            if not tasks or any(t['review'].get('status') != 'PASS' or t['review'].get('reviewed_content_hash') != compliance.content_hash(t['review'].get('content', '')) for t in tasks):
                raise ValueError('运营包存在未通过审核的任务')
            reconstructed = '\n\n'.join(
                f"## 任务 {i} · {t['task']['time']} / {t['task']['channel']} / {t['task']['audience']}\n"
                f"来源: {t['task']['source']} | 审核: {t['review']['status']}\n\n{t['review']['content']}"
                for i, t in enumerate(tasks, 1))
            if reconstructed != material:
                raise ValueError('运营包正文与已审核任务不一致')
            gate['status'] = status
            obj['decision'] = gate
            obj['deliverable'] = status == 'APPROVED'
            header = re.sub(r'状态: [A-Z_]+', '状态: ' + ('READY' if obj['deliverable'] else 'REJECTED'), parts[1], count=1)
            header = re.sub(r'闸门④: [A-Z_]+', '闸门④: ' + status, header, count=1)
            updated_md = parts[0] + '\n\n' + header + '\n\n' + parts[2]
        if kind == 'ticket':
            # Keep the originating inbound run and its trace aligned with the
            # local ticket after the human decision.
            with closing(workflow.connect()) as db, db:
                _journal_init(db)
                db.execute('BEGIN IMMEDIATE')
                matched = False
                for run in db.execute("SELECT id, result FROM runs WHERE type='INBOUND_MESSAGE'").fetchall():
                    try:
                        saved = json.loads(run['result'])
                    except (TypeError, ValueError):
                        continue
                    if not isinstance(saved, dict) or saved.get('id') != ident:
                        continue
                    if obj.get('workflow_run_id') and run['id'] != obj['workflow_run_id']:
                        continue
                    if (saved.get('gate7_decision') or {}).get('content_hash') != expected or saved.get('gate7') != 'PENDING':
                        continue
                    matched = True
                    run_status = 'DRAFT' if status == 'APPROVED' and not needs_human else 'HUMAN_REVIEW'
                    db.execute('UPDATE runs SET status=?, result=? WHERE id=?',
                               (run_status, json.dumps(obj, ensure_ascii=False), run['id']))
                    workflow._trace(db, run['id'], '老板', '网页审批投诉升级', status,
                                    {'ticket_id': ident, 'content_hash': expected})
                if obj.get('workflow_run_id') and not matched:
                    raise ValueError('工作流结果尚未就绪或审批材料已变化，请刷新后重试')
                _journal(db, [(path, json.dumps(obj, ensure_ascii=False, indent=2))])
        else:
            with closing(workflow.connect()) as db, db:
                _journal_init(db)
                db.execute('BEGIN IMMEDIATE')
                matched = False
                # SOP paths are reused for each day. Update only the latest
                # matching pending run for this exact reviewed content.
                for run in db.execute("SELECT id, result FROM runs WHERE type='DAILY_SOP' ORDER BY rowid DESC").fetchall():
                    try:
                        saved = json.loads(run['result'])
                    except (TypeError, ValueError):
                        continue
                    if not isinstance(saved, dict) or Path(saved.get('path', '')).name != ident + '.md':
                        continue
                    if obj.get('workflow_run_id') and run['id'] != obj['workflow_run_id']:
                        continue
                    if saved.get('gate4') != 'PENDING' or compliance.content_hash(saved.get('content', '')) != expected:
                        continue
                    matched = True
                    saved.update(gate4=status, decision=gate, deliverable=obj['deliverable'],
                                 status='READY' if status == 'APPROVED' else 'REJECTED')
                    db.execute('UPDATE runs SET status=?, result=? WHERE id=?',
                               (saved['status'], json.dumps(saved, ensure_ascii=False), run['id']))
                    workflow._trace(db, run['id'], '老板', '网页审批运营包', status,
                                    {'content_hash': expected, 'path': saved['path']})
                    break
                if obj.get('workflow_run_id') and not matched:
                    raise ValueError('工作流结果尚未就绪或审批材料已变化，请刷新后重试')
                _journal(db, [(path.with_suffix(''), updated_md), (path, json.dumps(obj, ensure_ascii=False, indent=2))])
        recover_pending()
        log_action('网页审批', ident, f'{status} / 材料哈希 {expected}', status='GATE')
        return obj


def resolve_human_task(payload):
    ident, result = payload.get('id'), payload.get('result')
    if not isinstance(ident, str) or Path(ident).name != ident or ident in ('', '.', '..'):
        raise ValueError('无效工单编号')
    if not isinstance(result, str) or not result.strip() or len(result) > 5000:
        raise ValueError('请输入不超过 5000 字的处理结果')
    path = ROOT / 'output' / 'tickets' / (ident + '.json')
    with LOCK:
        recover_pending()
        ticket = _read(path)
        if not isinstance(ticket, dict): raise ValueError('未找到工单')
        _legacy_review_task(ticket)
        task = ticket.get('human_task') or {}
        if task.get('status') != 'PENDING': raise ValueError('人工任务不存在或已经处理')
        if ticket.get('risk_level') == 'L3' and ticket.get('gate7') not in ('APPROVED', 'REJECTED', 'REVIEW_REQUIRED'):
            raise ValueError('请先完成高风险事项的审批或打回')
        task.update(status='COMPLETED', result=result.strip(), completed_at=datetime.now().isoformat(timespec='seconds'))
        ticket['human_task'] = task
        ticket['action'] = '人工处理已记录，未发送'
        ticket['reply'] = ''
        with closing(workflow.connect()) as db, db:
            _journal_init(db)
            db.execute('BEGIN IMMEDIATE')
            matched = False
            for run in db.execute("SELECT id, result FROM runs WHERE type='INBOUND_MESSAGE'").fetchall():
                try: saved = json.loads(run['result'])
                except (TypeError, ValueError): continue
                if not isinstance(saved, dict) or saved.get('id') != ident: continue
                if ticket.get('workflow_run_id') and run['id'] != ticket['workflow_run_id']: continue
                _legacy_review_task(saved)
                if (saved.get('human_task') or {}).get('status') != 'PENDING': continue
                matched = True
                db.execute('UPDATE runs SET status=?, result=? WHERE id=?',
                           ('RESOLVED', json.dumps(ticket, ensure_ascii=False), run['id']))
                workflow._trace(db, run['id'], '人工处理', '记录处理结果', 'COMPLETED',
                                {'ticket_id': ident, 'result': result.strip(), 'delivery': 'NOT_SENT'})
            if ticket.get('workflow_run_id') and not matched:
                raise ValueError('工作流结果尚未就绪或人工任务已变化，请刷新后重试')
            _journal(db, [(path, json.dumps(ticket, ensure_ascii=False, indent=2))])
        recover_pending()
        log_action('人工处理', ident, result.strip(), status='COMPLETED')
        return ticket


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, data):
        content = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(content)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(content)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        try:
            path = urlparse(self.path).path
            # Vite production output; source JSX is served only by the dev server.
            if path in ('/', '/index.html') or path.startswith('/assets/'):
                dist = (ROOT / 'web' / 'dist').resolve()
                file = (dist / ('index.html' if path in ('/', '/index.html') else path.lstrip('/'))).resolve()
                if file != dist and dist not in file.parents:
                    return self._send(404, {'error': '页面不存在'})
                if not file.is_file():
                    return self._send(503 if path in ('/', '/index.html') else 404,
                                      {'error': '缺少 React 构建文件；请在 junction/web 运行 npm install && npm run build'})
                content = file.read_bytes()
                mime = mimetypes.guess_type(file.name)[0] or 'application/octet-stream'
                self.send_response(200)
                self.send_header('Content-Type', mime + ('; charset=utf-8' if mime.startswith('text/') or mime == 'application/javascript' else ''))
                self.send_header('Content-Length', str(len(content)))
                self.send_header('Cache-Control', 'no-cache' if path in ('/', '/index.html') else 'public, max-age=31536000, immutable')
                self.end_headers()
                self.wfile.write(content)
                return
            if path == '/api/state': return self._send(200, state())
            if path == '/api/workflow': return self._send(200, workflow_state())
            if path.startswith('/api/jobs/'):
                with LOCK: job = JOBS.get(path.rsplit('/', 1)[-1])
                return self._send(200, job) if job else self._send(404, {'error': '任务不存在'})
            return self._send(404, {'error': '未找到接口'})
        except Exception as exc:
            return self._send(500, {'error': str(exc)})

    def do_POST(self):
        try:
            if self.headers.get_content_type() != 'application/json':
                return self._send(415, {'error': '请求必须为 JSON'})
            length = int(self.headers.get('Content-Length', '0'))
            if length > 65536: return self._send(413, {'error': '请求过大'})
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict): raise ValueError('请求必须是对象')
            path = urlparse(self.path).path
            if path == '/api/approvals': return self._send(200, approval(payload))
            if path == '/api/human-tasks': return self._send(200, resolve_human_task(payload))
            if path in ('/api/customers/stage', '/api/customers/consent'):
                with closing(workflow.connect()) as db:
                    if path.endswith('/stage'):
                        workflow.change_stage(db, payload.get('customer_id'), payload.get('stage'), payload.get('reason', ''))
                    else:
                        workflow.change_consent(db, payload.get('customer_id'), payload.get('consent'), payload.get('source', ''))
                return self._send(200, {'status': 'UPDATED'})
            endpoints = {'/api/service': 'service', '/api/sop': 'sop', '/api/report': 'report'}
            endpoints.update({f'/api/workflow/{key}': 'workflow-' + key for key in ('seed', 'plan', 'plan-content', 'content', 'approve', 'queue', 'receipt')})
            if path not in endpoints: return self._send(404, {'error': '未找到接口'})
            return self._send(202, start_job(endpoints[path], payload))
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            return self._send(400, {'error': str(exc)})
        except Exception as exc:
            return self._send(500, {'error': str(exc)})


def main():
    server = ThreadingHTTPServer(('127.0.0.1', 8765), Handler)
    with LOCK:
        recover_pending()
        interrupt_runs()
    print('OPC API: http://127.0.0.1:8765', flush=True)
    server.serve_forever()


if __name__ == '__main__': main()
