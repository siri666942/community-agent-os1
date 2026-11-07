"""受约束的双 Agent 跟进工作流。所有触达均为本地草稿或模拟回执。"""
import argparse
import hashlib
import json
import os
import sqlite3
import uuid
from datetime import date, datetime, timedelta

from . import config
from .agents import compliance, prompts
from .llm import chat

DB_PATH = os.path.join(config.OUTPUT_DIR, 'workflow.sqlite3')


def connect(path=DB_PATH):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.executescript('''
    CREATE TABLE IF NOT EXISTS customers(id TEXT PRIMARY KEY, stage TEXT NOT NULL, consent INTEGER NOT NULL, contact_limit INTEGER NOT NULL, source TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY, customer_id TEXT NOT NULL REFERENCES customers(id), type TEXT NOT NULL, occurred_at TEXT NOT NULL, source TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY, batch_id TEXT NOT NULL, customer_id TEXT NOT NULL REFERENCES customers(id), owner TEXT NOT NULL, action TEXT NOT NULL, reason TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS artifacts(id TEXT PRIMARY KEY, batch_id TEXT NOT NULL, content TEXT NOT NULL, content_hash TEXT NOT NULL, review TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS approvals(batch_id TEXT PRIMARY KEY, material_hash TEXT NOT NULL, status TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS drafts(id TEXT PRIMARY KEY, task_id TEXT UNIQUE NOT NULL REFERENCES tasks(id), artifact_id TEXT NOT NULL REFERENCES artifacts(id), content_hash TEXT NOT NULL, status TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, type TEXT NOT NULL, status TEXT NOT NULL, input_ref TEXT NOT NULL, result TEXT NOT NULL DEFAULT '{}');
    CREATE TABLE IF NOT EXISTS trace(seq INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, at TEXT NOT NULL, owner TEXT NOT NULL, action TEXT NOT NULL, status TEXT NOT NULL, details TEXT NOT NULL);
<<<<<<< HEAD
=======
    CREATE TABLE IF NOT EXISTS consent_changes(id TEXT PRIMARY KEY, customer_id TEXT NOT NULL REFERENCES customers(id), consent INTEGER NOT NULL, source TEXT NOT NULL, at TEXT NOT NULL);
>>>>>>> 63625db7de08473c3560290102df65491798ed49
    CREATE TABLE IF NOT EXISTS state_changes(id TEXT PRIMARY KEY, customer_id TEXT NOT NULL REFERENCES customers(id), old_stage TEXT NOT NULL, new_stage TEXT NOT NULL, reason TEXT NOT NULL, at TEXT NOT NULL);
    ''')
    return db


def _id(prefix):
    return prefix + uuid.uuid4().hex[:12]


def _run_id(prefix):
    job = os.environ.get('OPC_WEB_JOB_ID', '')
    if len(job) == 32 and all(char in '0123456789abcdef' for char in job):
        return 'web-' + job + '-' + _id(prefix)
    return _id(prefix)


def _trace(db, run_id, owner, action, status, details=None):
    db.execute('INSERT INTO trace(run_id,at,owner,action,status,details) VALUES (?,?,?,?,?,?)',
               (run_id, datetime.now().isoformat(timespec='seconds'), owner, action, status,
                json.dumps(details or {}, ensure_ascii=False, sort_keys=True)))


def seed_demo(db, today=None):
    """明确标注模拟数据；重复调用不重复导入。"""
    today = today or date.today()
    with db:
        for i in range(1, 31):
            cid = f'demo-{i:03}'
            db.execute('INSERT OR IGNORE INTO customers VALUES (?,?,?,?,?)', (cid, '训练营', int(i % 5 != 0), 2, '模拟'))
            db.execute('INSERT OR IGNORE INTO events VALUES (?,?,?,?,?)',
                       (f'seed-{i:03}', cid, 'interaction', (today - timedelta(days=i % 7)).isoformat(), '模拟'))


def analyze(db, today=None):
    """数据增长 Agent：三天未互动，以最近七天模拟回执计接触次数；返回完整可复算依据。"""
    today = today or date.today()
    rows = db.execute('SELECT * FROM customers ORDER BY id').fetchall()
    results = []
    for customer in rows:
        last = db.execute("SELECT MAX(occurred_at) FROM events WHERE customer_id=? AND type='interaction' AND occurred_at<=?", (customer['id'], today.isoformat())).fetchone()[0]
        count = db.execute("SELECT COUNT(*) FROM events WHERE customer_id=? AND type='simulated_delivery' AND occurred_at BETWEEN ? AND ?", (customer['id'], (today - timedelta(days=6)).isoformat(), today.isoformat())).fetchone()[0]
        inactive = last is None or date.fromisoformat(last) <= today - timedelta(days=3)
        results.append({'customer_id': customer['id'], 'source': customer['source'], 'stage': customer['stage'], 'last_interaction': last,
                        'inactive_3d': inactive, 'consent': bool(customer['consent']),
                        'contacts_7d': count, 'contact_limit': customer['contact_limit']})
    return {'as_of': today.isoformat(), 'definition': '最近互动日期距统计日至少3天，或无互动记录；触达次数为近7天模拟回执',
            'customers': results, 'total': len(results), 'inactive': sum(r['inactive_3d'] for r in results)}


def plan(db, today=None):
    """数据增长 Agent：只基于已知行为和许可制订任务，不推断隐私属性。"""
    today = today or date.today()
    snapshot = analyze(db, today)
    batch = _id('batch-')
    with db:
        db.execute('INSERT INTO runs(id,type,status,input_ref) VALUES (?,?,?,?)', (batch, 'FOLLOWUP_BATCH', 'PLANNED', snapshot['as_of']))
        _trace(db, batch, prompts.GROWTH_AGENT, '计算分层', 'COMPLETE', snapshot)
        for row in snapshot['customers']:
            if not row['inactive_3d'] or row['stage'] != '训练营':
                continue
            if not row['consent']:
                action, reason = '暂停触达', '未记录触达同意'
            elif row['contacts_7d'] >= row['contact_limit']:
                action, reason = '人工复核', '近七日接触次数达到上限'
            else:
                action, reason = '温和提醒', '至少三天未互动且满足触达条件'
            db.execute('INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?)',
                       (_id('task-'), batch, row['customer_id'], prompts.GROWTH_AGENT, action, reason,
                        'WAITING_CONTENT' if action == '温和提醒' else 'HUMAN_REVIEW' if action == '人工复核' else 'PAUSED', today.isoformat()))
        _trace(db, batch, prompts.GROWTH_AGENT, '创建跟进任务', 'COMPLETE', {'count': len(tasks(db, batch))})
    return {'batch_id': batch, 'snapshot': snapshot, 'tasks': tasks(db, batch)}


def tasks(db, batch):
    return [dict(r) for r in db.execute('SELECT * FROM tasks WHERE batch_id=? ORDER BY customer_id', (batch,))]


def create_content(db, batch):
    """服务运营 Agent 生成内容并在独立步骤审查，失败不放行；重复生成产生新产物并撤销审批。"""
    if not any(t['status'] == 'WAITING_CONTENT' for t in tasks(db, batch)):
        raise ValueError('没有等待内容的提醒任务')
    draft = chat(prompts.BRAND_CONTEXT + '\n角色：服务运营 Agent，当前执行内容生成步骤。为三天未互动家长写一条温和提醒，不暗示效果或优惠，不催付。只输出话术。',
                 '场景：训练营阅读提醒。不要假设用户的原因或个人情况。', agent=prompts.SERVICE_AGENT, input_summary=batch)
    review = compliance.review_loop(draft, context='训练营三天未互动，温和提醒')
    artifact = _id('artifact-')
    if db.in_transaction:
        raise ValueError('请先完成当前事务再保存内容')
    db.execute('BEGIN IMMEDIATE')
    try:
        if not any(t['status'] == 'WAITING_CONTENT' for t in tasks(db, batch)):
            raise ValueError('任务状态已变化，无法保存内容')
        db.execute('INSERT INTO artifacts VALUES (?,?,?,?,?)', (artifact, batch, review['content'], compliance.content_hash(review['content']), json.dumps(review, ensure_ascii=False)))
        db.execute('DELETE FROM approvals WHERE batch_id=?', (batch,))
        _trace(db, batch, prompts.SERVICE_AGENT, '生成内容', 'COMPLETE', {'artifact_id': artifact})
        _trace(db, batch, prompts.SERVICE_AGENT, '审核内容', review['status'], {'artifact_id': artifact, 'review': review})
        db.commit()
    except BaseException:
        db.rollback()
        raise
    return {'artifact_id': artifact, 'review': review}


def material(db, batch, artifact):
    row = db.execute('SELECT * FROM artifacts WHERE id=? AND batch_id=?', (artifact, batch)).fetchone()
    if row is None:
        raise ValueError('找不到产物')
    review = json.loads(row['review'])
    if review.get('status') != 'PASS' or review.get('reviewed_content_hash') != compliance.content_hash(row['content']) or row['content_hash'] != compliance.content_hash(row['content']):
        raise ValueError('内容未通过与当前版本绑定的审核')
    recipients = [t['customer_id'] for t in tasks(db, batch) if t['status'] == 'WAITING_CONTENT']
    if not recipients:
        raise ValueError('没有待发送对象')
    payload = json.dumps({'batch': batch, 'artifact': artifact, 'content': row['content'], 'recipients': recipients}, ensure_ascii=False, sort_keys=True)
    return row, recipients, hashlib.sha256(payload.encode()).hexdigest()


def approve(db, batch, artifact, decision, expected_hash=None):
    """调用者须明确选择 APPROVED；模拟批准永不等于真实授权。"""
    if decision not in ('APPROVED', 'REJECTED', 'SIMULATED_APPROVAL'):
        raise ValueError('无效审批决定')
    if db.in_transaction:
        raise ValueError('请先完成当前事务再审批')
    db.execute('BEGIN IMMEDIATE')
    try:
        _, recipients, digest = material(db, batch, artifact)
        if expected_hash is not None and expected_hash != digest:
            raise ValueError('审批材料已变化，请重新查看')
        db.execute('INSERT OR REPLACE INTO approvals VALUES (?,?,?)', (batch, digest, decision))
        _trace(db, batch, '老板', '审批正文与名单', decision, {'artifact_id': artifact, 'material_hash': digest, 'recipients': recipients})
        db.commit()
    except BaseException:
        db.rollback()
        raise
    return {'status': decision, 'material_hash': digest}


def queue_drafts(db, batch, artifact):
    """服务运营 Agent 写入本地草稿；审批绑定正文和名单，重新校验当前许可和频次。"""
    if db.in_transaction:
        raise ValueError('请先完成当前事务再创建草稿')
    db.execute('BEGIN IMMEDIATE')
    try:
        row, recipients, digest = material(db, batch, artifact)
        approval = db.execute('SELECT * FROM approvals WHERE batch_id=?', (batch,)).fetchone()
        if not approval or approval['status'] != 'APPROVED' or approval['material_hash'] != digest:
            raise ValueError('需要针对当前正文和名单的明确批准')
        current = {r['customer_id']: r for r in analyze(db)['customers']}
        if any(not current[c]['consent'] or current[c]['stage'] != '训练营' or current[c]['contacts_7d'] >= current[c]['contact_limit'] or not current[c]['inactive_3d'] for c in recipients):
            raise ValueError('客户状态或触达条件已变化，请重新规划和审批')
        for task in tasks(db, batch):
            if task['status'] == 'WAITING_CONTENT':
                db.execute('INSERT INTO drafts VALUES (?,?,?,?,?)', (_id('draft-'), task['id'], artifact, row['content_hash'], 'DRAFT'))
                db.execute("UPDATE tasks SET status='DRAFT' WHERE id=?", (task['id'],))
        db.execute("UPDATE runs SET status='DRAFT' WHERE id=?", (batch,))
        _trace(db, batch, prompts.SERVICE_AGENT, '创建本地草稿', 'DRAFT', {'artifact_id': artifact, 'recipients': recipients})
        db.commit()
    except BaseException:
        db.rollback()
        raise
    return len(recipients)


def simulate_receipt(db, draft_id, today=None):
    """仅记录模拟送达，绝不调用外部渠道；相同草稿不可重复记录。"""
    today = today or date.today()
    if db.in_transaction:
        raise ValueError('请先完成当前事务再记录模拟回执')
    # 抢占写锁后再读取条件，避免并发回执同时通过频次和状态检查。
    db.execute('BEGIN IMMEDIATE')
    try:
        row = db.execute('SELECT d.*, t.customer_id, t.batch_id FROM drafts d JOIN tasks t ON t.id=d.task_id WHERE d.id=?', (draft_id,)).fetchone()
        if not row or row['status'] != 'DRAFT':
            raise ValueError('草稿不存在或已有回执')
        customer = next((item for item in analyze(db, today)['customers'] if item['customer_id'] == row['customer_id']), None)
        if (not customer or not customer['consent'] or customer['stage'] != '训练营'
                or customer['contacts_7d'] >= customer['contact_limit'] or not customer['inactive_3d']):
            raise ValueError('客户状态或触达条件已变化，不能记录模拟回执')
        db.execute('INSERT INTO events VALUES (?,?,?,?,?)', (_id('event-'), row['customer_id'], 'simulated_delivery', today.isoformat(), '模拟'))
        db.execute("UPDATE drafts SET status='SIMULATED_DELIVERY' WHERE id=?", (draft_id,))
        db.execute("UPDATE tasks SET status='SIMULATED_DELIVERY' WHERE id=?", (row['task_id'],))
        _trace(db, row['batch_id'], prompts.SERVICE_AGENT, '记录模拟回执', 'SIMULATED_DELIVERY', {'draft_id': draft_id, 'customer_id': row['customer_id']})
        db.commit()
    except BaseException:
        db.rollback()
        raise


def inbound(db, customer_id, message, message_id=None, *, auto=False):
    """入站消息去重并登记，再调用现有客服流程；异常保留可追踪的失败任务。"""
    from .agents import frontdesk
    if not message.strip():
        raise ValueError('消息不能为空')
<<<<<<< HEAD
    if not db.execute('SELECT 1 FROM customers WHERE id=?', (customer_id,)).fetchone():
=======
    customer = db.execute('SELECT source FROM customers WHERE id=?', (customer_id,)).fetchone()
    if not customer:
>>>>>>> 63625db7de08473c3560290102df65491798ed49
        raise ValueError('客户不存在')
    message_id = message_id or _id('message-')
    run_id = _run_id('inbound-')
    with db:
<<<<<<< HEAD
        db.execute('INSERT INTO events VALUES (?,?,?,?,?)', (message_id, customer_id, 'interaction', date.today().isoformat(), '入站消息'))
=======
        db.execute('INSERT INTO events VALUES (?,?,?,?,?)', (message_id, customer_id, 'interaction', date.today().isoformat(), '模拟入站消息' if customer['source'] == '模拟入站消息' else '入站消息'))
>>>>>>> 63625db7de08473c3560290102df65491798ed49
        db.execute('INSERT INTO runs(id,type,status,input_ref) VALUES (?,?,?,?)', (run_id, 'INBOUND_MESSAGE', 'RUNNING', message_id))
        _trace(db, run_id, 'COO', '登记入站消息', 'RUNNING', {'customer_id': customer_id, 'message_id': message_id})
    try:
        ticket = frontdesk.handle(message, parent=customer_id, auto=auto, workflow_run_id=run_id)
    except Exception as exc:
        with db:
            changed = db.execute("UPDATE runs SET status='REVIEW_REQUIRED', result=? WHERE id=? AND status='RUNNING'", (json.dumps({'error': str(exc)}, ensure_ascii=False), run_id)).rowcount
            if not changed: return {'run_id': run_id, 'status': 'INTERRUPTED', 'error': '任务已中断'}
            _trace(db, run_id, prompts.SERVICE_AGENT, '处理消息', 'REVIEW_REQUIRED', {'error': str(exc)})
        return {'run_id': run_id, 'status': 'REVIEW_REQUIRED', 'error': str(exc)}
    status = 'HUMAN_REVIEW' if ticket.get('human_task') or ticket['review']['status'] != 'PASS' else 'DRAFT'
    with db:
        changed = db.execute("UPDATE runs SET status=?, result=? WHERE id=? AND status='RUNNING'", (status, json.dumps(ticket, ensure_ascii=False), run_id)).rowcount
        if not changed: return {'run_id': run_id, 'status': 'INTERRUPTED', 'error': '任务已中断'}
        _trace(db, run_id, prompts.SERVICE_AGENT, '创建工单', status, {'ticket_id': ticket['id'], 'risk_level': ticket['risk_level'], 'human_task': ticket.get('human_task')})
        _trace(db, run_id, prompts.SERVICE_AGENT, '审核回复', ticket['review']['status'], {'review': ticket['review']})
        if ticket.get('gate7_decision'):
            _trace(db, run_id, '老板', '投诉升级审批', ticket['gate7'], ticket['gate7_decision'])
    return {'run_id': run_id, 'status': status, 'ticket': ticket}


def sop_run(db, day, *, auto=False):
    """将现有逐条 SOP 流程登记在共享状态中，不把模拟审批视作真实发布。"""
    from .agents import sop_pipeline
    run_id = _run_id('sop-')
    with db:
        db.execute('INSERT INTO runs(id,type,status,input_ref) VALUES (?,?,?,?)', (run_id, 'DAILY_SOP', 'RUNNING', day))
        _trace(db, run_id, 'COO', '拆分 SOP', 'RUNNING', {'day': day})
    try:
        package = sop_pipeline.daily_package(day, auto=auto, workflow_run_id=run_id)
    except Exception as exc:
        with db:
            changed = db.execute("UPDATE runs SET status='REVIEW_REQUIRED', result=? WHERE id=? AND status='RUNNING'", (json.dumps({'error': str(exc)}, ensure_ascii=False), run_id)).rowcount
            if not changed: return {'run_id': run_id, 'status': 'INTERRUPTED', 'error': '任务已中断'}
            _trace(db, run_id, prompts.SERVICE_AGENT, '生成运营包', 'REVIEW_REQUIRED', {'error': str(exc)})
        return {'run_id': run_id, 'status': 'REVIEW_REQUIRED', 'error': str(exc)}
    with db:
        changed = db.execute("UPDATE runs SET status=?, result=? WHERE id=? AND status='RUNNING'", (package['status'], json.dumps(package, ensure_ascii=False), run_id)).rowcount
        if not changed: return {'run_id': run_id, 'status': 'INTERRUPTED', 'error': '任务已中断'}
        for item in package['tasks']:
            _trace(db, run_id, prompts.SERVICE_AGENT, '生成 SOP 条目', 'COMPLETE' if item['review']['content'] else 'REVIEW_REQUIRED', {'task': item['task']})
            _trace(db, run_id, prompts.SERVICE_AGENT, '审核 SOP 条目', item['review']['status'], {'source': item['task']['source'], 'review': item['review']})
        _trace(db, run_id, '老板', '发布审批', package['gate4'], {'path': package['path']})
    return {'run_id': run_id, 'status': package['status'], 'package': package}


def change_stage(db, customer_id, new_stage, reason):
    """仅记录有明确人工依据的阶段变更，不从生成文本推断客户状态。"""
    if new_stage not in ('承接期', '训练营', '已结束') or not reason.strip():
        raise ValueError('无效阶段或缺少变更依据')
    if db.in_transaction:
        raise ValueError('请先完成当前事务再变更阶段')
    db.execute('BEGIN IMMEDIATE')
    try:
        row = db.execute('SELECT stage FROM customers WHERE id=?', (customer_id,)).fetchone()
        if not row:
            raise ValueError('客户不存在')
        db.execute('UPDATE customers SET stage=? WHERE id=?', (new_stage, customer_id))
        db.execute('INSERT INTO state_changes VALUES (?,?,?,?,?,?)', (_id('state-'), customer_id, row['stage'], new_stage, reason, datetime.now().isoformat(timespec='seconds')))
        db.commit()
    except BaseException:
        db.rollback()
        raise


<<<<<<< HEAD
=======

def change_consent(db, customer_id, consent, source):
    """Record an explicit human-supplied consent source or withdrawal."""
    if not isinstance(consent, bool) or not isinstance(source, str) or not source.strip():
        raise ValueError('请选择授权状态并填写来源或撤销依据')
    with db:
        if not db.execute('UPDATE customers SET consent=? WHERE id=?', (int(consent), customer_id)).rowcount:
            raise ValueError('客户不存在')
        db.execute('INSERT INTO consent_changes VALUES (?,?,?,?,?)',
                   (_id('consent-'), customer_id, int(consent), source.strip(), datetime.now().isoformat(timespec='seconds')))

>>>>>>> 63625db7de08473c3560290102df65491798ed49
def main():
    parser = argparse.ArgumentParser(description='双 Agent 受控工作流（本地草稿，不发送消息）')
    parser.add_argument('action', choices=['seed', 'analyze', 'plan', 'content', 'approve', 'queue', 'list', 'receipt', 'inbound', 'sop', 'stage'])
    parser.add_argument('--db', default=DB_PATH)
    parser.add_argument('--batch')
    parser.add_argument('--artifact')
    parser.add_argument('--draft')
    parser.add_argument('--decision', choices=['APPROVED', 'REJECTED', 'SIMULATED_APPROVAL'])
    parser.add_argument('--material-hash', help='查看待审批内容和名单时返回的 material_hash')
    parser.add_argument('--customer')
    parser.add_argument('--message')
    parser.add_argument('--message-id')
    parser.add_argument('--day')
    parser.add_argument('--stage')
    parser.add_argument('--reason')
    parser.add_argument('--simulate-approval', action='store_true')
    args = parser.parse_args()
    with connect(args.db) as db:
        if args.action == 'seed': result = seed_demo(db) or {'status': '已导入模拟数据'}
        elif args.action == 'analyze': result = analyze(db)
        elif args.action == 'plan': result = plan(db)
        elif args.action == 'content': result = create_content(db, args.batch)
        elif args.action == 'approve':
            if not args.material_hash: raise ValueError('请先查看材料并提供 --material-hash')
            result = approve(db, args.batch, args.artifact, args.decision, expected_hash=args.material_hash)
        elif args.action == 'queue': result = {'drafts': queue_drafts(db, args.batch, args.artifact)}
        elif args.action == 'list':
            result = {'tasks': tasks(db, args.batch),
                      'artifacts': [dict(r) for r in db.execute('SELECT id, batch_id, content, content_hash, review FROM artifacts WHERE batch_id=?', (args.batch,))],
                      'drafts': [dict(r) for r in db.execute('SELECT d.* FROM drafts d JOIN tasks t ON t.id=d.task_id WHERE t.batch_id=?', (args.batch,))],
                      'run': dict(db.execute('SELECT * FROM runs WHERE id=?', (args.batch,)).fetchone() or {}),
                      'trace': [dict(r) for r in db.execute('SELECT * FROM trace WHERE run_id=? ORDER BY seq', (args.batch,))]}
            for item in result['artifacts']:
                try:
                    _, item['approval_recipients'], item['material_hash'] = material(db, args.batch, item['id'])
                except ValueError:
                    item['approval_recipients'], item['material_hash'] = None, None
        elif args.action == 'receipt': result = simulate_receipt(db, args.draft) or {'status': 'SIMULATED_DELIVERY'}
        elif args.action == 'inbound': result = inbound(db, args.customer, args.message or '', args.message_id, auto=args.simulate_approval)
        elif args.action == 'sop': result = sop_run(db, args.day, auto=args.simulate_approval)
        else: result = change_stage(db, args.customer, args.stage, args.reason or '') or {'status': 'UPDATED'}
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
