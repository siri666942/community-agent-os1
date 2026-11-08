"""MySQL connection, scoped transactions and safe timestamp handling."""
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import os
import re
import ssl
import time
from queue import LifoQueue, Empty, Full
from threading import BoundedSemaphore

import pymysql

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo("Asia/Shanghai")
_idle = LifoQueue(maxsize=12)
_slots = BoundedSemaphore(20)


def now():
    return datetime.now(TZ).replace(tzinfo=None)


def connect():
    path = Path(os.environ.get("OPSIE_DB_CONFIG_FILE", ROOT / "配置文件文字版.txt"))
    values = dict(re.findall(r"^(主机|端口|数据库|用户名|密码)\s*[：:]\s*(.*?)\s*$", path.read_text(encoding="utf-8-sig"), re.M))
    cert = Path(os.environ.get("OPSIE_DB_CA", ROOT / ".dbmcp" / "server-cert.pem"))
    context = ssl.create_default_context(cafile=str(cert)) if cert.exists() else ssl.create_default_context()
    if cert.exists():
        context.check_hostname = False
    return pymysql.connect(host=values["主机"], port=int(values["端口"]), user=values["用户名"],
                           password=values["密码"], database=values["数据库"], charset="utf8mb4",
                           cursorclass=pymysql.cursors.DictCursor, ssl=context, connect_timeout=10,
                           read_timeout=30, write_timeout=30, autocommit=False)


def backend():
    return os.environ.get('OPSIE_DB_BACKEND', 'sqlite').lower()


def sqlite_path():
    return Path(os.environ.get('OPSIE_SQLITE_PATH', ROOT / '.dbmcp' / 'opsie-demo.sqlite'))


@contextmanager
def transaction():
    if backend() == 'sqlite':
        from .sqlite_db import Connection
        conn = Connection(sqlite_path())
        try:
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()
        return
    if backend() != 'mysql':
        raise ValueError('OPSIE_DB_BACKEND must be sqlite or mysql')
    _slots.acquire()
    conn = None
    reusable = False
    try:
        try:
            conn, returned_at = _idle.get_nowait()
        except Empty:
            conn = connect()
        else:
            # Recently used connections need no extra network round trip on every request.
            # Revalidate idle connections before reuse, when server idle timeouts are likely.
            if time.monotonic() - returned_at > 20:
                conn.ping(reconnect=True)
        yield conn
        conn.commit()
        reusable = True
    except BaseException:
        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass
        raise
    finally:
        if conn is not None:
            if reusable:
                try:
                    _idle.put_nowait((conn, time.monotonic()))
                except Full:
                    conn.close()
            else:
                conn.close()
        _slots.release()


def json_default(value):
    if isinstance(value, datetime):
        return value.isoformat(sep=" ", timespec="seconds")
    return str(value)
