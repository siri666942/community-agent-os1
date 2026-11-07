"""一次性导入:Excel 社群用户基础数据 → SQLite 缓存(数据访问适配层的底层)。

用法:
    python3 -I scripts/import_excel.py [--excel 路径] [--db 路径] [--limit N]

导入完成后的 opsie.db 即 Agent Service 的数据源;后续接 MySQL 时,
repository 层接口不变,只替换适配器(见 service/repository.py)。
"""
import argparse
import os
import sqlite3
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from service import config  # noqa: E402
from service.repository import SCHEMA  # noqa: E402

# 列号 → 字段(以「用户基础数据」表头为准)
COL = {
    "group_no": 0, "ext_id": 1, "phone": 2, "child_nickname": 3, "child_age": 4,
    "avg_read_minutes": 5, "channel": 6, "tags": 8, "parent_role": 9,
    "added_by": 11, "signup": 12, "signup_amount": 13, "expire_date": 14,
    "order_review": 15, "link_clicks": 16, "tested": 17, "test_result": 18,
    "learning_tags": 19, "total_read_days": 20,
}
# 逐日阅读列:开营当天(索引21)…第二十一天(索引64),共 22 天,每天 2 列
DAY0 = 21


def mask_phone(raw) -> str:
    s = str(raw or "")
    if len(s) >= 7 and s.isdigit():
        return s[:3] + "****" + s[-4:]
    return ""


def norm(v):
    if isinstance(v, str):
        return v.strip()
    return v


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--excel", default=config.EXCEL_PATH)
    ap.add_argument("--db", default=config.DB_PATH)
    ap.add_argument("--limit", type=int, default=0, help="仅导入前 N 行(调试用)")
    args = ap.parse_args()

    import openpyxl

    t0 = time.time()
    wb = openpyxl.load_workbook(args.excel, read_only=True)
    ws = wb["用户基础数据"]
    rows = ws.iter_rows(min_row=2, values_only=True)

    os.makedirs(os.path.dirname(args.db), exist_ok=True)
    if os.path.exists(args.db):
        os.remove(args.db)
    con = sqlite3.connect(args.db)
    con.executescript(SCHEMA)

    batch, total = [], 0
    for row in rows:
        uid = str(row[COL["ext_id"]] or "").strip()
        if not uid:
            continue
        days = []
        for d in range(22):
            read = str(row[DAY0 + d * 2] or "").strip() == "是"
            minutes = row[DAY0 + d * 2 + 1] or 0
            try:
                minutes = float(minutes)
            except (TypeError, ValueError):
                minutes = 0.0
            days.append((1 if read else 0, minutes))
        batch.append((
            uid, str(row[COL["group_no"]] or ""), mask_phone(row[COL["phone"]]),
            norm(row[COL["child_nickname"]]) or "",
            _num(row[COL["child_age"]]), _num(row[COL["avg_read_minutes"]]),
            norm(row[COL["channel"]]) or "", norm(row[COL["tags"]]) or "",
            norm(row[COL["parent_role"]]) or "", norm(row[COL["added_by"]]) or "",
            norm(row[COL["signup"]]) or "无", _num(row[COL["signup_amount"]]),
            norm(row[COL["expire_date"]]) or "", norm(row[COL["order_review"]]) or "",
            _num(row[COL["link_clicks"]]), norm(row[COL["tested"]]) or "",
            norm(row[COL["test_result"]]) or "", norm(row[COL["learning_tags"]]) or "",
            _num(row[COL["total_read_days"]]),
            _days_json(days),
        ))
        total += 1
        if len(batch) >= 2000:
            con.executemany(_INSERT, batch)
            con.commit()
            batch = []
            print(f"  已导入 {total} 行…", flush=True)
        if args.limit and total >= args.limit:
            break
    if batch:
        con.executemany(_INSERT, batch)
        con.commit()
    con.execute("ANALYZE")
    con.commit()
    con.close()
    print(f"✅ 导入完成:{total} 行 → {args.db}({time.time() - t0:.0f}s)")


_INSERT = """
INSERT OR REPLACE INTO customers(
  uid, group_no, phone_masked, child_nickname, child_age, avg_read_minutes,
  channel, tags, parent_role, added_by, signup, signup_amount, expire_date,
  order_review, link_clicks, tested, test_result, learning_tags,
  total_read_days, daily_json
) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
"""


def _num(v):
    try:
        return float(v) if v is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _days_json(days) -> str:
    import json
    return json.dumps(days, ensure_ascii=False, separators=(",", ":"))


if __name__ == "__main__":
    main()
