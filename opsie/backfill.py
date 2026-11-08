"""Queue the demo's own recent historical parent messages for real risk detection."""
from datetime import timedelta
from . import ai, repository
from .db import now, transaction, backend


def run():
    with transaction() as conn, conn.cursor() as cur:
        cur.execute("SELECT account_id,user_id,role,display_name FROM opsie_accounts WHERE role='teacher' AND active=1 LIMIT 1")
        raw = cur.fetchone()
        if not raw:
            return
        account = {"account_id": str(raw["account_id"]), "user_id": str(raw["user_id"]),
                   "role": raw["role"], "display_name": raw["display_name"]}
        cur.execute("SELECT user_id FROM opsie_accounts WHERE role='parent' AND active=1")
        parent_ids = {str(r["user_id"]) for r in cur.fetchall()}
        cur.execute("SELECT user_id FROM opsie_profile_cache WHERE source_revision LIKE 'demo-safe-v1:%%'")
        cached = {str(r["user_id"]) for r in cur.fetchall()}
        conversations = repository.conversations(conn, account)
    for conv in conversations:
        with transaction() as conn:
            messages = repository.messages(conn, account, conv["id"], full=True)
        for message in messages:
            if (message['source'] != '演示初始私聊' and message["sender_id"] in parent_ids and message["sender_role"] == "parent" and
                    message["type"] == "text" and message["time"] >= now() - timedelta(days=3)):
                ai.assess_inbound(account, conv["id"], message)
    # Fictional seed histories should not trigger a burst of model calls on startup.
    if backend() == 'sqlite':
        return
    for uid in parent_ids - cached:
        ai.EXECUTOR.submit(ai.refresh_summary, account, uid)


if __name__ == "__main__":
    run()
