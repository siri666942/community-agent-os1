"""Move only prepared demo dates to a new demonstration day, preserving imported/live data."""
from datetime import timedelta
import argparse

from .db import now, transaction, backend
from .setup_demo import DEMO, PEOPLE
from .demo_data import group_messages


def reanchor():
    with transaction() as conn, conn.cursor() as cur:
        if backend() == 'sqlite':
            cur.execute("SELECT message_id,created_at FROM messages WHERE source_system='opsie_demo_seed'")
            items = cur.fetchall()
            if not items:
                raise RuntimeError('没有可调整的演示背景消息')
            offset = now() - timedelta(minutes=5) - max(row['created_at'] for row in items)
            for row in items:
                shifted = row['created_at'] + offset
                cur.execute('UPDATE messages SET created_at=%s WHERE message_id=%s', (shifted, row['message_id']))
                cur.execute('UPDATE opsie_inbound_reviews SET effective_time=%s WHERE message_key=%s', (shifted, 'm:' + str(row['message_id'])))
            cur.execute('UPDATE opsie_demo SET created_at=%s WHERE demo_key=%s', (now(), DEMO))
            cur.execute('UPDATE conversations SET last_message_at=(SELECT MAX(created_at) FROM messages WHERE messages.conversation_id=conversations.conversation_id)')
            print('演示背景时间已调整，现场新消息保持不变。')
            return
        cur.execute("SELECT * FROM opsie_demo WHERE demo_key=%s FOR UPDATE", (DEMO,))
        demo = cur.fetchone()
        if not demo:
            raise RuntimeError("请先初始化演示数据")
        cur.execute("SELECT MAX(created_at) AS latest FROM messages WHERE conversation_id=%s", (demo["source_group_id"],))
        latest = cur.fetchone()["latest"]
        if not latest:
            raise RuntimeError("来源群没有历史消息")
        offset = int(((now() - timedelta(minutes=30)) - latest).total_seconds())
        cur.execute("UPDATE opsie_demo SET offset_seconds=%s,created_at=%s WHERE demo_key=%s", (offset, now(), DEMO))
        for index, (_, uid, _, _) in enumerate(PEOPLE[1:]):
            cur.execute("UPDATE messages SET created_at=%s WHERE source_system='opsie_demo_seed' AND external_message_id=%s",
                        (now() - timedelta(minutes=20-index*3), f"{DEMO}-seed-{uid}"))
        cur.execute("UPDATE messages SET created_at=%s WHERE source_system='opsie_demo_seed' AND external_message_id=%s",
                    (now() - timedelta(minutes=5), f"{DEMO}-seed-followup-198"))
        cur.execute("UPDATE opsie_inbound_reviews r JOIN messages m ON r.message_key=CONCAT('m:',m.message_id) "
                    "SET r.effective_time=m.created_at WHERE m.source_system='opsie_demo_seed' AND m.external_message_id LIKE %s",
                    (DEMO + '-seed%',))
        cur.execute("UPDATE opsie_inbound_reviews r JOIN messages m ON r.message_key=CONCAT('h:',m.message_id) "
                    "SET r.effective_time=DATE_ADD(m.created_at,INTERVAL %s SECOND) "
                    "WHERE r.conversation_id=%s AND m.conversation_id=%s",
                    (offset, demo["group_id"], demo["source_group_id"]))
        cur.execute("SELECT created_at FROM opsie_demo WHERE demo_key=%s", (DEMO,))
        for message in group_messages(cur.fetchone()['created_at']):
            cur.execute("UPDATE opsie_inbound_reviews SET effective_time=%s WHERE message_key=%s AND conversation_id=%s",
                        (message['time'], message['id'], demo['group_id']))
    print("演示时间已调整；原始群记录和现场新消息未改动。请重启服务以预处理当前演示日的消息。")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--new-day", action="store_true", help="explicitly start a new demo day")
    args = parser.parse_args()
    if not args.new_day:
        parser.error("use --new-day to explicitly move the demo timeline")
    reanchor()
