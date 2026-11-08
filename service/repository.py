"""数据访问适配层:面向未来 MySQL 的抽象接口 + 本机 SQLite/Excel 实现。

三层架构:用户 ↔ Web Chat ↔ **Agent Service(本层)** ↔ Database。
Database 现阶段由 Excel 导入 SQLite 充当(scripts/import_excel.py),
后续接 MySQL 时只需新增一个 Repository 实现,业务代码零改动。
"""
from __future__ import annotations

import json
import sqlite3
from abc import ABC, abstractmethod
from typing import Any, Iterable

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
  uid              TEXT PRIMARY KEY,
  group_no         TEXT,
  phone_masked     TEXT,
  child_nickname   TEXT,
  child_age        REAL,
  avg_read_minutes REAL,
  channel          TEXT,
  tags             TEXT,
  parent_role      TEXT,
  added_by         TEXT,
  signup           TEXT,
  signup_amount    REAL,
  expire_date      TEXT,
  order_review     TEXT,
  link_clicks      REAL,
  tested           TEXT,
  test_result      TEXT,
  learning_tags    TEXT,
  total_read_days  REAL,
  daily_json       TEXT
);
CREATE INDEX IF NOT EXISTS idx_customers_signup ON customers(signup);
CREATE INDEX IF NOT EXISTS idx_customers_tags ON customers(tags);

-- 会话留痕(人工发送,AI 只出稿)
CREATE TABLE IF NOT EXISTS conversations (
  cid        TEXT PRIMARY KEY,
  uid        TEXT,
  scenario   TEXT,
  created_at TEXT,
  updated_at TEXT
);
CREATE TABLE IF NOT EXISTS messages (
  id           TEXT PRIMARY KEY,
  cid          TEXT,
  role         TEXT,        -- parent | teacher
  text         TEXT,
  created_at   TEXT,
  sender       TEXT,        -- 老师工号/系统
  variant      TEXT,        -- 选用备选 A/B/C 或 CUSTOM
  edited       INTEGER DEFAULT 0,
  confirmed    INTEGER DEFAULT 0,  -- 黄色状态勾选「我已确认」
  qc_status    TEXT,        -- green | yellow | red
  qc_risks     TEXT         -- JSON 命中明细
);
CREATE INDEX IF NOT EXISTS idx_messages_cid ON messages(cid);

CREATE TABLE IF NOT EXISTS sop_states (
  uid         TEXT PRIMARY KEY,
  stage       TEXT,          -- 当前 SOP 阶段
  entered_at  TEXT,          -- 进入当前阶段时间(ISO)
  last_action TEXT,          -- 最近一次推进动作
  updated_at  TEXT
);

CREATE TABLE IF NOT EXISTS sop_changes (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  uid       TEXT,            -- 空 = 公司默认规则
  field     TEXT,
  old_value TEXT,
  new_value TEXT,
  reason    TEXT,
  scope     TEXT,            -- once | default | log_only
  editor    TEXT,
  created_at TEXT
);
"""


class Repository(ABC):
    """Agent Service 面向数据库的唯一出入口。"""

    # ── 客户 ────────────────────────────────────────────────
    @abstractmethod
    def get_customer(self, uid: str) -> dict | None: ...

    @abstractmethod
    def list_customers(self, where: dict | None = None,
                       limit: int = 50, offset: int = 0) -> list[dict]: ...

    @abstractmethod
    def count_customers(self, where: dict | None = None) -> int: ...

    # ── 会话留痕 ─────────────────────────────────────────────
    @abstractmethod
    def save_message(self, msg: dict) -> None: ...

    @abstractmethod
    def list_messages(self, cid: str) -> list[dict]: ...

    @abstractmethod
    def save_conversation(self, cid: str, uid: str, scenario: str = "") -> None: ...

    @abstractmethod
    def list_cids_by_uid(self, uid: str) -> list[str]: ...

    @abstractmethod
    def parent_texts_by_uid(self) -> dict[str, list[str]]: ...

    @abstractmethod
    def upsert_sop_state(self, uid: str, state: dict) -> None: ...

    @abstractmethod
    def get_sop_state(self, uid: str) -> dict | None: ...

    @abstractmethod
    def log_sop_change(self, entry: dict) -> None: ...


class SQLiteRepository(Repository):
    """本机实现:SQLite(由 Excel 导入)。接口与 MySQL 实现等价。"""

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or config.DB_PATH
        self.con = sqlite3.connect(self.db_path, check_same_thread=False)
        self.con.row_factory = sqlite3.Row
        self.con.executescript(SCHEMA)

    # ── 客户 ────────────────────────────────────────────────
    def _row_to_customer(self, row: sqlite3.Row) -> dict:
        d = dict(row)
        d["daily"] = json.loads(d.pop("daily_json") or "[]")
        tags = d.get("tags") or ""
        d["tag_list"] = [t.strip() for t in tags.split(",") if t.strip()]
        return d

    def get_customer(self, uid: str) -> dict | None:
        row = self.con.execute(
            "SELECT * FROM customers WHERE uid=?", (uid,)).fetchone()
        return self._row_to_customer(row) if row else None

    def list_customers(self, where: dict | None = None,
                       limit: int = 50, offset: int = 0) -> list[dict]:
        sql, params = self._where(where)
        rows = self.con.execute(
            f"SELECT * FROM customers{sql} LIMIT ? OFFSET ?",
            (*params, limit, offset)).fetchall()
        return [self._row_to_customer(r) for r in rows]

    def count_customers(self, where: dict | None = None) -> int:
        sql, params = self._where(where)
        return self.con.execute(
            f"SELECT COUNT(*) FROM customers{sql}", params).fetchone()[0]

    @staticmethod
    def _where(where: dict | None) -> tuple[str, tuple]:
        if not where:
            return "", ()
        parts, params = [], []
        for k, v in where.items():
            if k == "signup":                       # 精确
                parts.append("signup=?"); params.append(v)
            elif k == "tag_like":                   # 标签模糊
                parts.append("tags LIKE ?"); params.append(f"%{v}%")
            elif k == "search":                     # 昵称/群号模糊
                parts.append("(child_nickname LIKE ? OR group_no LIKE ? OR uid LIKE ?)")
                params += [f"%{v}%"] * 3
            elif k == "active_ge":                  # 总阅读天数下限
                parts.append("total_read_days>=?"); params.append(v)
        return (" WHERE " + " AND ".join(parts), tuple(params))

    # ── 会话留痕 ─────────────────────────────────────────────
    def save_message(self, msg: dict) -> None:
        self.con.execute(
            "INSERT OR REPLACE INTO messages"
            "(id,cid,role,text,created_at,sender,variant,edited,confirmed,qc_status,qc_risks)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (msg["id"], msg["cid"], msg["role"], msg["text"], msg["created_at"],
             msg.get("sender", ""), msg.get("variant", ""),
             int(msg.get("edited", 0)), int(msg.get("confirmed", 0)),
             msg.get("qc_status", ""), json.dumps(msg.get("qc_risks", []), ensure_ascii=False)))
        self.con.commit()

    def list_messages(self, cid: str) -> list[dict]:
        rows = self.con.execute(
            "SELECT * FROM messages WHERE cid=? ORDER BY created_at, rowid", (cid,)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["qc_risks"] = json.loads(d.pop("qc_risks") or "[]")
            out.append(d)
        return out

    def save_conversation(self, cid: str, uid: str, scenario: str = "") -> None:
        from datetime import datetime  # noqa: PLC0415
        now = datetime.now().isoformat(timespec="seconds")
        self.con.execute(
            "INSERT OR REPLACE INTO conversations(cid,uid,scenario,created_at,updated_at)"
            " VALUES(?,?,?,?,?)",
            (cid, uid, scenario, now, now))
        self.con.commit()

    def list_cids_by_uid(self, uid: str) -> list[str]:
        rows = self.con.execute(
            "SELECT cid FROM conversations WHERE uid=?", (uid,)).fetchall()
        return [r[0] for r in rows]

    def parent_texts_by_uid(self) -> dict[str, list[str]]:
        """全部家长消息按 uid 聚合(单次 JOIN 查询,供名单批处理读对话信号)。"""
        rows = self.con.execute(
            "SELECT co.uid, m.text FROM messages m"
            " JOIN conversations co ON co.cid = m.cid"
            " WHERE m.role='parent' ORDER BY m.created_at, m.rowid").fetchall()
        out: dict[str, list[str]] = {}
        for r in rows:
            out.setdefault(r[0], []).append(r[1])
        return out

    def upsert_sop_state(self, uid: str, state: dict) -> None:
        self.con.execute(
            "INSERT OR REPLACE INTO sop_states(uid,stage,entered_at,last_action,updated_at)"
            " VALUES(?,?,?,?,?)",
            (uid, state.get("stage", ""), state.get("entered_at", ""),
             state.get("last_action", ""), state.get("updated_at", "")))
        self.con.commit()

    def get_sop_state(self, uid: str) -> dict | None:
        row = self.con.execute(
            "SELECT * FROM sop_states WHERE uid=?", (uid,)).fetchone()
        return dict(row) if row else None

    def log_sop_change(self, entry: dict) -> None:
        self.con.execute(
            "INSERT INTO sop_changes(uid,field,old_value,new_value,reason,scope,editor,created_at)"
            " VALUES(?,?,?,?,?,?,?,?)",
            (entry.get("uid", ""), entry.get("field", ""), entry.get("old_value", ""),
             entry.get("new_value", ""), entry.get("reason", ""), entry.get("scope", "once"),
             entry.get("editor", ""), entry.get("created_at", "")))
        self.con.commit()

    def close(self) -> None:
        self.con.close()


_repo: Repository | None = None


def get_repository() -> Repository:
    """全局单例;将来换成 MySQLRepository 只改这一处。"""
    global _repo
    if _repo is None:
        _repo = SQLiteRepository()
    return _repo
