"""Shared MySQL read/write model for demo chat, agents and dashboard."""
import json
from datetime import timedelta
from .db import now
from . import profile, demo_data


def ensure_member(conn, account, cid):
    with conn.cursor() as cur:
        cur.execute("SELECT c.* FROM conversations c JOIN conversation_members m ON m.conversation_id=c.conversation_id "
                    "WHERE c.conversation_id=%s AND m.user_id=%s AND m.member_status='active' AND c.conversation_status='active'",
                    (cid, account["user_id"]))
        row = cur.fetchone()
    if not row:
        raise PermissionError("无权访问此会话")
    return row


def conversations(conn, account):
    with conn.cursor() as cur:
        cur.execute("""SELECT c.conversation_id,c.conversation_type,c.title,c.last_message_at,
          (SELECT a.display_name FROM conversation_members cm JOIN opsie_accounts a ON a.user_id=cm.user_id
           WHERE cm.conversation_id=c.conversation_id AND cm.user_id<>%s LIMIT 1) AS peer_name,
          (SELECT cm.user_id FROM conversation_members cm WHERE cm.conversation_id=c.conversation_id
           AND cm.user_id<>%s LIMIT 1) AS peer_id
          FROM conversations c JOIN conversation_members mine ON mine.conversation_id=c.conversation_id
          WHERE mine.user_id=%s AND mine.member_status='active' AND c.conversation_status='active'
          AND JSON_UNQUOTE(JSON_EXTRACT(c.settings,'$.opsie_demo'))='reading-camp-v1'
          ORDER BY c.conversation_type='group' DESC,c.conversation_id""",
                    (account["user_id"], account["user_id"], account["user_id"]))
        rows = cur.fetchall()
    return [{"id": str(r["conversation_id"]), "type": r["conversation_type"],
             "title": (demo_data.display_name(r['peer_id'], r['peer_name'] or '对话') if r['conversation_type']=='direct' else r['title'] or '阅读营群聊'), "peer_id": str(r["peer_id"]) if r["peer_id"] else None}
            for r in rows]


def messages(conn, account, cid, full=False):
    ensure_member(conn, account, cid)
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM opsie_demo WHERE group_id=%s", (cid,))
        demo = cur.fetchone()
        sql = """SELECT CONCAT('m:',m.message_id) AS message_key,m.message_id,m.sender_user_id,
          COALESCE(a.display_name,u.display_name,'未知用户') AS sender_name,
          COALESCE(a.role,'parent') AS sender_role,m.message_type,m.body,m.created_at AS effective_time,
          m.created_at AS original_time,m.source_system,COALESCE(m.reply_to_message_id,0) AS reply_to_message_id
          FROM messages m LEFT JOIN users u ON u.user_id=m.sender_user_id
          LEFT JOIN opsie_accounts a ON a.user_id=m.sender_user_id
          WHERE m.conversation_id=%s AND m.message_status='active' AND m.message_type='text'"""
        params = [cid]
        sql = "SELECT * FROM (" + sql + ") combined ORDER BY effective_time DESC,message_id DESC"
        if not full:
            sql += " LIMIT 100"
        cur.execute(sql, params)
        rows = list(reversed(cur.fetchall()))
    result = []
    for r in rows:
        body = r["body"] or ""
        if r["message_type"] != "text":
            body = f"[{r['message_type']} 历史消息]" if not body else f"[{r['message_type']}] {body}"
        result.append({"id": r["message_key"], "sender_id": str(r["sender_user_id"]) if r["sender_user_id"] else None,
                       "sender_name": demo_data.display_name(r['sender_user_id'], r['sender_name']), "sender_role": r["sender_role"], "type": r["message_type"],
                       "text": body, "time": r["effective_time"], "original_time": r["original_time"],
                       "source": "历史群" if r["message_key"].startswith("h:") else
                                 "演示初始私聊" if r["source_system"] == "opsie_demo_seed" else "现场消息"})
    if demo and not getattr(conn, 'is_sqlite', False):
        result.extend(demo_data.group_messages(demo['created_at']))
        result.sort(key=lambda m: (m['time'], m['id']))
        if not full:
            result = result[-100:]
    return result


def get_target(conn, account, cid, message_key):
    for msg in messages(conn, account, cid, full=True):
        if msg["id"] == message_key:
            return msg
    raise ValueError("消息不存在或不属于当前会话")


def insert_message(conn, account, cid, client_id, text):
    ensure_member(conn, account, cid)
    if not isinstance(text, str) or not text.strip() or len(text) > 6000:
        raise ValueError("消息不能为空或超过 6000 字")
    if not isinstance(client_id, str) or not (8 <= len(client_id) <= 128):
        raise ValueError("消息标识无效")
    with conn.cursor() as cur:
        # Serialize retries for the same sender before checking the unique message ID.
        cur.execute("SELECT account_id FROM opsie_accounts WHERE account_id=%s FOR UPDATE", (account["account_id"],))
        cur.execute("SELECT message_id,conversation_id,body FROM messages WHERE sender_user_id=%s AND client_message_id=%s FOR UPDATE",
                    (account["user_id"], client_id))
        old = cur.fetchone()
        if old:
            if str(old["conversation_id"]) != str(cid) or old["body"] != text.strip():
                raise ValueError("消息标识已用于其他内容")
            return str(old["message_id"]), False
        cur.execute("INSERT INTO messages(conversation_id,sender_user_id,client_message_id,source_system,message_type,body,created_at) "
                    "VALUES(%s,%s,%s,'opsie_live','text',%s,%s)", (cid, account["user_id"], client_id, text.strip(), now()))
        mid = cur.lastrowid
        cur.execute("UPDATE conversations SET last_message_at=%s WHERE conversation_id=%s", (now(), cid))
        return str(mid), True


def user_profile(conn, account, uid):
    if account["role"] != "teacher":
        raise PermissionError("无权查看画像")
    with conn.cursor() as cur:
        cur.execute("SELECT u.profile,a.display_name FROM users u LEFT JOIN opsie_accounts a ON a.user_id=u.user_id WHERE u.user_id=%s", (uid,))
        u = cur.fetchone()
        if not u:
            raise ValueError("用户不存在")
        cur.execute("SELECT tag,created_at FROM opsie_tags WHERE user_id=%s ORDER BY tag_id", (uid,))
        tags = cur.fetchall()
        cur.execute("SELECT summary,updated_at,source_revision FROM opsie_profile_cache WHERE user_id=%s", (uid,))
        cache = cur.fetchone()
        if cache and not (cache['source_revision'] or '').startswith('demo-safe-v1:'): cache = None
    result = profile.build(u["profile"])
    result.update({"user_id": str(uid), "name": demo_data.display_name(uid, u["display_name"] or "家长"), "manual_tags": tags,
                   "summary": cache["summary"] if cache else None, "summary_updated_at": cache["updated_at"] if cache else None})
    return result


def user_profiles(conn, account, ids):
    """Load the dashboard's profiles in batches, preserving the normal profile shape."""
    if account["role"] != "teacher":
        raise PermissionError("无权查看画像")
    if not ids:
        return []
    marks = ','.join(['%s'] * len(ids))
    with conn.cursor() as cur:
        cur.execute(f"SELECT u.user_id,u.profile,a.display_name FROM users u LEFT JOIN opsie_accounts a ON a.user_id=u.user_id WHERE u.user_id IN ({marks})", ids)
        users = {str(row['user_id']): row for row in cur.fetchall()}
        cur.execute(f"SELECT user_id,tag,created_at FROM opsie_tags WHERE user_id IN ({marks}) ORDER BY tag_id", ids)
        tags = {}
        for row in cur.fetchall():
            tags.setdefault(str(row['user_id']), []).append({'tag': row['tag'], 'created_at': row['created_at']})
        cur.execute(f"SELECT user_id,summary,updated_at,source_revision FROM opsie_profile_cache WHERE user_id IN ({marks})", ids)
        cache = {str(row['user_id']): row for row in cur.fetchall() if (row['source_revision'] or '').startswith('demo-safe-v1:')}
    result = []
    for uid in ids:
        key = str(uid)
        if key not in users:
            raise ValueError("用户不存在")
        user, saved = users[key], cache.get(key)
        item = profile.build(user['profile'])
        item.update({'user_id': key, 'name': demo_data.display_name(uid, user['display_name'] or '家长'), 'manual_tags': tags.get(key, []),
                     'summary': saved['summary'] if saved else None, 'summary_updated_at': saved['updated_at'] if saved else None})
        result.append(item)
    return result
