"""Editable shared wording and risk guidance for the teacher workspace."""
import hashlib
import json
from .db import now, transaction


def list_entries(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT entry_id,kind,title,content,level,updated_at FROM opsie_library_entries ORDER BY entry_id")
        return cur.fetchall()


def snapshot():
    with transaction() as conn:
        entries = list_entries(conn)
    items = [{k: e[k] for k in ('entry_id', 'kind', 'title', 'content', 'level')} for e in entries]
    version = hashlib.sha256(json.dumps(items, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]
    return {'entries': items, 'version': version}


def save(conn, account, data):
    kind = data.get('kind')
    title, content = data.get('title'), data.get('content')
    level = data.get('level') if kind == 'risk' else None
    if kind not in ('standard', 'risk') or not isinstance(title, str) or not title.strip() or len(title.strip()) > 120:
        raise ValueError('请填写不超过 120 字的标题')
    if not isinstance(content, str) or not content.strip() or len(content.strip()) > 4000:
        raise ValueError('请填写不超过 4000 字的内容')
    if kind == 'risk' and level not in ('red', 'yellow'):
        raise ValueError('请选择风险级别')
    entry_id = data.get('id')
    with conn.cursor() as cur:
        if entry_id is not None:
            if not str(entry_id).isdigit():
                raise ValueError('条目标识无效')
            cur.execute('SELECT entry_id FROM opsie_library_entries WHERE entry_id=%s AND kind=%s FOR UPDATE', (entry_id, kind))
            if not cur.fetchone():
                raise ValueError('条目不存在')
            cur.execute('UPDATE opsie_library_entries SET title=%s,content=%s,level=%s,updated_by=%s,updated_at=%s WHERE entry_id=%s',
                        (title.strip(), content.strip(), level, account['account_id'], now(), entry_id))
        else:
            cur.execute('INSERT INTO opsie_library_entries(kind,title,content,level,updated_by,updated_at) VALUES(%s,%s,%s,%s,%s,%s)',
                        (kind, title.strip(), content.strip(), level, account['account_id'], now()))
            entry_id = cur.lastrowid
    return str(entry_id)


def delete(conn, entry_id):
    if not str(entry_id).isdigit():
        raise ValueError('条目标识无效')
    with conn.cursor() as cur:
        cur.execute('DELETE FROM opsie_library_entries WHERE entry_id=%s', (entry_id,))
        if not cur.rowcount:
            raise ValueError('条目不存在')
