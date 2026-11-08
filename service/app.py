"""Agent Service RESTful HTTP+JSON 接口(暴露给 Web Chat 层)。

三层架构:用户 ↔ Web Chat ↔ **Agent Service(本服务)** ↔ Database。
只出稿不发送:所有对外消息的发送动作由 Web 端老师点击触发,本服务
记录留痕(message_id / 选用备选 / 是否改写 / 质检状态)。

POST /api/v1/drafts            运营助手:家长消息 → 三个备选 + 风险标注
POST /api/v1/send              发送闸门 + 留痕(红锁死 / 黄需确认 / 绿放行)
POST /api/v1/qc                独立质检(自定义文本)
GET  /api/v1/profile/{uid}     用户画像(五块内容)
GET  /api/v1/growth/daily      增值分析师:今日跟进名单 + 专属话术
GET  /api/v1/growth/report     分层分布
GET  /api/v1/sop/board         SOP 推进看板
POST /api/v1/sop/change        人工调整留痕(三种生效范围)
GET  /api/v1/customers         客户检索(分页)
GET  /api/v1/messages/{cid}    会话留痕回放
GET  /healthz                  健康检查
"""
from __future__ import annotations

import json
import re
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import assistant, analyst, config, profile as profile_mod, qc, repository, sop


def _json(handler: BaseHTTPRequestHandler, code: int, data: dict) -> None:
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    # Web Chat 开发期跨端口联调
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.end_headers()
    handler.wfile.write(body)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # 安静运行,留痕走系统日志
        pass

    def do_OPTIONS(self):
        _json(self, 204, {})

    def do_GET(self):
        path = self.path.split("?")[0]
        try:
            if path == "/healthz":
                _json(self, 200, {"ok": True, "service": "agent-service",
                                  "db": config.DB_PATH, "llm": config.LLM_ENABLED})
            elif path.startswith("/api/v1/profile/"):
                uid = path.rsplit("/", 1)[1]
                self._profile(uid)
            elif path == "/api/v1/growth/daily":
                q = self._query()
                _json(self, 200, analyst.daily_list(
                    limit=int(q.get("limit", 50)), uid_filter=q.get("uid") or None))
            elif path == "/api/v1/growth/report":
                _json(self, 200, analyst.segment_report())
            elif path == "/api/v1/sop/board":
                self._board()
            elif path == "/api/v1/customers":
                self._customers()
            elif path.startswith("/api/v1/messages/"):
                cid = path.rsplit("/", 1)[1]
                _json(self, 200, {"cid": cid,
                                  "messages": repository.get_repository().list_messages(cid)})
            else:
                _json(self, 404, {"error": "not found"})
        except Exception as e:  # noqa: BLE001
            _json(self, 500, {"error": str(e)})

    def do_POST(self):
        path = self.path.split("?")[0]
        try:
            body = self._body()
            if path == "/api/v1/drafts":
                self._drafts(body)
            elif path == "/api/v1/send":
                self._send(body)
            elif path == "/api/v1/qc":
                result = qc.check(body.get("text", ""))
                _json(self, 200, {**result, "sendable": qc.is_sendable(
                    result["status"], body.get("confirmed", False))})
            elif path == "/api/v1/sop/change":
                entry = sop.change_scope(body)
                entry.setdefault("id", uuid.uuid4().hex[:8])
                repository.get_repository().log_sop_change(entry)
                _json(self, 200, {"ok": True, "change": entry})
            else:
                _json(self, 404, {"error": "not found"})
        except Exception as e:  # noqa: BLE001
            _json(self, 500, {"error": str(e)})

    # ── 端点实现 ────────────────────────────────────────────
    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n) or b"{}") if n else {}

    def _query(self) -> dict:
        from urllib.parse import parse_qs, urlparse  # noqa: PLC0415
        return {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}

    def _drafts(self, body: dict) -> None:
        """运营助手:家长消息 → 三个备选(A/B/C)+ 逐条风险标注。"""
        uid = body.get("uid", "")
        message = body.get("message", "")
        repo = repository.get_repository()
        customer = repo.get_customer(uid)
        if not customer:
            _json(self, 404, {"error": f"customer {uid} not found"})
            return
        result = assistant.draft_three(customer, message,
                                       body.get("recent_messages"))
        # 家长消息入会话留痕;当前消息计入意向信号
        cid = body.get("cid") or ("C" + uuid.uuid4().hex[:10])
        repo.save_conversation(cid, uid)
        repo.save_message({"id": "MSG" + uuid.uuid4().hex[:10], "cid": cid,
                           "role": "parent", "text": message,
                           "created_at": sop.now_iso(), "sender": uid})
        result["cid"] = cid
        _json(self, 200, result)

    def _send(self, body: dict) -> None:
        """发送闸门 + 全程留痕。红色状态直接拒绝,不产生任何外发。"""
        gate = assistant.send_gate(
            body.get("text", ""), body.get("variant", "CUSTOM"),
            bool(body.get("confirmed", False)), body.get("sender", "teacher"),
            edited=bool(body.get("edited", False)))
        if not gate["sendable"]:
            _json(self, 409, {"error": "质检未通过,禁止发送",
                              "qc_status": gate["qc_status"],
                              "risks": gate["qc_risks"], "gate": gate})
            return
        repository.get_repository().save_message({
            "id": gate["message_id"], "cid": body.get("cid", ""),
            "role": "teacher", "text": body.get("text", ""),
            "created_at": sop.now_iso(), "sender": gate["sender"],
            "variant": gate["variant"], "edited": int(gate["edited"]),
            "confirmed": int(gate["confirmed"]),
            "qc_status": gate["qc_status"], "qc_risks": gate["qc_risks"],
        })
        _json(self, 200, {"ok": True, "gate": gate})

    def _profile(self, uid: str) -> None:
        repo = repository.get_repository()
        customer = repo.get_customer(uid)
        if not customer:
            _json(self, 404, {"error": f"customer {uid} not found"})
            return
        recent = [m["text"] for cid in repo.list_cids_by_uid(uid)
                  for m in repo.list_messages(cid) if m["role"] == "parent"]
        prof = profile_mod.build_profile(customer, recent or None)
        prof["sop"] = sop.board_entry(uid, repo.get_sop_state(uid),
                                      prof["nickname"])
        prof["phone_masked"] = customer.get("phone_masked", "")
        _json(self, 200, prof)

    def _board(self) -> None:
        repo = repository.get_repository()
        q = self._query()
        uid = q.get("uid")
        rows = []
        for c in repo.list_customers(limit=int(q.get("limit", 20))):
            if uid and c["uid"] != uid:
                continue
            rows.append(sop.board_entry(c["uid"], repo.get_sop_state(c["uid"]),
                                        c.get("child_nickname", "")))
        _json(self, 200, {"board": rows})

    def _customers(self) -> None:
        q = self._query()
        repo = repository.get_repository()
        where = {}
        for k in ("signup", "tag_like", "search"):
            if q.get(k):
                where[k] = q[k]
        total = repo.count_customers(where)
        items = repo.list_customers(where, limit=int(q.get("limit", 20)),
                                    offset=int(q.get("offset", 0)))
        for it in items:          # 脱敏:不下发手机号与逐日明细
            it.pop("phone_masked", None)
            it.pop("daily", None)
        _json(self, 200, {"total": total, "items": items})


def serve() -> None:
    server = ThreadingHTTPServer((config.HOST, config.PORT), Handler)
    print(f"🚀 Agent Service  http://{config.HOST}:{config.PORT}"
          f"  (LLM={'on' if config.LLM_ENABLED else 'off'})")
    server.serve_forever()


if __name__ == "__main__":
    serve()
