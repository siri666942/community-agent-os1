"""Small SQLite adapter for the application's existing database interface."""
import re
import sqlite3
from datetime import datetime
from pathlib import Path


def translate(sql):
    sql = sql.replace('%%', '%').replace('%s', '?')
    sql = re.sub(r'\bINSERT\s+IGNORE\b', 'INSERT OR IGNORE', sql, flags=re.I)
    sql = re.sub(r'\s+FOR\s+UPDATE\b', '', sql, flags=re.I)
    sql = re.sub(r"JSON_UNQUOTE\(JSON_EXTRACT\(([^,]+),\s*('(?:[^']*)')\)\)", r'json_extract(\1, \2)', sql, flags=re.I)
    sql = re.sub(r"CONCAT\('([^']*)',\s*([\w.]+)\)", r"('\1' || \2)", sql, flags=re.I)
    sql = re.sub(r'ON DUPLICATE KEY UPDATE summary=VALUES\(summary\),source_revision=VALUES\(source_revision\),updated_at=VALUES\(updated_at\)',
                 'ON CONFLICT(user_id) DO UPDATE SET summary=excluded.summary,source_revision=excluded.source_revision,updated_at=excluded.updated_at', sql, flags=re.I)
    return sql


def as_dict(row):
    if row is None:
        return None
    result = dict(row)
    for key in ('time', 'created_at', 'updated_at', 'effective_time', 'original_time', 'expires_at', 'last_message_at'):
        value = result.get(key)
        if isinstance(value, str):
            try:
                result[key] = datetime.fromisoformat(value)
            except ValueError:
                pass
    return result


class Cursor:
    def __init__(self, conn):
        self.cursor = conn.cursor()

    def __enter__(self): return self
    def __exit__(self, *args): self.cursor.close()
    @property
    def rowcount(self): return self.cursor.rowcount
    @property
    def lastrowid(self): return self.cursor.lastrowid
    def execute(self, sql, params=()):
        self.cursor.execute(translate(sql), tuple(v.isoformat(' ') if isinstance(v, datetime) else v for v in params))
        return self
    def executemany(self, sql, params):
        self.cursor.executemany(translate(sql), [tuple(v.isoformat(' ') if isinstance(v, datetime) else v for v in row) for row in params])
        return self
    def fetchone(self): return as_dict(self.cursor.fetchone())
    def fetchall(self): return [as_dict(row) for row in self.cursor.fetchall()]


class Connection:
    is_sqlite = True

    def __init__(self, path):
        self.raw = sqlite3.connect(str(Path(path)), timeout=30, isolation_level=None)
        self.raw.row_factory = sqlite3.Row
        self.raw.execute('PRAGMA foreign_keys=ON')
        self.raw.execute('PRAGMA busy_timeout=30000')
        self.raw.execute('BEGIN IMMEDIATE')

    def cursor(self): return Cursor(self.raw)
    def commit(self): self.raw.commit()
    def rollback(self): self.raw.rollback()
    def close(self): self.raw.close()
