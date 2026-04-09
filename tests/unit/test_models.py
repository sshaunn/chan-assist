"""
Phase 2 单元测试：models.py — 数据模型构造与字段验证。
"""
import pytest
from chan_assist.models import (
    ScanRun, ScanResult, ScanSignal,
    VALID_RESULT_STATUSES, VALID_RUN_STATUSES,
    RESULT_STATUS_HIT, RESULT_STATUS_NO_HIT, RESULT_STATUS_ERROR,
    RUN_STATUS_RUNNING, RUN_STATUS_SUCCESS, RUN_STATUS_PARTIAL_SUCCESS, RUN_STATUS_FAILED,
)


class TestScanRun:
    """ScanRun dataclass"""

    def test_construction_minimal(self):
        run = ScanRun(started_at="2026-04-09 10:00:00", market="A", strategy_name="chan_default")
        assert run.started_at == "2026-04-09 10:00:00"
        assert run.market == "A"
        assert run.strategy_name == "chan_default"
        assert run.status == "running"
        assert run.id is None

    def test_default_counts(self):
        run = ScanRun(started_at="2026-04-09", market="A", strategy_name="test")
        assert run.total_symbols == 0
        assert run.hit_count == 0
        assert run.error_count == 0
        assert run.processed_count == 0

    def test_all_fields(self):
        run = ScanRun(
            started_at="2026-04-09 10:00:00",
            finished_at="2026-04-09 11:00:00",
            status="success",
            market="A",
            strategy_name="chan_default",
            params_json='{"divergence_rate": 0.8}',
            total_symbols=100,
            hit_count=5,
            error_count=2,
            processed_count=100,
            notes="测试运行",
            id=1,
        )
        assert run.finished_at == "2026-04-09 11:00:00"
        assert run.params_json == '{"divergence_rate": 0.8}'
        assert run.id == 1


class TestScanResult:
    """ScanResult dataclass"""

    def test_hit_result(self):
        r = ScanResult(symbol="000001", name="平安银行", status="hit")
        assert r.status == "hit"
        assert r.error_msg is None
        assert r.signals == []

    def test_no_hit_result(self):
        r = ScanResult(symbol="000002", name="万科A", status="no_hit")
        assert r.status == "no_hit"
        assert r.signal_code is None

    def test_error_result(self):
        r = ScanResult(symbol="000003", name="测试股", status="error", error_msg="连接超时")
        assert r.status == "error"
        assert r.error_msg == "连接超时"

    def test_scan_time_auto_fills(self):
        """scan_time 未指定时自动填充当前时间"""
        r = ScanResult(symbol="000001", name="test", status="hit")
        assert r.scan_time != ""
        assert len(r.scan_time) == 19  # YYYY-MM-DD HH:MM:SS

    def test_scan_time_explicit(self):
        r = ScanResult(symbol="000001", name="test", status="hit", scan_time="2026-04-09 10:00:00")
        assert r.scan_time == "2026-04-09 10:00:00"

    def test_signals_list_independent(self):
        """每个实例的 signals 列表独立"""
        r1 = ScanResult(symbol="000001", name="a", status="hit")
        r2 = ScanResult(symbol="000002", name="b", status="hit")
        r1.signals.append({"type": "b1"})
        assert len(r2.signals) == 0


class TestScanRunStatusValidation:
    """ScanRun 模型层 status 校验"""

    def test_rejects_invalid_status(self):
        with pytest.raises(ValueError, match="ScanRun.status"):
            ScanRun(started_at="2026-04-09", market="A", strategy_name="test", status="weird")

    def test_rejects_empty_status(self):
        with pytest.raises(ValueError, match="ScanRun.status"):
            ScanRun(started_at="2026-04-09", market="A", strategy_name="test", status="")

    def test_accepts_all_valid_statuses(self):
        for status in VALID_RUN_STATUSES:
            run = ScanRun(started_at="2026-04-09", market="A", strategy_name="test", status=status)
            assert run.status == status


class TestScanResultStatusValidation:
    """ScanResult 模型层 status 校验"""

    def test_rejects_invalid_status(self):
        with pytest.raises(ValueError, match="ScanResult.status"):
            ScanResult(symbol="000001", name="test", status="weird")

    def test_rejects_empty_status(self):
        with pytest.raises(ValueError, match="ScanResult.status"):
            ScanResult(symbol="000001", name="test", status="")

    def test_rejects_result_status_using_run_values(self):
        """ScanResult 不能使用 scan_run 的 status 值"""
        with pytest.raises(ValueError, match="ScanResult.status"):
            ScanResult(symbol="000001", name="test", status="running")

    def test_accepts_all_valid_statuses(self):
        for status in VALID_RESULT_STATUSES:
            r = ScanResult(symbol="000001", name="test", status=status)
            assert r.status == status


class TestScanSignal:
    """ScanSignal dataclass"""

    def test_construction_minimal(self):
        s = ScanSignal(signal_type="b1")
        assert s.signal_type == "b1"
        assert s.signal_level is None
        assert s.signal_value is None
        assert s.extra_json is None
        assert s.result_id is None

    def test_construction_full(self):
        s = ScanSignal(
            signal_type="b2",
            signal_level="day",
            signal_value="12.50",
            extra_json='{"detail": "xxx"}',
            result_id=42,
            id=7,
        )
        assert s.signal_type == "b2"
        assert s.signal_level == "day"
        assert s.result_id == 42
        assert s.id == 7


class TestStatusConstants:
    """状态常量验证"""

    def test_result_status_values(self):
        assert VALID_RESULT_STATUSES == {"hit", "no_hit", "error"}

    def test_run_status_values(self):
        assert VALID_RUN_STATUSES == {"running", "success", "partial_success", "failed"}

    def test_result_status_constants_match_set(self):
        assert RESULT_STATUS_HIT in VALID_RESULT_STATUSES
        assert RESULT_STATUS_NO_HIT in VALID_RESULT_STATUSES
        assert RESULT_STATUS_ERROR in VALID_RESULT_STATUSES

    def test_run_status_constants_match_set(self):
        assert RUN_STATUS_RUNNING in VALID_RUN_STATUSES
        assert RUN_STATUS_SUCCESS in VALID_RUN_STATUSES
        assert RUN_STATUS_PARTIAL_SUCCESS in VALID_RUN_STATUSES
        assert RUN_STATUS_FAILED in VALID_RUN_STATUSES
