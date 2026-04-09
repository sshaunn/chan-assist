"""
SQLite 连接与建表。

负责数据库初始化和连接管理。
"""
import sqlite3
from pathlib import Path

SQL_CREATE_SCAN_RUN = """
CREATE TABLE IF NOT EXISTS scan_run (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at      TEXT    NOT NULL,
    finished_at     TEXT,
    status          TEXT    NOT NULL DEFAULT 'running'
                    CHECK(status IN ('running', 'success', 'partial_success', 'failed')),
    market          TEXT    NOT NULL,
    strategy_name   TEXT    NOT NULL,
    params_json     TEXT,
    total_symbols   INTEGER NOT NULL DEFAULT 0,
    hit_count       INTEGER NOT NULL DEFAULT 0,
    error_count     INTEGER NOT NULL DEFAULT 0,
    processed_count INTEGER NOT NULL DEFAULT 0,
    notes           TEXT
);
"""

SQL_CREATE_SCAN_RESULT = """
CREATE TABLE IF NOT EXISTS scan_result (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id            INTEGER NOT NULL,
    symbol            TEXT    NOT NULL,
    name              TEXT    NOT NULL,
    scan_time         TEXT    NOT NULL,
    status            TEXT    NOT NULL
                      CHECK(status IN ('hit', 'no_hit', 'error')),
    signal_code       TEXT,
    signal_desc       TEXT,
    score             REAL,
    error_msg         TEXT,
    raw_snapshot_json  TEXT,
    FOREIGN KEY (run_id) REFERENCES scan_run(id)
);
"""

SQL_CREATE_SCAN_SIGNAL = """
CREATE TABLE IF NOT EXISTS scan_signal (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    result_id       INTEGER NOT NULL,
    signal_type     TEXT    NOT NULL,
    signal_level    TEXT,
    signal_value    TEXT,
    extra_json      TEXT,
    FOREIGN KEY (result_id) REFERENCES scan_result(id)
);
"""

_ALL_CREATE_STMTS = [SQL_CREATE_SCAN_RUN, SQL_CREATE_SCAN_RESULT, SQL_CREATE_SCAN_SIGNAL]


def get_connection(db_path: str) -> sqlite3.Connection:
    """获取 SQLite 连接"""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """创建所有必需的表（如果不存在）。可安全重复调用。"""
    for stmt in _ALL_CREATE_STMTS:
        conn.execute(stmt)
    conn.commit()


def get_table_names(conn: sqlite3.Connection) -> list[str]:
    """获取数据库中所有用户表名"""
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name;"
    )
    return [row[0] for row in cursor.fetchall()]


def get_table_columns(conn: sqlite3.Connection, table_name: str) -> list[dict]:
    """获取指定表的列信息"""
    cursor = conn.execute(f"PRAGMA table_info({table_name});")
    return [
        {
            "cid": row[0],
            "name": row[1],
            "type": row[2],
            "notnull": bool(row[3]),
            "default": row[4],
            "pk": bool(row[5]),
        }
        for row in cursor.fetchall()
    ]
