"""
Phase 3 集成测试：persistence 完整闭环 — create run → persist results → update summary → verify。
"""
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
    conn = get_connection(str(tmp_path / "integration_test.db"))
    init_db(conn)
    yield conn
    conn.close()


class TestPersistenceRoundtrip:
    """完整落库闭环"""

    def test_full_scan_lifecycle(self, db_conn):
        """
        完整扫描生命周期：
        1. 创建 run
        2. 写入 1 hit + signal, 1 no_hit, 1 error
        3. 更新 run 汇总
        4. 验证所有数据正确
        """
        # 1. 创建 run
        run_id = create_scan_run(
            db_conn,
            started_at="2026-04-09 10:00:00",
            market="A",
            strategy_name="chan_default",
            params_json='{"divergence_rate": 0.8}',
            total_symbols=3,
        )

        # 2. 写入三态结果
        # hit
        hit_result = ScanResult(
            symbol="000001", name="平安银行", status="hit",
            signal_code="b1", signal_desc="一买信号", score=0.85,
            signals=[
                {"signal_type": "b1", "signal_level": "day", "signal_value": "10.50"},
            ],
        )
        hit_result_id = persist_one_result(db_conn, run_id, hit_result)

        # no_hit
        nohit_result = ScanResult(symbol="000002", name="万科A", status="no_hit")
        persist_one_result(db_conn, run_id, nohit_result)

        # error
        error_result = ScanResult(
            symbol="000003", name="测试股", status="error", error_msg="数据拉取超时",
        )
        persist_one_result(db_conn, run_id, error_result)

        db_conn.commit()

        # 3. 更新 run 汇总
        update_scan_run_summary(
            db_conn, run_id,
            status="success",
            finished_at="2026-04-09 10:05:00",
            hit_count=1,
            error_count=1,
            processed_count=3,
        )

        # 4. 验证
        # scan_run
        run = db_conn.execute("SELECT * FROM scan_run WHERE id=?", (run_id,)).fetchone()
        assert run["status"] == "success"
        assert run["finished_at"] == "2026-04-09 10:05:00"
        assert run["total_symbols"] == 3
        assert run["hit_count"] == 1
        assert run["error_count"] == 1
        assert run["processed_count"] == 3

        # scan_result — 必须是 3 条
        results = db_conn.execute(
            "SELECT * FROM scan_result WHERE run_id=? ORDER BY id", (run_id,)
        ).fetchall()
        assert len(results) == 3
        assert results[0]["status"] == "hit"
        assert results[0]["signal_code"] == "b1"
        assert results[1]["status"] == "no_hit"
        assert results[2]["status"] == "error"
        assert results[2]["error_msg"] == "数据拉取超时"

        # scan_signal — 只关联 hit
        signals = db_conn.execute("SELECT * FROM scan_signal").fetchall()
        assert len(signals) == 1
        assert signals[0]["result_id"] == hit_result_id
        assert signals[0]["signal_type"] == "b1"

    def test_result_count_equals_total_symbols(self, db_conn):
        """验证 scan_result 条数 == total_symbols（统计闭合）"""
        total = 5
        run_id = create_scan_run(
            db_conn, started_at="2026-04-09", market="A", strategy_name="t",
            total_symbols=total,
        )
        for i in range(total):
            r = ScanResult(symbol=f"0000{i:02d}", name=f"stock_{i}", status="no_hit")
            persist_one_result(db_conn, run_id, r)
        db_conn.commit()

        count = db_conn.execute(
            "SELECT COUNT(*) FROM scan_result WHERE run_id=?", (run_id,)
        ).fetchone()[0]
        assert count == total

    def test_hit_no_hit_error_counts_close(self, db_conn):
        """验证 hit + no_hit + error == total_symbols"""
        run_id = create_scan_run(
            db_conn, started_at="2026-04-09", market="A", strategy_name="t",
            total_symbols=5,
        )
        statuses = ["hit", "hit", "no_hit", "no_hit", "error"]
        for i, status in enumerate(statuses):
            r = ScanResult(
                symbol=f"0000{i:02d}", name=f"s{i}", status=status,
                error_msg="err" if status == "error" else None,
                signals=[{"signal_type": "b1"}] if status == "hit" else [],
            )
            persist_one_result(db_conn, run_id, r)
        db_conn.commit()

        hits = db_conn.execute(
            "SELECT COUNT(*) FROM scan_result WHERE run_id=? AND status='hit'", (run_id,)
        ).fetchone()[0]
        no_hits = db_conn.execute(
            "SELECT COUNT(*) FROM scan_result WHERE run_id=? AND status='no_hit'", (run_id,)
        ).fetchone()[0]
        errors = db_conn.execute(
            "SELECT COUNT(*) FROM scan_result WHERE run_id=? AND status='error'", (run_id,)
        ).fetchone()[0]
        assert hits + no_hits + errors == 5
        assert hits == 2
        assert no_hits == 2
        assert errors == 1

        # signal 数 == hit 数
        sig_count = db_conn.execute("SELECT COUNT(*) FROM scan_signal").fetchone()[0]
        assert sig_count == 2

    def test_signals_only_on_hit_results(self, db_conn):
        """验证 scan_signal 只关联 status='hit' 的 scan_result"""
        run_id = create_scan_run(
            db_conn, started_at="2026-04-09", market="A", strategy_name="t",
        )
        for status in ["hit", "no_hit", "error"]:
            r = ScanResult(
                symbol=f"s_{status}", name=f"n_{status}", status=status,
                error_msg="err" if status == "error" else None,
                signals=[{"signal_type": "b1"}] if status == "hit" else [],
            )
            persist_one_result(db_conn, run_id, r)
        db_conn.commit()

        # 所有 signal 的 result_id 对应的 result 都是 hit
        rows = db_conn.execute(
            "SELECT r.status FROM scan_signal s "
            "JOIN scan_result r ON s.result_id = r.id"
        ).fetchall()
        assert all(row["status"] == "hit" for row in rows)
        assert len(rows) == 1

    def test_error_without_error_msg_rejected_in_roundtrip(self, db_conn):
        """集成验证：error + error_msg=None 在真实 SQLite 环境中被拒绝"""
        run_id = create_scan_run(
            db_conn, started_at="2026-04-09", market="A", strategy_name="t",
        )
        result = ScanResult(symbol="000001", name="test", status="error")
        with pytest.raises(ValueError, match="error_msg"):
            persist_one_result(db_conn, run_id, result)
        # 确认未写入任何 result
        count = db_conn.execute("SELECT COUNT(*) FROM scan_result").fetchone()[0]
        assert count == 0

    def test_direct_signal_to_no_hit_rejected_in_roundtrip(self, db_conn):
        """集成验证：insert_scan_signal 写给 no_hit 在真实 SQLite 环境中被拒绝"""
        run_id = create_scan_run(
            db_conn, started_at="2026-04-09", market="A", strategy_name="t",
        )
        result = ScanResult(symbol="000001", name="test", status="no_hit")
        result_id = insert_scan_result(db_conn, run_id, result)
        db_conn.commit()
        with pytest.raises(ValueError, match="hit"):
            insert_scan_signal(db_conn, result_id, ScanSignal(signal_type="b1"))
        # 确认未写入 signal
        count = db_conn.execute("SELECT COUNT(*) FROM scan_signal").fetchone()[0]
        assert count == 0
