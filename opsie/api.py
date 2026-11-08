"""Single HTTP service for Opsie demo; all state resides in MySQL."""
import hashlib
import hmac
import json
import logging
import mimetypes
import os
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import ai, auth, dashboard, policy, repository
from .db import ROOT, json_default, now, transaction

WEB = ROOT / "web"
SECRET = secrets.token_bytes(32)
POLICY_LOCK = threading.Lock()
LAST_POLICY = None


def refresh_policy_tasks():
    global LAST_POLICY
    version = policy.load()["runtime_version"]
    with POLICY_LOCK:
        if version == LAST_POLICY:
            return
        LAST_POLICY = version
    from . import backfill
    def run_backfill():
        global LAST_POLICY
        try:
            backfill.run()
        except Exception:
            with POLICY_LOCK:
                if LAST_POLICY == version:
                    LAST_POLICY = None
    ai.EXECUTOR.submit(run_backfill)


def confirmation(account, cid, text):
    msg = json.dumps([account["account_id"], str(cid), text, policy.load()["runtime_version"]], ensure_ascii=False).encode()
    return hmac.new(SECRET, msg, hashlib.sha256).hexdigest()


class Handler(BaseHTTPRequestHandler):
    server_version = "Opsie/1"

    def log_message(self, fmt, *args):
        pass

    def send_json(self, status, obj):
        raw = json.dumps(obj, ensure_ascii=False, default=json_default).encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            pass  # A browser may navigate away while a model or database request is in flight.

    def body(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length > 65536:
            raise ValueError("请求过大")
        data = json.loads(self.rfile.read(length) or b"{}")
        if not isinstance(data, dict):
            raise ValueError("请求格式无效")
        return data

    def account(self, conn):
        header = self.headers.get("Authorization", "")
        token = header[7:] if header.startswith("Bearer ") else ""
        account = auth.identify(conn, token)
        if not account:
            raise PermissionError("请先登录")
        return account

    def do_GET(self):
        try:
            url = urlparse(self.path)
            path = url.path
            if path in ("/", "/opsie.html", "/opsie.css", "/opsie.js"):
                file = WEB / ("opsie.html" if path == "/" else path[1:])
                raw = file.read_bytes()
                content_type = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
                self.send_response(200)
                self.send_header("Content-Type", content_type + "; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(raw)
                return
            if path == "/health":
                try:
                    with transaction() as conn, conn.cursor() as cur:
                        cur.execute("SELECT 1")
                        cur.fetchone()
                    return self.send_json(200, {"ok": True, "service": "opsie", "database": "connected"})
                except Exception:
                    return self.send_json(503, {"ok": False, "database": "unavailable"})
            with transaction() as conn:
                user = self.account(conn)
                if path == "/api/v1/me":
                    return self.send_json(200, user)
                if path == "/api/v1/conversations":
                    return self.send_json(200, {"items": repository.conversations(conn, user)})
                if path.startswith("/api/v1/messages/"):
                    cid = path.rsplit("/", 1)[1]
                    full = parse_qs(url.query).get("all", ["0"])[0] == "1"
                    return self.send_json(200, {"items": repository.messages(conn, user, cid, full)})
                if path.startswith("/api/v1/profile/"):
                    uid = path.rsplit("/", 1)[1]
                    return self.send_json(200, dashboard.profile_for(conn, user, uid))
                if path.startswith("/api/v1/jobs/"):
                    return self.send_json(200, ai.job_status(conn, user, path.rsplit("/", 1)[1]))
                if path == "/api/v1/dashboard":
                    refresh_policy_tasks()
                    return self.send_json(200, dashboard.data(conn, user))
                if path == "/api/v1/sop":
                    if user["role"] != "teacher": raise PermissionError("仅老师可查看 SOP")
                    source = json.loads((ROOT / "knowledge" / "sop.json").read_text(encoding="utf-8"))
                    return self.send_json(200, {"days": source})
                if path.startswith("/api/v1/inbound/"):
                    cid = path.rsplit("/", 1)[1]
                    repository.ensure_member(conn, user, cid)
                    if user["role"] != "teacher":
                        raise PermissionError("仅老师可查看质检")
                    with conn.cursor() as cur:
                        cur.execute("SELECT message_key,status,is_sensitive,details FROM opsie_inbound_reviews WHERE conversation_id=%s", (cid,))
                        entries = cur.fetchall()
                    for entry in entries:
                        if isinstance(entry["details"], str): entry["details"] = json.loads(entry["details"])
                    return self.send_json(200, {"items": entries})
                if path == "/api/v1/policy":
                    if user["role"] != "teacher": raise PermissionError("仅老师可查看规则")
                    refresh_policy_tasks()
                    doc = policy.load()
                    keys = ["product.catalog", "product.pricing", "product.promotions", "refund.policy", "product.access_after_expiry", "product.assessment_trial", "product.teacher_service"]
                    entries = {key: {"status": doc["policies"][key]["status"], "value": doc["policies"][key]["value"]} for key in keys}
                    return self.send_json(200, {"version": doc["runtime_version"], "rules": policy.confirmed_facts(doc), "product": entries})
            return self.send_json(404, {"error": "接口不存在"})
        except PermissionError as exc:
            return self.send_json(403, {"error": str(exc)})
        except (ValueError, TypeError) as exc:
            return self.send_json(400, {"error": str(exc)})
        except Exception as exc:
            logging.error("Opsie GET failed: %s", type(exc).__name__)
            return self.send_json(500, {"error": "读取失败，请稍后重试"})

    def do_POST(self):
        try:
            path = urlparse(self.path).path
            data = self.body()
            if path == "/api/v1/login":
                with transaction() as conn:
                    token, user = auth.login(conn, str(data.get("username", "")), str(data.get("password", "")))
                return self.send_json(200, {"token": token, "user": user})
            if path in ("/api/v1/drafts", "/api/v1/drafts/auto"):
                with transaction() as conn:
                    user = self.account(conn)
                if user["role"] != "teacher": raise PermissionError("仅老师可生成回复")
                job_id = ai.enqueue_drafts(user, str(data.get("conversation_id", "")), str(data.get("target_message_id", "")),
                                           instruction=data.get('instruction', ''), rewrite_text=data.get('rewrite_text', ''),
                                           automatic=path.endswith('/auto'))
                return self.send_json(202, {"job_id": job_id})
            if path == "/api/v1/summary":
                with transaction() as conn:
                    user = self.account(conn)
                if user["role"] != "teacher": raise PermissionError("仅老师可生成画像概括")
                return self.send_json(200, {"summary": ai.refresh_summary(user, str(data.get("user_id", "")))})
            if path == "/api/v1/retry-inbound":
                cid, key = str(data.get("conversation_id", "")), str(data.get("message_id", ""))
                with transaction() as conn:
                    user = self.account(conn)
                    if user["role"] != "teacher": raise PermissionError("仅老师可重试识别")
                    message = repository.get_target(conn, user, cid, key)
                    if message["sender_role"] != "parent" or not message["sender_id"]:
                        raise ValueError("请选择一条家长消息")
                ai.assess_inbound(user, cid, message)
                return self.send_json(202, {"ok": True})
            if path == "/api/v1/messages":
                return self.post_message(data)
            result = None
            with transaction() as conn:
                user = self.account(conn)
                if path == "/api/v1/logout":
                    token = self.headers.get("Authorization", "")[7:]
                    with conn.cursor() as cur:
                        cur.execute("DELETE FROM opsie_sessions WHERE token_hash=%s", (auth.token_hash(token),))
                    result = {"ok": True}
                if path == "/api/v1/tags":
                    if user["role"] != "teacher": raise PermissionError("仅老师可管理标签")
                    uid, tag = str(data.get("user_id", "")), str(data.get("tag", "")).strip()
                    if not tag or len(tag) > 60: raise ValueError("标签长度应为 1 至 60 字")
                    with conn.cursor() as cur:
                        if data.get("remove"):
                            cur.execute("DELETE FROM opsie_tags WHERE user_id=%s AND tag=%s", (uid, tag))
                        else:
                            cur.execute("INSERT IGNORE INTO opsie_tags(user_id,tag,account_id,created_at) VALUES(%s,%s,%s,%s)",
                                        (uid, tag, user["account_id"], now()))
                    result = {"ok": True}
            if result is not None:
                return self.send_json(200, result)
            return self.send_json(404, {"error": "接口不存在"})
        except PermissionError as exc:
            return self.send_json(403, {"error": str(exc)})
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            return self.send_json(400, {"error": str(exc)})
        except RuntimeError as exc:
            return self.send_json(503, {"error": str(exc)})
        except Exception as exc:
            logging.error("Opsie POST failed: %s", type(exc).__name__)
            return self.send_json(500, {"error": "操作失败，请稍后重试"})

    def post_message(self, data):
        cid, text = str(data.get("conversation_id", "")), str(data.get("text", "")).strip()
        client_id = data.get("client_message_id", "")
        with transaction() as conn:
            user = self.account(conn)
            conversation = repository.ensure_member(conn, user, cid)
            with conn.cursor() as cur:
                cur.execute("SELECT message_id,conversation_id,body FROM messages WHERE sender_user_id=%s AND client_message_id=%s", (user["user_id"], client_id))
                old = cur.fetchone()
            if old:
                if str(old["conversation_id"]) != cid or old["body"] != text:
                    raise ValueError("消息标识已用于其他内容")
                return self.send_json(200, {"message_id": str(old["message_id"]), "duplicate": True})
        if user["role"] == "teacher":
            review_version = policy.load()["runtime_version"]
            result = ai.review_outbound(text, conversation["conversation_type"])
            if policy.load()["runtime_version"] != review_version:
                raise RuntimeError("质检口径刚刚更新，请重新发送以完成审核")
            status = result["status"]
            needed = status == "yellow" and not hmac.compare_digest(str(data.get("confirmation", "")), confirmation(user, cid, text))
            if status == "red" or needed:
                with transaction() as conn, conn.cursor() as cur:
                    cur.execute("INSERT INTO opsie_outbound_reviews(conversation_id,account_id,text_hash,status,details,policy_version,created_at) VALUES(%s,%s,%s,%s,%s,%s,%s)",
                                (cid, user["account_id"], hashlib.sha256(text.encode()).hexdigest(), status,
                                 json.dumps(result, ensure_ascii=False), policy.load()["runtime_version"], now()))
                return self.send_json(409, {"error": "请修改回复" if status == "red" else "请核对风险后确认发送",
                                            "review": result, "confirmation": confirmation(user, cid, text) if needed else None})
        with transaction() as conn:
            mid, created = repository.insert_message(conn, user, cid, client_id, text)
            if user["role"] == "teacher" and created:
                with conn.cursor() as cur:
                    cur.execute("INSERT INTO opsie_outbound_reviews(conversation_id,account_id,text_hash,status,details,confirmed,variant,edited,message_id,policy_version,created_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                                (cid, user["account_id"], hashlib.sha256(text.encode()).hexdigest(), result["status"],
                                 json.dumps(result, ensure_ascii=False), bool(data.get("confirmation")), str(data.get("variant", "CUSTOM"))[:32],
                                 bool(data.get("edited")), mid, policy.load()["runtime_version"], now()))
        if user["role"] == "parent" and created:
            ai.EXECUTOR.submit(ai.prepare_auto_drafts, cid, "m:" + mid)
            try:
                ai.assess_inbound(user, cid, {"id": "m:" + mid, "sender_id": user["user_id"], "text": text, "time": now()})
            except Exception:
                # The message is already committed; never report it as unsent.
                return self.send_json(200, {"message_id": mid, "duplicate": False, "review_pending": True})
        return self.send_json(200, {"message_id": mid, "duplicate": not created})


def main():
    with transaction() as conn, conn.cursor() as cur:
        cur.execute("UPDATE opsie_jobs SET status='interrupted',error='服务重启，需重新生成',updated_at=%s WHERE status IN ('queued','running')", (now(),))
        cur.execute("UPDATE opsie_inbound_reviews SET status='failed',updated_at=%s WHERE status IN ('pending','running')", (now(),))
    server = ThreadingHTTPServer((os.environ.get("OPSIE_HOST", "127.0.0.1"), int(os.environ.get("OPSIE_PORT", "8780"))), Handler)
    refresh_policy_tasks()
    print("Opsie: http://%s:%s" % server.server_address, flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
