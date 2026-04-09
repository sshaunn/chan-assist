"""
回归测试：锁定 Phase 3 持久化层的关键失败模式。

锁定的风险点（来自 task plan regression 要求 + Phase 3 review 失败项）：
- no_hit 被漏写
- error 没带 error_msg → 必须被拒绝
- signal 被错误写给 no_hit / error → 必须被拒绝
- run 汇总统计不闭合
"""
import pytest
from chan_assist.db import get_connection, init_db
from chan_assist.models import ScanResult, ScanSignal
from chan_assist.persistence import (
    create_scan_run,
    insert_scan_result,
    insert_scan_signal,
    persist_one_result,
    update_scan_run_summary,
)


@pytest.fixture
def db_conn(tmp_path):
    conn = get_connection(str(tmp_path / "regression_test.db"))
    init_db(conn)
    yield conn
    conn.close()


class TestNoHitMustBeWritten:
    """no_hit 不得被漏写"""

    def test_no_hit_creates_scan_result_row(self, db_conn):
        run_id = create_scan_run(db_conn, started_at="2026-04-09", market="A", strategy_name="t")
        result = ScanResult(symbol="000001", name="test", status="no_hit")
        persist_one_result(db_conn, run_id, result)
        db_conn.commit()
        count = db_conn.execute(
            "SELECT COUNT(*) FROM scan_result WHERE run_id=? AND status='no_hit'", (run_id,)
        ).fetchone()[0]
        assert count == 1, "no_hit 结果未被写入 scan_result"

    def test_all_three_states_written(self, db_conn):
        """hit + no_hit + error 全部都要写 scan_result"""
        run_id = create_scan_run(db_conn, started_at="2026-04-09", market="A", strategy_name="t")
        for status in ["hit", "no_hit", "error"]:
            r = ScanResult(
                symbol=f"s_{status}", name=f"n_{status}", status=status,
                error_msg="err" if status == "error" else None,
            )
            persist_one_result(db_conn, run_id, r)
        db_conn.commit()
        count = db_conn.execute(
            "SELECT COUNT(*) FROM scan_result WHERE run_id=?", (run_id,)
        ).fetchone()[0]
        assert count == 3, "三态结果未全量落库"


class TestErrorMustHaveErrorMsg:
    """error 必须能带 error_msg"""

    def test_error_msg_persisted(self, db_conn):
        run_id = create_scan_run(db_conn, started_at="2026-04-09", market="A", strategy_name="t")
        result = ScanResult(
            symbol="000001", name="test", status="error", error_msg="连接超时",
        )
        result_id = persist_one_result(db_conn, run_id, result)
        db_conn.commit()
        row = db_conn.execute(
            "SELECT error_msg FROM scan_result WHERE id=?", (result_id,)
        ).fetchone()
        assert row["error_msg"] == "连接超时", "error_msg 未被正确持久化"

    def test_error_without_error_msg_rejected(self, db_conn):
        """error 状态必须携带非空 error_msg，否则拒绝写入"""
        run_id = create_scan_run(db_conn, started_at="2026-04-09", market="A", strategy_name="t")
        result = ScanResult(symbol="000001", name="test", status="error")
        with pytest.raises(ValueError, match="error_msg"):
            persist_one_result(db_conn, run_id, result)

    def test_error_with_empty_string_error_msg_rejected(self, db_conn):
        """error_msg 为空字符串也应被拒绝"""
        run_id = create_scan_run(db_conn, started_at="2026-04-09", market="A", strategy_name="t")
        result = ScanResult(symbol="000001", name="test", status="error", error_msg="")
        with pytest.raises(ValueError, match="error_msg"):
            persist_one_result(db_conn, run_id, result)


class TestSignalNotWrittenForNonHit:
    """signal 不得被写给 no_hit / error"""

    def test_no_signal_for_no_hit(self, db_conn):
        run_id = create_scan_run(db_conn, started_at="2026-04-09", market="A", strategy_name="t")
        result = ScanResult(symbol="000001", name="test", status="no_hit")
        result_id = persist_one_result(db_conn, run_id, result)
        db_conn.commit()
        count = db_conn.execute(
            "SELECT COUNT(*) FROM scan_signal WHERE result_id=?", (result_id,)
        ).fetchone()[0]
        assert count == 0, "no_hit 结果不应有 scan_signal"

    def test_no_signal_for_error(self, db_conn):
        run_id = create_scan_run(db_conn, started_at="2026-04-09", market="A", strategy_name="t")
        result = ScanResult(
            symbol="000001", name="test", status="error", error_msg="err",
        )
        result_id = persist_one_result(db_conn, run_id, result)
        db_conn.commit()
        count = db_conn.execute(
            "SELECT COUNT(*) FROM scan_signal WHERE result_id=?", (result_id,)
        ).fetchone()[0]
        assert count == 0, "error 结果不应有 scan_signal"

    def test_no_signal_for_error_even_with_signals_field(self, db_conn):
        """即使 ScanResult.signals 列表有内容，error 也不应写 signal"""
        run_id = create_scan_run(db_conn, started_at="2026-04-09", market="A", strategy_name="t")
        result = ScanResult(
            symbol="000001", name="test", status="error", error_msg="err",
            signals=[{"signal_type": "b1"}],
        )
        result_id = persist_one_result(db_conn, run_id, result)
        db_conn.commit()
        count = db_conn.execute(
            "SELECT COUNT(*) FROM scan_signal WHERE result_id=?", (result_id,)
        ).fetchone()[0]
        assert count == 0, "error 结果即使有 signals 字段也不应写 scan_signal"


class TestInsertScanSignalHitOnly:
    """insert_scan_signal 必须拒绝写给 non-hit 结果（Phase 3 review 失败项）"""

    def test_insert_signal_to_no_hit_rejected(self, db_conn):
        """直接调用 insert_scan_signal 写给 no_hit 结果必须失败"""
        run_id = create_scan_run(db_conn, started_at="2026-04-09", market="A", strategy_name="t")
        result = ScanResult(symbol="000001", name="test", status="no_hit")
        result_id = insert_scan_result(db_conn, run_id, result)
        db_conn.commit()
        with pytest.raises(ValueError, match="hit"):
            insert_scan_signal(db_conn, result_id, ScanSignal(signal_type="b1"))

    def test_insert_signal_to_error_rejected(self, db_conn):
        """直接调用 insert_scan_signal 写给 error 结果必须失败"""
        run_id = create_scan_run(db_conn, started_at="2026-04-09", market="A", strategy_name="t")
        result = ScanResult(symbol="000001", name="test", status="error", error_msg="err")
        result_id = insert_scan_result(db_conn, run_id, result)
        db_conn.commit()
        with pytest.raises(ValueError, match="hit"):
            insert_scan_signal(db_conn, result_id, ScanSignal(signal_type="b1"))

    def test_insert_signal_to_hit_allowed(self, db_conn):
        """写给 hit 结果正常通过"""
        run_id = create_scan_run(db_conn, started_at="2026-04-09", market="A", strategy_name="t")
        result = ScanResult(symbol="000001", name="test", status="hit")
        result_id = insert_scan_result(db_conn, run_id, result)
        db_conn.commit()
        signal_id = insert_scan_signal(db_conn, result_id, ScanSignal(signal_type="b1"))
        assert signal_id >= 1

    def test_insert_signal_to_nonexistent_result_rejected(self, db_conn):
        """result_id 不存在也必须失败"""
        with pytest.raises(ValueError, match="不存在"):
            insert_scan_signal(db_conn, 9999, ScanSignal(signal_type="b1"))


class TestRunSummaryClosure:
    """run 汇总统计必须闭合"""

    def test_summary_matches_actual_counts(self, db_conn):
        """更新后的汇总数与实际 result 条数一致"""
        run_id = create_scan_run(
            db_conn, started_at="2026-04-09", market="A", strategy_name="t",
            total_symbols=4,
        )
        statuses = ["hit", "no_hit", "no_hit", "error"]
        for i, status in enumerate(statuses):
            r = ScanResult(
                symbol=f"s{i}", name=f"n{i}", status=status,
                error_msg="err" if status == "error" else None,
            )
            persist_one_result(db_conn, run_id, r)
        db_conn.commit()

        # 手动统计
        actual_hits = db_conn.execute(
            "SELECT COUNT(*) FROM scan_result WHERE run_id=? AND status='hit'", (run_id,)
        ).fetchone()[0]
        actual_errors = db_conn.execute(
            "SELECT COUNT(*) FROM scan_result WHERE run_id=? AND status='error'", (run_id,)
        ).fetchone()[0]
        actual_total = db_conn.execute(
            "SELECT COUNT(*) FROM scan_result WHERE run_id=?", (run_id,)
        ).fetchone()[0]

        update_scan_run_summary(
            db_conn, run_id,
            hit_count=actual_hits,
            error_count=actual_errors,
            processed_count=actual_total,
            status="success",
        )

        run = db_conn.execute("SELECT * FROM scan_run WHERE id=?", (run_id,)).fetchone()
        assert run["hit_count"] == 1
        assert run["error_count"] == 1
        assert run["processed_count"] == 4
        assert run["total_symbols"] == 4
        assert run["hit_count"] + run["error_count"] <= run["processed_count"]
