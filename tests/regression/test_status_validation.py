"""
回归测试：锁定 Phase 2 review 中发现的 status 合法性缺陷。

背景：
- Phase 2 首次审批失败，原因是 scan_run.status 和 scan_result.status
  没有合法值约束，允许任意字符串写入。
- 修复后在 DB 层加了 CHECK 约束，在模型层加了 __post_init__ 校验。
- 这些测试确保该缺陷不再复发。
"""
import sqlite3
import pytest
from chan_assist.db import get_connection, init_db
from chan_assist.models import ScanRun, ScanResult, VALID_RUN_STATUSES, VALID_RESULT_STATUSES


@pytest.fixture
def db_conn(tmp_path):
    conn = get_connection(str(tmp_path / "regression_test.db"))
    init_db(conn)
    yield conn
    conn.close()


class TestStatusValidationRegression:
    """
    锁定缺陷：status 字段曾经允许任意字符串写入。

    修复方案：
    - DB 层：CHECK(status IN (...))
    - 模型层：__post_init__ 校验
    """

    # --- DB 层回归 ---

    def test_db_scan_run_rejects_arbitrary_string(self, db_conn):
        """DB 层必须拒绝非法 scan_run.status"""
        with pytest.raises(sqlite3.IntegrityError):
            db_conn.execute(
                "INSERT INTO scan_run (started_at, status, market, strategy_name) "
                "VALUES ('2026-04-09', 'weird', 'A', 'test')"
            )

    def test_db_scan_result_rejects_arbitrary_string(self, db_conn):
        """DB 层必须拒绝非法 scan_result.status"""
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

    def test_db_scan_run_rejects_empty_string(self, db_conn):
        """空字符串也不是合法 status"""
        with pytest.raises(sqlite3.IntegrityError):
            db_conn.execute(
                "INSERT INTO scan_run (started_at, status, market, strategy_name) "
                "VALUES ('2026-04-09', '', 'A', 'test')"
            )

    def test_db_scan_result_rejects_empty_string(self, db_conn):
        """空字符串也不是合法 status"""
        db_conn.execute(
            "INSERT INTO scan_run (started_at, market, strategy_name) "
            "VALUES ('2026-04-09', 'A', 'test')"
        )
        db_conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            db_conn.execute(
                "INSERT INTO scan_result (run_id, symbol, name, scan_time, status) "
                "VALUES (1, '000001', '平安银行', '2026-04-09', '')"
            )

    def test_db_scan_run_rejects_result_status_values(self, db_conn):
        """scan_run 不能使用 scan_result 的 status 值（如 'hit'）"""
        with pytest.raises(sqlite3.IntegrityError):
            db_conn.execute(
                "INSERT INTO scan_run (started_at, status, market, strategy_name) "
                "VALUES ('2026-04-09', 'hit', 'A', 'test')"
            )

    def test_db_scan_result_rejects_run_status_values(self, db_conn):
        """scan_result 不能使用 scan_run 的 status 值（如 'running'）"""
        db_conn.execute(
            "INSERT INTO scan_run (started_at, market, strategy_name) "
            "VALUES ('2026-04-09', 'A', 'test')"
        )
        db_conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            db_conn.execute(
                "INSERT INTO scan_result (run_id, symbol, name, scan_time, status) "
                "VALUES (1, '000001', '平安银行', '2026-04-09', 'running')"
            )

    # --- 模型层回归 ---

    def test_model_scan_run_rejects_arbitrary_string(self):
        """模型层必须拒绝非法 ScanRun.status"""
        with pytest.raises(ValueError):
            ScanRun(started_at="2026-04-09", market="A", strategy_name="test", status="weird")

    def test_model_scan_result_rejects_arbitrary_string(self):
        """模型层必须拒绝非法 ScanResult.status"""
        with pytest.raises(ValueError):
            ScanResult(symbol="000001", name="test", status="weird")

    def test_model_scan_run_rejects_result_status(self):
        """ScanRun 不能使用 scan_result 的 status 值"""
        with pytest.raises(ValueError):
            ScanRun(started_at="2026-04-09", market="A", strategy_name="test", status="hit")

    def test_model_scan_result_rejects_run_status(self):
        """ScanResult 不能使用 scan_run 的 status 值"""
        with pytest.raises(ValueError):
            ScanResult(symbol="000001", name="test", status="running")
