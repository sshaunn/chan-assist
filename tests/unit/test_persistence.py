"""
Phase 3 单元测试：persistence.py — 落库写入与更新逻辑。
"""
import sqlite3
import pytest
from chan_assist.db import get_connection, init_db
from chan_assist.models import ScanResult, ScanSignal
from chan_assist.persistence import (
    create_scan_run,
    insert_scan_result,
    insert_scan_signal,
    update_scan_run_summary,
    persist_one_result,
)


@pytest.fixture
def db_conn(tmp_path):
    conn = get_connection(str(tmp_path / "test.db"))
    init_db(conn)
    yield conn
    conn.close()


class TestCreateScanRun:
    """create_scan_run"""

    def test_returns_run_id(self, db_conn):
        run_id = create_scan_run(
            db_conn,
            started_at="2026-04-09 10:00:00",
            market="A",
            strategy_name="chan_default",
        )
        assert run_id == 1

    def test_creates_row_with_correct_values(self, db_conn):
        run_id = create_scan_run(
            db_conn,
            started_at="2026-04-09 10:00:00",
            market="A",
            strategy_name="chan_default",
            params_json='{"divergence_rate": 0.8}',
            total_symbols=100,
        )
        row = db_conn.execute("SELECT * FROM scan_run WHERE id=?", (run_id,)).fetchone()
        assert row["started_at"] == "2026-04-09 10:00:00"
        assert row["market"] == "A"
        assert row["strategy_name"] == "chan_default"
        assert row["params_json"] == '{"divergence_rate": 0.8}'
        assert row["total_symbols"] == 100
        assert row["status"] == "running"
        assert row["processed_count"] == 0

    def test_auto_increments_id(self, db_conn):
        id1 = create_scan_run(db_conn, started_at="2026-04-09", market="A", strategy_name="t")
        id2 = create_scan_run(db_conn, started_at="2026-04-09", market="A", strategy_name="t")
        assert id2 == id1 + 1


class TestInsertScanResult:
    """insert_scan_result"""

    def test_hit_result(self, db_conn):
        run_id = create_scan_run(db_conn, started_at="2026-04-09", market="A", strategy_name="t")
        result = ScanResult(
            symbol="000001", name="平安银行", status="hit",
            signal_code="b1", signal_desc="一买", score=0.85,
        )
        result_id = insert_scan_result(db_conn, run_id, result)
        assert result_id == 1
        row = db_conn.execute("SELECT * FROM scan_result WHERE id=?", (result_id,)).fetchone()
        assert row["run_id"] == run_id
        assert row["symbol"] == "000001"
        assert row["status"] == "hit"
        assert row["signal_code"] == "b1"
        assert row["score"] == 0.85

    def test_no_hit_result(self, db_conn):
        run_id = create_scan_run(db_conn, started_at="2026-04-09", market="A", strategy_name="t")
        result = ScanResult(symbol="000002", name="万科A", status="no_hit")
        result_id = insert_scan_result(db_conn, run_id, result)
        row = db_conn.execute("SELECT * FROM scan_result WHERE id=?", (result_id,)).fetchone()
        assert row["status"] == "no_hit"
        assert row["signal_code"] is None
        assert row["error_msg"] is None

    def test_error_result_with_error_msg(self, db_conn):
        run_id = create_scan_run(db_conn, started_at="2026-04-09", market="A", strategy_name="t")
        result = ScanResult(
            symbol="000003", name="测试股", status="error", error_msg="数据拉取超时",
        )
        result_id = insert_scan_result(db_conn, run_id, result)
        row = db_conn.execute("SELECT * FROM scan_result WHERE id=?", (result_id,)).fetchone()
        assert row["status"] == "error"
        assert row["error_msg"] == "数据拉取超时"

    def test_returns_unique_ids(self, db_conn):
        run_id = create_scan_run(db_conn, started_at="2026-04-09", market="A", strategy_name="t")
        ids = []
        for i in range(3):
            r = ScanResult(symbol=f"0000{i}", name=f"s{i}", status="no_hit")
            ids.append(insert_scan_result(db_conn, run_id, r))
        assert len(set(ids)) == 3

    def test_error_without_error_msg_rejected(self, db_conn):
        """error 状态 + error_msg=None 必须被拒绝"""
        run_id = create_scan_run(db_conn, started_at="2026-04-09", market="A", strategy_name="t")
        result = ScanResult(symbol="000001", name="test", status="error")
        with pytest.raises(ValueError, match="error_msg"):
            insert_scan_result(db_conn, run_id, result)

    def test_error_with_empty_error_msg_rejected(self, db_conn):
        """error 状态 + error_msg='' 必须被拒绝"""
        run_id = create_scan_run(db_conn, started_at="2026-04-09", market="A", strategy_name="t")
        result = ScanResult(symbol="000001", name="test", status="error", error_msg="")
        with pytest.raises(ValueError, match="error_msg"):
            insert_scan_result(db_conn, run_id, result)


class TestInsertScanSignal:
    """insert_scan_signal"""

    def test_inserts_signal(self, db_conn):
        run_id = create_scan_run(db_conn, started_at="2026-04-09", market="A", strategy_name="t")
        result = ScanResult(symbol="000001", name="平安银行", status="hit")
        result_id = insert_scan_result(db_conn, run_id, result)
        signal = ScanSignal(signal_type="b1", signal_level="day", signal_value="10.50")
        signal_id = insert_scan_signal(db_conn, result_id, signal)
        assert signal_id >= 1
        row = db_conn.execute("SELECT * FROM scan_signal WHERE id=?", (signal_id,)).fetchone()
        assert row["result_id"] == result_id
        assert row["signal_type"] == "b1"
        assert row["signal_level"] == "day"
        assert row["signal_value"] == "10.50"

    def test_multiple_signals_per_result(self, db_conn):
        run_id = create_scan_run(db_conn, started_at="2026-04-09", market="A", strategy_name="t")
        result = ScanResult(symbol="000001", name="test", status="hit")
        result_id = insert_scan_result(db_conn, run_id, result)
        insert_scan_signal(db_conn, result_id, ScanSignal(signal_type="b1"))
        insert_scan_signal(db_conn, result_id, ScanSignal(signal_type="b2"))
        count = db_conn.execute(
            "SELECT COUNT(*) FROM scan_signal WHERE result_id=?", (result_id,)
        ).fetchone()[0]
        assert count == 2

    def test_rejects_signal_for_no_hit(self, db_conn):
        """insert_scan_signal 写给 no_hit 必须失败"""
        run_id = create_scan_run(db_conn, started_at="2026-04-09", market="A", strategy_name="t")
        result = ScanResult(symbol="000001", name="test", status="no_hit")
        result_id = insert_scan_result(db_conn, run_id, result)
        with pytest.raises(ValueError, match="hit"):
            insert_scan_signal(db_conn, result_id, ScanSignal(signal_type="b1"))

    def test_rejects_signal_for_error(self, db_conn):
        """insert_scan_signal 写给 error 必须失败"""
        run_id = create_scan_run(db_conn, started_at="2026-04-09", market="A", strategy_name="t")
        result = ScanResult(symbol="000001", name="test", status="error", error_msg="err")
        result_id = insert_scan_result(db_conn, run_id, result)
        with pytest.raises(ValueError, match="hit"):
            insert_scan_signal(db_conn, result_id, ScanSignal(signal_type="b1"))

    def test_rejects_signal_for_nonexistent_result(self, db_conn):
        """result_id 不存在必须失败"""
        with pytest.raises(ValueError, match="不存在"):
            insert_scan_signal(db_conn, 9999, ScanSignal(signal_type="b1"))


class TestUpdateScanRunSummary:
    """update_scan_run_summary"""

    def test_update_status(self, db_conn):
        run_id = create_scan_run(db_conn, started_at="2026-04-09", market="A", strategy_name="t")
        update_scan_run_summary(db_conn, run_id, status="success")
        row = db_conn.execute("SELECT status FROM scan_run WHERE id=?", (run_id,)).fetchone()
        assert row["status"] == "success"

    def test_update_counts(self, db_conn):
        run_id = create_scan_run(db_conn, started_at="2026-04-09", market="A", strategy_name="t")
        update_scan_run_summary(
            db_conn, run_id,
            hit_count=5, error_count=2, processed_count=100,
        )
        row = db_conn.execute("SELECT * FROM scan_run WHERE id=?", (run_id,)).fetchone()
        assert row["hit_count"] == 5
        assert row["error_count"] == 2
        assert row["processed_count"] == 100

    def test_update_finished_at(self, db_conn):
        run_id = create_scan_run(db_conn, started_at="2026-04-09", market="A", strategy_name="t")
        update_scan_run_summary(db_conn, run_id, finished_at="2026-04-09 11:00:00")
        row = db_conn.execute("SELECT finished_at FROM scan_run WHERE id=?", (run_id,)).fetchone()
        assert row["finished_at"] == "2026-04-09 11:00:00"

    def test_partial_update_preserves_other_fields(self, db_conn):
        run_id = create_scan_run(
            db_conn, started_at="2026-04-09", market="A", strategy_name="t", total_symbols=50,
        )
        update_scan_run_summary(db_conn, run_id, hit_count=3)
        row = db_conn.execute("SELECT * FROM scan_run WHERE id=?", (run_id,)).fetchone()
        assert row["total_symbols"] == 50  # 未被覆盖
        assert row["hit_count"] == 3

    def test_no_op_when_nothing_passed(self, db_conn):
        run_id = create_scan_run(db_conn, started_at="2026-04-09", market="A", strategy_name="t")
        update_scan_run_summary(db_conn, run_id)  # no-op
        row = db_conn.execute("SELECT status FROM scan_run WHERE id=?", (run_id,)).fetchone()
        assert row["status"] == "running"


class TestPersistOneResult:
    """persist_one_result 封装"""

    def test_hit_writes_result_and_signals(self, db_conn):
        run_id = create_scan_run(db_conn, started_at="2026-04-09", market="A", strategy_name="t")
        result = ScanResult(
            symbol="000001", name="平安银行", status="hit",
            signals=[
                {"signal_type": "b1", "signal_level": "day", "signal_value": "10.50"},
                {"signal_type": "b2", "signal_level": "day", "signal_value": "11.00"},
            ],
        )
        result_id = persist_one_result(db_conn, run_id, result)
        # result 写入
        row = db_conn.execute("SELECT * FROM scan_result WHERE id=?", (result_id,)).fetchone()
        assert row["status"] == "hit"
        # signals 写入
        sigs = db_conn.execute(
            "SELECT * FROM scan_signal WHERE result_id=? ORDER BY id", (result_id,)
        ).fetchall()
        assert len(sigs) == 2
        assert sigs[0]["signal_type"] == "b1"
        assert sigs[1]["signal_type"] == "b2"

    def test_no_hit_writes_result_no_signal(self, db_conn):
        run_id = create_scan_run(db_conn, started_at="2026-04-09", market="A", strategy_name="t")
        result = ScanResult(symbol="000002", name="万科A", status="no_hit")
        result_id = persist_one_result(db_conn, run_id, result)
        row = db_conn.execute("SELECT * FROM scan_result WHERE id=?", (result_id,)).fetchone()
        assert row["status"] == "no_hit"
        count = db_conn.execute(
            "SELECT COUNT(*) FROM scan_signal WHERE result_id=?", (result_id,)
        ).fetchone()[0]
        assert count == 0

    def test_error_writes_result_no_signal(self, db_conn):
        run_id = create_scan_run(db_conn, started_at="2026-04-09", market="A", strategy_name="t")
        result = ScanResult(
            symbol="000003", name="测试股", status="error", error_msg="连接超时",
        )
        result_id = persist_one_result(db_conn, run_id, result)
        row = db_conn.execute("SELECT * FROM scan_result WHERE id=?", (result_id,)).fetchone()
        assert row["status"] == "error"
        assert row["error_msg"] == "连接超时"
        count = db_conn.execute(
            "SELECT COUNT(*) FROM scan_signal WHERE result_id=?", (result_id,)
        ).fetchone()[0]
        assert count == 0

    def test_hit_with_empty_signals_list(self, db_conn):
        """hit 但 signals 为空列表时，不写 signal"""
        run_id = create_scan_run(db_conn, started_at="2026-04-09", market="A", strategy_name="t")
        result = ScanResult(symbol="000001", name="test", status="hit", signals=[])
        result_id = persist_one_result(db_conn, run_id, result)
        count = db_conn.execute(
            "SELECT COUNT(*) FROM scan_signal WHERE result_id=?", (result_id,)
        ).fetchone()[0]
        assert count == 0
