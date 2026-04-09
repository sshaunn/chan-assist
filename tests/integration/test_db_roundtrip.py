"""
Phase 2 集成测试：SQLite 最小闭环 — init → insert → query roundtrip。
"""
import sqlite3
import pytest
from chan_assist.db import get_connection, init_db


@pytest.fixture
def db_conn(tmp_path):
    conn = get_connection(str(tmp_path / "integration_test.db"))
    init_db(conn)
    yield conn
    conn.close()


class TestDbRoundtrip:
    """端到端：建表 → 插入三表 → 查询回读"""

    def test_full_roundtrip(self, db_conn):
        """完整闭环：insert scan_run → scan_result(三态) → scan_signal → 回读验证"""
        # 1. 插入 scan_run
        db_conn.execute(
            "INSERT INTO scan_run (started_at, status, market, strategy_name, params_json, total_symbols) "
            "VALUES ('2026-04-09 10:00:00', 'running', 'A', 'chan_default', '{\"divergence_rate\": 0.8}', 3)"
        )
        db_conn.commit()

        run = db_conn.execute("SELECT * FROM scan_run WHERE id=1").fetchone()
        assert run["status"] == "running"
        assert run["market"] == "A"
        assert run["total_symbols"] == 3

        # 2. 插入 3 条 scan_result（三态全覆盖）
        results_data = [
            (1, "000001", "平安银行", "2026-04-09 10:01:00", "hit", "b1", "一买信号", 0.85, None, None),
            (1, "000002", "万科A", "2026-04-09 10:01:01", "no_hit", None, None, None, None, None),
            (1, "000003", "测试股", "2026-04-09 10:01:02", "error", None, None, None, "数据拉取超时", None),
        ]
        db_conn.executemany(
            "INSERT INTO scan_result "
            "(run_id, symbol, name, scan_time, status, signal_code, signal_desc, score, error_msg, raw_snapshot_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            results_data,
        )
        db_conn.commit()

        results = db_conn.execute("SELECT * FROM scan_result ORDER BY id").fetchall()
        assert len(results) == 3
        assert results[0]["status"] == "hit"
        assert results[0]["signal_code"] == "b1"
        assert results[0]["score"] == 0.85
        assert results[1]["status"] == "no_hit"
        assert results[1]["signal_code"] is None
        assert results[2]["status"] == "error"
        assert results[2]["error_msg"] == "数据拉取超时"

        # 3. 只对 hit 结果插入 scan_signal
        hit_result_id = results[0]["id"]
        db_conn.execute(
            "INSERT INTO scan_signal (result_id, signal_type, signal_level, signal_value, extra_json) "
            "VALUES (?, 'b1', 'day', '10.50', '{\"bi_idx\": 42}')",
            (hit_result_id,),
        )
        db_conn.commit()

        signals = db_conn.execute("SELECT * FROM scan_signal").fetchall()
        assert len(signals) == 1
        assert signals[0]["result_id"] == hit_result_id
        assert signals[0]["signal_type"] == "b1"
        assert signals[0]["signal_level"] == "day"
        assert signals[0]["signal_value"] == "10.50"

        # 4. 更新 scan_run 汇总
        db_conn.execute(
            "UPDATE scan_run SET status='success', finished_at='2026-04-09 10:05:00', "
            "hit_count=1, error_count=1, processed_count=3 WHERE id=1"
        )
        db_conn.commit()

        run_final = db_conn.execute("SELECT * FROM scan_run WHERE id=1").fetchone()
        assert run_final["status"] == "success"
        assert run_final["finished_at"] == "2026-04-09 10:05:00"
        assert run_final["hit_count"] == 1
        assert run_final["error_count"] == 1
        assert run_final["processed_count"] == 3

    def test_scan_result_count_matches_total(self, db_conn):
        """验证 scan_result 条数 == total_symbols"""
        total = 5
        db_conn.execute(
            "INSERT INTO scan_run (started_at, market, strategy_name, total_symbols) "
            "VALUES ('2026-04-09', 'A', 'test', ?)",
            (total,),
        )
        for i in range(total):
            db_conn.execute(
                "INSERT INTO scan_result (run_id, symbol, name, scan_time, status) "
                "VALUES (1, ?, ?, '2026-04-09', 'no_hit')",
                (f"0000{i:02d}", f"stock_{i}"),
            )
        db_conn.commit()

        count = db_conn.execute("SELECT COUNT(*) FROM scan_result WHERE run_id=1").fetchone()[0]
        run = db_conn.execute("SELECT total_symbols FROM scan_run WHERE id=1").fetchone()
        assert count == run["total_symbols"]

    def test_signal_only_linked_to_hit(self, db_conn):
        """验证 scan_signal 只关联 hit 结果"""
        db_conn.execute(
            "INSERT INTO scan_run (started_at, market, strategy_name) "
            "VALUES ('2026-04-09', 'A', 'test')"
        )
        # hit result
        db_conn.execute(
            "INSERT INTO scan_result (run_id, symbol, name, scan_time, status) "
            "VALUES (1, '000001', 'A', '2026-04-09', 'hit')"
        )
        # no_hit result
        db_conn.execute(
            "INSERT INTO scan_result (run_id, symbol, name, scan_time, status) "
            "VALUES (1, '000002', 'B', '2026-04-09', 'no_hit')"
        )
        db_conn.commit()

        # 对 hit 插入 signal
        db_conn.execute(
            "INSERT INTO scan_signal (result_id, signal_type) VALUES (1, 'b1')"
        )
        db_conn.commit()

        # 验证 signal 只关联 hit
        signals = db_conn.execute(
            "SELECT s.* FROM scan_signal s "
            "JOIN scan_result r ON s.result_id = r.id "
            "WHERE r.status = 'hit'"
        ).fetchall()
        assert len(signals) == 1

        all_signals = db_conn.execute("SELECT COUNT(*) FROM scan_signal").fetchone()[0]
        assert all_signals == 1  # 没有多余的 signal

    def test_invalid_scan_run_status_rejected_in_roundtrip(self, db_conn):
        """集成验证：非法 scan_run.status 在真实 SQLite 中被 CHECK 拒绝"""
        with pytest.raises(sqlite3.IntegrityError):
            db_conn.execute(
                "INSERT INTO scan_run (started_at, status, market, strategy_name) "
                "VALUES ('2026-04-09', 'invalid_status', 'A', 'test')"
            )

    def test_invalid_scan_result_status_rejected_in_roundtrip(self, db_conn):
        """集成验证：非法 scan_result.status 在真实 SQLite 中被 CHECK 拒绝"""
        db_conn.execute(
            "INSERT INTO scan_run (started_at, market, strategy_name) "
            "VALUES ('2026-04-09', 'A', 'test')"
        )
        db_conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            db_conn.execute(
                "INSERT INTO scan_result (run_id, symbol, name, scan_time, status) "
                "VALUES (1, '000001', '平安银行', '2026-04-09', 'invalid_status')"
            )

    def test_update_scan_run_to_invalid_status_rejected(self, db_conn):
        """集成验证：UPDATE scan_run.status 到非法值也被拒绝"""
        db_conn.execute(
            "INSERT INTO scan_run (started_at, market, strategy_name) "
            "VALUES ('2026-04-09', 'A', 'test')"
        )
        db_conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            db_conn.execute("UPDATE scan_run SET status='bogus' WHERE id=1")

    def test_reopen_connection_preserves_data(self, tmp_path):
        """关闭连接后重新打开，数据仍在"""
        db_path = str(tmp_path / "reopen_test.db")

        conn1 = get_connection(db_path)
        init_db(conn1)
        conn1.execute(
            "INSERT INTO scan_run (started_at, market, strategy_name) "
            "VALUES ('2026-04-09', 'A', 'test')"
        )
        conn1.commit()
        conn1.close()

        conn2 = get_connection(db_path)
        count = conn2.execute("SELECT COUNT(*) FROM scan_run").fetchone()[0]
        assert count == 1
        conn2.close()
