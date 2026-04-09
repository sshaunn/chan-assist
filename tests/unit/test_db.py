"""
Phase 2 单元测试：db.py — 建表、schema 验证、重复初始化安全。
"""
import sqlite3
import pytest
from chan_assist.db import get_connection, init_db, get_table_names, get_table_columns


@pytest.fixture
def db_conn(tmp_path):
    """提供一个临时 SQLite 连接，测试结束后关闭"""
    conn = get_connection(str(tmp_path / "test.db"))
    yield conn
    conn.close()


class TestInitDb:
    """建表与初始化"""

    def test_init_db_creates_tables(self, db_conn):
        init_db(db_conn)
        tables = get_table_names(db_conn)
        assert "scan_run" in tables
        assert "scan_result" in tables
        assert "scan_signal" in tables

    def test_init_db_creates_exactly_three_tables(self, db_conn):
        init_db(db_conn)
        tables = get_table_names(db_conn)
        assert len(tables) == 3

    def test_init_db_idempotent(self, db_conn):
        """重复初始化不报错"""
        init_db(db_conn)
        init_db(db_conn)
        init_db(db_conn)
        tables = get_table_names(db_conn)
        assert len(tables) == 3

    def test_init_db_idempotent_preserves_data(self, db_conn):
        """重复初始化不丢已有数据"""
        init_db(db_conn)
        db_conn.execute(
            "INSERT INTO scan_run (started_at, status, market, strategy_name) "
            "VALUES ('2026-04-09 10:00:00', 'running', 'A', 'chan_default')"
        )
        db_conn.commit()
        init_db(db_conn)  # 再次初始化
        cursor = db_conn.execute("SELECT COUNT(*) FROM scan_run")
        assert cursor.fetchone()[0] == 1


class TestScanRunSchema:
    """scan_run 表 schema 验证"""

    def test_scan_run_columns(self, db_conn):
        init_db(db_conn)
        cols = get_table_columns(db_conn, "scan_run")
        col_names = {c["name"] for c in cols}
        expected = {
            "id", "started_at", "finished_at", "status", "market",
            "strategy_name", "params_json", "total_symbols",
            "hit_count", "error_count", "processed_count", "notes",
        }
        assert expected.issubset(col_names), f"缺少列: {expected - col_names}"

    def test_scan_run_id_is_pk(self, db_conn):
        init_db(db_conn)
        cols = get_table_columns(db_conn, "scan_run")
        id_col = next(c for c in cols if c["name"] == "id")
        assert id_col["pk"] is True

    def test_scan_run_status_default(self, db_conn):
        init_db(db_conn)
        db_conn.execute(
            "INSERT INTO scan_run (started_at, market, strategy_name) "
            "VALUES ('2026-04-09 10:00:00', 'A', 'chan_default')"
        )
        db_conn.commit()
        row = db_conn.execute("SELECT status FROM scan_run WHERE id=1").fetchone()
        assert row["status"] == "running"

    def test_scan_run_started_at_not_null(self, db_conn):
        init_db(db_conn)
        with pytest.raises(sqlite3.IntegrityError):
            db_conn.execute(
                "INSERT INTO scan_run (market, strategy_name) "
                "VALUES ('A', 'chan_default')"
            )

    def test_scan_run_rejects_invalid_status(self, db_conn):
        """非法 status 必须被 CHECK 约束拒绝"""
        init_db(db_conn)
        with pytest.raises(sqlite3.IntegrityError):
            db_conn.execute(
                "INSERT INTO scan_run (started_at, status, market, strategy_name) "
                "VALUES ('2026-04-09', 'weird', 'A', 'test')"
            )

    def test_scan_run_accepts_all_valid_statuses(self, db_conn):
        """所有合法 status 都能成功插入"""
        init_db(db_conn)
        for status in ("running", "success", "partial_success", "failed"):
            db_conn.execute(
                "INSERT INTO scan_run (started_at, status, market, strategy_name) "
                "VALUES ('2026-04-09', ?, 'A', 'test')",
                (status,),
            )
        db_conn.commit()
        count = db_conn.execute("SELECT COUNT(*) FROM scan_run").fetchone()[0]
        assert count == 4


class TestScanResultSchema:
    """scan_result 表 schema 验证"""

    def test_scan_result_columns(self, db_conn):
        init_db(db_conn)
        cols = get_table_columns(db_conn, "scan_result")
        col_names = {c["name"] for c in cols}
        expected = {
            "id", "run_id", "symbol", "name", "scan_time", "status",
            "signal_code", "signal_desc", "score", "error_msg", "raw_snapshot_json",
        }
        assert expected.issubset(col_names), f"缺少列: {expected - col_names}"

    def test_scan_result_status_not_null(self, db_conn):
        """status 是 NOT NULL"""
        init_db(db_conn)
        # 先插入 scan_run
        db_conn.execute(
            "INSERT INTO scan_run (started_at, market, strategy_name) "
            "VALUES ('2026-04-09', 'A', 'test')"
        )
        db_conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            db_conn.execute(
                "INSERT INTO scan_result (run_id, symbol, name, scan_time) "
                "VALUES (1, '000001', '平安银行', '2026-04-09')"
            )

    def test_scan_result_status_accepts_three_states(self, db_conn):
        """status 可表达 hit / no_hit / error 三态"""
        init_db(db_conn)
        db_conn.execute(
            "INSERT INTO scan_run (started_at, market, strategy_name) "
            "VALUES ('2026-04-09', 'A', 'test')"
        )
        for i, status in enumerate(["hit", "no_hit", "error"], start=1):
            db_conn.execute(
                "INSERT INTO scan_result (run_id, symbol, name, scan_time, status) "
                "VALUES (1, ?, ?, '2026-04-09', ?)",
                (f"00000{i}", f"stock_{i}", status),
            )
        db_conn.commit()
        cursor = db_conn.execute("SELECT status FROM scan_result ORDER BY id")
        statuses = [row["status"] for row in cursor.fetchall()]
        assert statuses == ["hit", "no_hit", "error"]

    def test_scan_result_rejects_invalid_status(self, db_conn):
        """非法 status 必须被 CHECK 约束拒绝"""
        init_db(db_conn)
        db_conn.execute(
            "INSERT INTO scan_run (started_at, market, strategy_name) "
            "VALUES ('2026-04-09', 'A', 'test')"
        )
        db_conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            db_conn.execute(
                "INSERT INTO scan_result (run_id, symbol, name, scan_time, status) "
                "VALUES (1, '000001', '平安银行', '2026-04-09', 'weird')"
            )

    def test_scan_result_run_id_not_null(self, db_conn):
        init_db(db_conn)
        with pytest.raises(sqlite3.IntegrityError):
            db_conn.execute(
                "INSERT INTO scan_result (symbol, name, scan_time, status) "
                "VALUES ('000001', '平安银行', '2026-04-09', 'hit')"
            )

    def test_scan_result_fk_references_scan_run(self, db_conn):
        """外键约束：run_id 必须引用有效的 scan_run.id"""
        init_db(db_conn)
        with pytest.raises(sqlite3.IntegrityError):
            db_conn.execute(
                "INSERT INTO scan_result (run_id, symbol, name, scan_time, status) "
                "VALUES (9999, '000001', '平安银行', '2026-04-09', 'hit')"
            )
            db_conn.commit()


class TestScanSignalSchema:
    """scan_signal 表 schema 验证"""

    def test_scan_signal_columns(self, db_conn):
        init_db(db_conn)
        cols = get_table_columns(db_conn, "scan_signal")
        col_names = {c["name"] for c in cols}
        expected = {
            "id", "result_id", "signal_type", "signal_level",
            "signal_value", "extra_json",
        }
        assert expected.issubset(col_names), f"缺少列: {expected - col_names}"

    def test_scan_signal_result_id_not_null(self, db_conn):
        init_db(db_conn)
        with pytest.raises(sqlite3.IntegrityError):
            db_conn.execute(
                "INSERT INTO scan_signal (signal_type) VALUES ('b1')"
            )

    def test_scan_signal_fk_references_scan_result(self, db_conn):
        """外键约束：result_id 必须引用有效的 scan_result.id"""
        init_db(db_conn)
        with pytest.raises(sqlite3.IntegrityError):
            db_conn.execute(
                "INSERT INTO scan_signal (result_id, signal_type) "
                "VALUES (9999, 'b1')"
            )
            db_conn.commit()


class TestGetConnection:
    """get_connection helper"""

    def test_creates_parent_dirs(self, tmp_path):
        db_path = str(tmp_path / "sub" / "dir" / "test.db")
        conn = get_connection(db_path)
        assert conn is not None
        conn.close()

    def test_row_factory_is_set(self, tmp_path):
        conn = get_connection(str(tmp_path / "test.db"))
        assert conn.row_factory == sqlite3.Row
        conn.close()

    def test_foreign_keys_enabled(self, tmp_path):
        conn = get_connection(str(tmp_path / "test.db"))
        cursor = conn.execute("PRAGMA foreign_keys;")
        assert cursor.fetchone()[0] == 1
        conn.close()
