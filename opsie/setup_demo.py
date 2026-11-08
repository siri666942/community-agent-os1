"""Idempotently provision the explicitly scoped Opsie demo; preserves imported records."""
import json
import os
import secrets
import shutil
import sqlite3
from datetime import datetime, timedelta
from contextlib import closing
from pathlib import Path

from .auth import hash_password, verify_password
from .db import ROOT, now, transaction, backend, sqlite_path

DEMO = "reading-camp-v1"
SOURCE_GROUP = 3
PEOPLE = [
    ("teacher", 279, "teacher", "阅读老师"),
    ("parent1", 201, "parent", "家长一"),
    ("parent2", 198, "parent", "家长二"),
    ("parent3", 194, "parent", "家长三"),
    ("parent4", 176, "parent", "家长四"),
]
SEEDS = {
    201: "老师，孩子最近读得比较多，后面阅读会员怎么安排？",
    198: "老师，孩子挺喜欢读的，会员价格和权益可以介绍一下吗？",
    194: "最近孩子不太愿意阅读，我有点担心坚持不下来。",
    176: "老师，我想了解一下，如果报名后需要退款该怎么办？",
}


def setup():
    credentials_path = ROOT / ".dbmcp" / "demo-accounts.json"
    credentials_path.parent.mkdir(exist_ok=True)
    if credentials_path.exists():
        credentials = json.loads(credentials_path.read_text(encoding="utf-8"))
    else:
        if backend() == 'sqlite':
            if sqlite_path().exists():
                raise RuntimeError('本地数据库已存在但账号文件丢失，请恢复账号文件，不自动覆盖密码。')
        else:
            with transaction() as conn, conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS n FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name='opsie_accounts'")
                if cur.fetchone()["n"]:
                    cur.execute("SELECT COUNT(*) AS n FROM opsie_accounts")
                    if cur.fetchone()["n"]:
                        raise RuntimeError("演示账号已存在但本机账号文件丢失，请恢复账号文件，不自动覆盖密码。")
        credentials = {name: secrets.token_urlsafe(12) for name, _, _, _ in PEOPLE}
        credentials_path.write_text(json.dumps(credentials, ensure_ascii=False, indent=2), encoding="utf-8")
    if backend() == 'sqlite':
        setup_sqlite(credentials)
        print('本地演示数据库已就绪；账号文件:', credentials_path)
        return
    schema = (ROOT / "opsie" / "schema.sql").read_text(encoding="utf-8")
    with transaction() as conn:
        with conn.cursor() as cur:
            for statement in schema.split(";"):
                if statement.strip():
                    cur.execute(statement)
            for username, uid, role, name in PEOPLE:
                cur.execute("SELECT user_id FROM users WHERE user_id=%s", (uid,))
                if not cur.fetchone():
                    raise RuntimeError("指定演示用户不存在: " + str(uid))
                cur.execute("SELECT * FROM opsie_accounts WHERE username=%s", (username,))
                existing = cur.fetchone()
                if existing:
                    if existing["user_id"] != uid or not verify_password(credentials[username], existing["password_hash"]):
                        raise RuntimeError("已有演示账号与本机凭据不匹配，未修改账号。")
                else:
                    cur.execute("INSERT INTO opsie_accounts(username,password_hash,role,user_id,display_name) VALUES(%s,%s,%s,%s,%s)",
                                (username, hash_password(credentials[username]), role, uid, name))
            cur.execute("INSERT IGNORE INTO opsie_library_meta(meta_key,created_at) VALUES('initial_library',%s)", (now(),))
            if cur.rowcount:
                cur.execute("SELECT account_id FROM opsie_accounts WHERE username='teacher'")
                teacher_account = cur.fetchone()['account_id']
                defaults = [
                    ('standard','产品与权益','具体产品权益待确认，请先核实。',None),
                    ('standard','价格与优惠','价格和活动待确认，请先核实当前适用口径。',None),
                    ('standard','退费规则','先理解家长诉求，具体退费规则需核实，不承诺随时退或一律不能退。',None),
                    ('standard','测评与试听','是否免费及预约方式待确认，请先核实。',None),
                    ('risk','绝对效果承诺','不得保证每个孩子必然达到某个阅读效果或识字数量。','red'),
                    ('risk','退款承诺','不得擅自承诺随时退或无条件退款。','red'),
                    ('risk','群聊隐私','不得在群里披露孩子或家庭的个人隐私。','red'),
                    ('risk','未经核实的价格与优惠','不得承诺未经核实的价格、锁价或优惠。','yellow'),
                    ('risk','夸大师资或效果','师资和效果描述需要事实依据，不确定时先核实。','yellow'),
                ]
                cur.executemany("INSERT INTO opsie_library_entries(kind,title,content,level,updated_by,updated_at) VALUES(%s,%s,%s,%s,%s,%s)",
                                [(kind,title,content,level,teacher_account,now()) for kind,title,content,level in defaults])
            cur.execute("SELECT * FROM opsie_demo WHERE demo_key=%s", (DEMO,))
            demo = cur.fetchone()
            if not demo:
                cur.execute("SELECT MAX(created_at) AS latest FROM messages WHERE conversation_id=%s", (SOURCE_GROUP,))
                latest = cur.fetchone()["latest"]
                if not latest:
                    raise RuntimeError("历史群没有消息")
                offset = int(((now() - timedelta(minutes=30)) - latest).total_seconds())
                cur.execute("INSERT INTO conversations(conversation_type,title,created_by_user_id,settings) VALUES('group',%s,%s,%s)",
                            ("21 天阅读营演示群", PEOPLE[0][1], json.dumps({"opsie_demo": DEMO})))
                group_id = cur.lastrowid
                cur.execute("INSERT INTO opsie_demo(demo_key,group_id,source_group_id,offset_seconds,created_at) VALUES(%s,%s,%s,%s,%s)",
                            (DEMO, group_id, SOURCE_GROUP, offset, now()))
                for _, uid, role, _ in PEOPLE:
                    cur.execute("INSERT INTO conversation_members(conversation_id,user_id,member_role) VALUES(%s,%s,%s)",
                                (group_id, uid, "owner" if role == "teacher" else "member"))
            for index, (_, uid, role, _) in enumerate(PEOPLE[1:]):
                teacher = PEOPLE[0][1]
                lo, hi = sorted([teacher, uid])
                cur.execute("SELECT conversation_id FROM direct_conversation_pairs WHERE user_low_id=%s AND user_high_id=%s", (lo, hi))
                pair = cur.fetchone()
                if pair:
                    cid = pair["conversation_id"]
                else:
                    cur.execute("INSERT INTO conversations(conversation_type,title,created_by_user_id,settings) VALUES('direct',NULL,%s,%s)",
                                (teacher, json.dumps({"opsie_demo": DEMO})))
                    cid = cur.lastrowid
                    cur.execute("INSERT INTO direct_conversation_pairs(conversation_id,user_low_id,user_high_id) VALUES(%s,%s,%s)", (cid, lo, hi))
                    cur.executemany("INSERT INTO conversation_members(conversation_id,user_id,member_role) VALUES(%s,%s,%s)",
                                    [(cid, teacher, "owner"), (cid, uid, "member")])
                cur.execute("INSERT IGNORE INTO messages(conversation_id,sender_user_id,source_system,external_message_id,message_type,body,created_at) VALUES(%s,%s,'opsie_demo_seed',%s,'text',%s,%s)",
                            (cid, uid, f"{DEMO}-seed-{uid}", SEEDS[uid], now() - timedelta(minutes=20-index*3)))
                if uid == 198:
                    cur.execute("INSERT IGNORE INTO messages(conversation_id,sender_user_id,source_system,external_message_id,message_type,body,created_at) VALUES(%s,%s,'opsie_demo_seed',%s,'text',%s,%s)",
                                (cid, uid, f"{DEMO}-seed-followup-{uid}",
                                 "老师，能把会员资料清单发我看看吗？我想一起比较一下。", now() - timedelta(minutes=5)))
    print("演示结构和账号已就绪；账号文件:", credentials_path)


def setup_sqlite(credentials):
    """Copy only the fictional seed on first run, preserving the live DB thereafter."""
    path = sqlite_path()
    if path.exists():
        return
    seed = ROOT / 'data' / 'opsie-demo.sqlite3'
    if not seed.exists():
        raise RuntimeError('缺少演示种子库 data/opsie-demo.sqlite3')
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.initializing')
    if temporary.exists():
        raise RuntimeError('发现未完成的本地数据库初始化文件，请检查后移走：' + str(temporary))
    shutil.copyfile(seed, temporary)
    try:
        with closing(sqlite3.connect(temporary)) as conn, conn:
            for username, _, _, _ in PEOPLE:
                if username not in credentials:
                    raise RuntimeError('本机账号文件缺少账号：' + username)
                conn.execute('UPDATE opsie_accounts SET password_hash=? WHERE username=?', (hash_password(credentials[username]), username))
            latest = conn.execute("SELECT MAX(created_at) FROM messages WHERE source_system='opsie_demo_seed'").fetchone()[0]
            offset = now() - timedelta(minutes=5) - datetime.fromisoformat(latest)
            rows = conn.execute("SELECT message_id,created_at FROM messages WHERE source_system='opsie_demo_seed'").fetchall()
            conn.executemany('UPDATE messages SET created_at=? WHERE message_id=?',
                             [((datetime.fromisoformat(at)+offset).isoformat(' '), mid) for mid, at in rows])
            conn.execute('UPDATE opsie_demo SET created_at=?', (now().isoformat(' '),))
            conn.execute('UPDATE conversations SET last_message_at=(SELECT MAX(created_at) FROM messages WHERE messages.conversation_id=conversations.conversation_id)')
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


if __name__ == "__main__":
    setup()
