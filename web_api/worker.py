"""One isolated web job. The JSON request consumes stdin before CLI gates run."""
import contextlib
import json
import sys
import uuid

from opc import workflow
from opc.agents import frontdesk, report


def execute(kind, data):
    if kind == 'service':
        message = data.get('message', '').strip()
        if not message: raise ValueError('请输入家长消息')
        customer_id = data.get('customer_id')
        with workflow.connect() as db:
            if customer_id:
                if not db.execute('SELECT 1 FROM customers WHERE id=?', (customer_id,)).fetchone():
                    raise ValueError('所选客户不存在')
            else:
                customer_id = 'inbound-' + uuid.uuid4().hex[:12]
                with db:
                    db.execute('INSERT INTO customers VALUES (?,?,?,?,?)',
                               (customer_id, '未确认', 0, 0, '模拟入站消息' if data.get('demo') is True else '入站消息'))
            return workflow.inbound(db, customer_id, message)
    if kind == 'sop':
        day = data.get('day', '').strip()
        if not day: raise ValueError('请选择营期日')
        with workflow.connect() as db: return workflow.sop_run(db, day)
    if kind == 'report': return {'report': report.weekly_report()}
    with workflow.connect() as db:
        if kind == 'workflow-seed':
            workflow.seed_demo(db)
            return {'status': '已导入模拟数据'}
        if kind == 'workflow-plan': return workflow.plan(db)
        if kind == 'workflow-plan-content':
            result = workflow.plan(db)
            if any(t['status'] == 'WAITING_CONTENT' for t in result['tasks']):
                result['content'] = workflow.create_content(db, result['batch_id'])
            return result
        if kind == 'workflow-content': return workflow.create_content(db, data['batch_id'])
        if kind == 'workflow-approve':
            if data.get('decision') not in ('APPROVED', 'REJECTED'):
                raise ValueError('请选择批准或打回')
            expected = data.get('material_hash')
            if not isinstance(expected, str) or not expected:
                raise ValueError('缺少审批材料哈希')
            return workflow.approve(db, data['batch_id'], data['artifact_id'], data['decision'], expected_hash=expected)
        if kind == 'workflow-queue': return {'drafts': workflow.queue_drafts(db, data['batch_id'], data['artifact_id'])}
        if kind == 'workflow-receipt':
            workflow.simulate_receipt(db, data['draft_id'])
            return {'status': 'SIMULATED_DELIVERY'}
    raise ValueError('未知任务')


def main():
    payload = json.load(sys.stdin)
    with contextlib.redirect_stdout(sys.stderr):
        result = execute(sys.argv[1], payload)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__': main()
