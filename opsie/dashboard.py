"""Explainable indicators over the same messages used by chat."""
from datetime import timedelta
import json
from . import repository, policy
from .db import now


def intent(messages, uid, reviews):
    document = policy.load()
    rule = document["policies"]["intent.rule"]["value"]
    version = document["runtime_version"]
    since = now() - timedelta(days=rule["window_days"])
    signals = {}
    relevant, pending = 0, 0
    for m in messages:
        if m["sender_id"] != str(uid) or m["sender_role"] != "parent" or m["time"] < since or m["type"] != "text":
            continue
        relevant += 1
        review = reviews.get(m["id"])
        if not review or review["status"] != "complete" or review["policy_version"] != version:
            pending += 1
            continue
        details = review["details"]
        if isinstance(details, str): details = json.loads(details)
        if not isinstance(details, dict) or not isinstance(details.get("intent_signals"), list):
            pending += 1
            continue
        for label in details["intent_signals"]:
            signals.setdefault(label, m["id"])
    n = len(signals)
    level = "高" if n >= rule["high_distinct_signal_types_min"] else "待识别" if pending else "中" if n == 1 else "低" if relevant else "信息不足"
    return {"level": level, "pending_messages": pending,
            "signals": [{"type": k, "message_id": v} for k, v in signals.items()]}


def profile_for(conn, account, uid):
    result = repository.user_profile(conn, account, uid)
    all_messages = []
    for conv in repository.conversations(conn, account):
        if conv["type"] == "group" or conv["peer_id"] == str(uid):
            all_messages.extend(repository.messages(conn, account, conv["id"], full=True))
    with conn.cursor() as cur:
        cur.execute("SELECT message_key,status,details,policy_version FROM opsie_inbound_reviews WHERE sender_id=%s AND effective_time>=%s",
                    (uid, now() - timedelta(days=3)))
        reviews = {row["message_key"]: row for row in cur.fetchall()}
    result["intent"] = intent(all_messages, uid, reviews)
    return result


def data(conn, account):
    if account["role"] != "teacher":
        raise PermissionError("仅老师可查看工作台")
    convs = repository.conversations(conn, account)
    # Only the last three days can affect today's count or the intent window.
    # Read all accessible demo conversations together to avoid repeated remote round trips.
    all_messages = []
    ids = [c['id'] for c in convs]
    if ids:
        marks = ','.join(['%s'] * len(ids))
        since = now() - timedelta(days=3)
        with conn.cursor() as cur:
            cur.execute(f"""SELECT CONCAT('m:',m.message_id) AS id,m.sender_user_id AS sender_id,
                COALESCE(a.role,'parent') AS sender_role,m.message_type AS type,m.created_at AS time
                FROM messages m LEFT JOIN opsie_accounts a ON a.user_id=m.sender_user_id
                WHERE m.conversation_id IN ({marks}) AND m.message_status='active' AND m.created_at >= %s
                UNION ALL
                SELECT CONCAT('h:',m.message_id),m.sender_user_id,COALESCE(a.role,'parent'),m.message_type,
                DATE_ADD(m.created_at, INTERVAL d.offset_seconds SECOND)
                FROM opsie_demo d JOIN messages m ON m.conversation_id=d.source_group_id
                LEFT JOIN opsie_accounts a ON a.user_id=m.sender_user_id
                WHERE d.group_id IN ({marks}) AND m.message_status='active'
                AND m.created_at >= DATE_SUB(%s, INTERVAL d.offset_seconds SECOND)""", ids + [since] + ids + [since])
            all_messages = cur.fetchall()
        for message in all_messages:
            message['sender_id'] = str(message['sender_id']) if message['sender_id'] is not None else None
    with conn.cursor() as cur:
        cur.execute("SELECT user_id,display_name FROM opsie_accounts WHERE role='parent' AND active=1 ORDER BY account_id")
        parents = cur.fetchall()
        cur.execute("SELECT message_key,status,details,policy_version FROM opsie_inbound_reviews WHERE effective_time>=%s", (now()-timedelta(days=3),))
        reviews = {r["message_key"]: r for r in cur.fetchall()}
        cur.execute("SELECT message_key,conversation_id,sender_id,details,effective_time FROM opsie_inbound_reviews "
                    "WHERE status='complete' AND is_sensitive=1 AND policy_version=%s AND effective_time>=%s AND effective_time<%s ORDER BY effective_time DESC",
                    (policy.load()["runtime_version"], now().replace(hour=0,minute=0,second=0,microsecond=0),
                     now().replace(hour=0,minute=0,second=0,microsecond=0)+timedelta(days=1)))
        risks = cur.fetchall()
    today = now().date()
    parent_ids = {str(x["user_id"]) for x in parents}
    active = {m["sender_id"] for m in all_messages if m["sender_id"] in parent_ids and m["time"].date() == today}
    profiles = repository.user_profiles(conn, account, [row['user_id'] for row in parents])
    for p in profiles:
        p["intent"] = intent(all_messages, p['user_id'], reviews)
    high = [x for x in profiles if x["intent"]["level"] == "高"]
    return {"today_conversations": len(active), "active_user_ids": sorted(active), "qc_count": len(risks), "high_intent": len(high),
            "risks": [{"message_id": r["message_key"], "user_id": str(r["sender_id"]),
                       "conversation_id": str(r["conversation_id"]),
                       "details": json.loads(r["details"]) if isinstance(r["details"], str) else r["details"],
                       "time": r["effective_time"]} for r in risks],
            "profiles": profiles}
