"""Opt-in real-MySQL/model smoke test; removes only its own uniquely marked rows.

Run after the demo server is started: python tests/opsie_e2e.py
"""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from opsie.db import transaction  # noqa: E402

BASE = "http://127.0.0.1:8780"
credentials = json.loads((ROOT / ".dbmcp" / "demo-accounts.json").read_text(encoding="utf-8"))


def request(path, token=None, body=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(BASE + path, headers=headers,
                                 data=json.dumps(body, ensure_ascii=False).encode() if body is not None else None)
    try:
        with urllib.request.urlopen(req, timeout=180) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as exc:
        return exc.code, json.load(exc)


def expect(status, expected, detail):
    if status != expected:
        raise AssertionError(f"Expected HTTP {expected}, got {status}: {detail}")


def main():
    marker = "opsie-e2e-" + uuid.uuid4().hex
    parent_client, second_client, third_client, teacher_client = marker + "-parent", marker + "-second", marker + "-stale", marker + "-teacher"
    message_ids, job_id, tokens = [], None, {}
    response_text = "我理解您的顾虑，我会先帮您核实相关规则。"
    red_text = "测试消息：我保证您可以随时退款"
    try:
        for name in ["teacher", "parent1", "parent2", "parent3", "parent4"]:
            status, value = request("/api/v1/login", body={"username": name, "password": credentials[name]})
            expect(status, 200, value)
            tokens[name] = value["token"]
        assert len(set(tokens.values())) == 5
        print("PASS five independent logins", flush=True)

        status, value = request("/api/v1/conversations", tokens["parent1"])
        expect(status, 200, value)
        group = next(c["id"] for c in value["items"] if c["type"] == "group")
        direct = next(c["id"] for c in value["items"] if c["type"] == "direct")
        status, value = request("/api/v1/messages/" + direct, tokens["parent2"])
        expect(status, 403, value)
        status, value = request("/api/v1/profile/201", tokens["parent1"])
        expect(status, 403, value)
        print("PASS private-chat and profile isolation", flush=True)

        body = {"conversation_id": group, "text": "演示联调：想咨询退款应该怎么办？", "client_message_id": parent_client}
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda _: request("/api/v1/messages", tokens["parent1"], body), range(2)))
        for status, value in responses:
            expect(status, 200, value)
        assert responses[0][1]["message_id"] == responses[1][1]["message_id"]
        mid = responses[0][1]["message_id"]
        message_ids.append(mid)
        print("PASS concurrent retry deduplication", flush=True)

        status, second = request("/api/v1/messages", tokens["parent2"],
                                 {"conversation_id": group, "text": "演示联调：孩子的阅读安排是什么？", "client_message_id": second_client})
        expect(status, 200, second)
        second_mid = second["message_id"]
        message_ids.append(second_mid)

        for name in tokens:
            status, value = request("/api/v1/messages/" + group, tokens[name])
            expect(status, 200, value)
            assert any(m["id"] == "m:" + mid for m in value["items"]), name
            assert any(m["id"] == "m:" + second_mid for m in value["items"]), name
        print("PASS group visibility across five sessions", flush=True)

        status, value = request("/api/v1/drafts", tokens["teacher"],
                                {"conversation_id": group, "target_message_id": "m:" + second_mid})
        expect(status, 202, value)
        job_id = value["job_id"]
        with transaction() as db, db.cursor() as cur:
            cur.execute("SELECT target_user_id FROM opsie_jobs WHERE job_id=%s", (job_id,))
            assert str(cur.fetchone()["target_user_id"]) == "198"
        print("PASS group reply targets the selected parent", flush=True)
        for _ in range(70):
            time.sleep(2)
            status, job = request("/api/v1/jobs/" + job_id, tokens["teacher"])
            expect(status, 200, job)
            if job["status"] not in ("queued", "running"):
                break
        assert job["status"] == "succeeded" and len(job["result"]["drafts"]) == 3, job.get("error")
        assert all(d['qc']['status'] in ('green', 'yellow', 'red') for d in job['result']['drafts']), 'candidate semantic review unavailable'
        print("PASS real-model group drafts and semantic checks using complete history", flush=True)

        status, additional = request("/api/v1/messages", tokens["parent2"],
                                     {"conversation_id": group, "text": "演示联调：我再补充一个问题。", "client_message_id": third_client})
        expect(status, 200, additional)
        message_ids.append(additional["message_id"])
        status, stale = request("/api/v1/jobs/" + job_id, tokens["teacher"])
        expect(status, 200, stale)
        assert stale["stale"] is True
        print("PASS new messages mark existing drafts stale", flush=True)

        for _ in range(35):
            status, value = request("/api/v1/inbound/" + group, tokens["teacher"])
            review = next((r for r in value["items"] if r["message_key"] == "m:" + mid), None)
            if review and review["status"] not in ("pending", "running"):
                break
            time.sleep(2)
        assert review and review["status"] == "complete" and review["is_sensitive"] == 1, review
        with transaction() as db, db.cursor() as cur:
            cur.execute("SELECT COUNT(*) n FROM opsie_inbound_reviews WHERE message_key=%s", ("m:" + mid,))
            assert cur.fetchone()["n"] == 1
        print("PASS real inbound assessment counted once", flush=True)

        status, value = request("/api/v1/messages", tokens["teacher"],
                                {"conversation_id": group, "text": red_text, "client_message_id": marker + "-red"})
        assert status == 409 and value["review"]["status"] == "red", value
        status, value = request("/api/v1/messages", tokens["teacher"],
                                {"conversation_id": group, "text": response_text, "client_message_id": teacher_client})
        if status == 409 and value.get("confirmation"):
            status, value = request("/api/v1/messages", tokens["teacher"],
                                    {"conversation_id": group, "text": response_text, "client_message_id": teacher_client,
                                     "confirmation": value["confirmation"]})
        expect(status, 200, value)
        message_ids.append(value["message_id"])
        status, seen = request("/api/v1/messages/" + group, tokens["parent2"])
        expect(status, 200, seen)
        assert any(m["id"] == "m:" + value["message_id"] for m in seen["items"])
        print("PASS red block and reviewed teacher reply delivered", flush=True)
    finally:
        with transaction() as db, db.cursor() as cur:
            if job_id:
                cur.execute("DELETE FROM opsie_jobs WHERE job_id=%s", (job_id,))
            for token in tokens.values():
                cur.execute("DELETE FROM opsie_sessions WHERE token_hash=%s", (hashlib.sha256(token.encode()).hexdigest(),))
            for mid in message_ids:
                cur.execute("DELETE FROM opsie_inbound_reviews WHERE message_key=%s", ("m:" + mid,))
                cur.execute("DELETE FROM opsie_outbound_reviews WHERE message_id=%s", (mid,))
            cur.execute("DELETE FROM opsie_outbound_reviews WHERE text_hash IN (%s,%s) AND message_id IS NULL",
                        (hashlib.sha256(red_text.encode()).hexdigest(), hashlib.sha256(response_text.encode()).hexdigest()))
            cur.execute("DELETE FROM messages WHERE source_system='opsie_live' AND client_message_id IN (%s,%s,%s,%s)",
                        (parent_client, second_client, third_client, teacher_client))
            if 'group' in locals():
                cur.execute("SELECT MAX(created_at) AS latest FROM messages WHERE conversation_id=%s AND message_status='active'", (group,))
                latest_live = cur.fetchone()['latest']
                cur.execute("SELECT DATE_ADD(MAX(m.created_at),INTERVAL d.offset_seconds SECOND) AS latest FROM opsie_demo d "
                            "JOIN messages m ON m.conversation_id=d.source_group_id WHERE d.group_id=%s GROUP BY d.offset_seconds", (group,))
                row = cur.fetchone()
                latest_history = row['latest'] if row else None
                latest = max((v for v in (latest_live, latest_history) if v is not None), default=None)
                cur.execute("UPDATE conversations SET last_message_at=%s WHERE conversation_id=%s", (latest, group))
        print("Test-only rows cleaned", flush=True)


if __name__ == "__main__":
    main()
