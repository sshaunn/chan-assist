"""
回归测试：锁定 Phase 6 批量扫描的关键失败模式。

锁定的风险点（来自 task plan regression 要求）：
- 中途异常导致 processed_count 不准
- scan_result 条数少于扫描股票数
- scan_signal 错绑到 no_hit / error
- commit_every 行为不稳定
- run 状态未正确收口
"""
import pytest
from unittest.mock import patch, MagicMock
from chan_assist.config import ScanConfig
from chan_assist.db import get_connection
from chan_assist.models import ScanResult
from chan_assist.scan_service import run_scan


def _config(tmp_path, symbols, commit_every=50):
    cfg = ScanConfig(
        db_path=str(tmp_path / "regression_test.db"),
        tushare_token="fake",
        symbols=symbols,
        commit_every=commit_every,
    )
    cfg.strategy_params["recent_dates"] = ["20260409"]
    return cfg


def _make_chan_nohit():
    chan = MagicMock()
    chan.__getitem__ = MagicMock(return_value=MagicMock(__len__=MagicMock(return_value=100)))
    chan.get_latest_bsp.return_value = []
    return chan


class TestProcessedCountAccuracy:
    """processed_count 必须精确"""

    @patch("chan_assist.scan_service._create_chan")
    def test_all_succeed_count_equals_total(self, mock_create, tmp_path):
        mock_create.return_value = _make_chan_nohit()
        config = _config(tmp_path, symbols=[f"s{i}" for i in range(5)])
        result = run_scan(config)
        assert result["processed_count"] == 5
        assert result["processed_count"] == result["total_symbols"]

    @patch("chan_assist.scan_service._create_chan")
    def test_errors_still_counted_in_processed(self, mock_create, tmp_path):
        """error 结果也计入 processed_count"""
        call_i = [0]
        def side(symbol, config):
            call_i[0] += 1
            if call_i[0] == 3:
                raise Exception("boom")
            return _make_chan_nohit()
        mock_create.side_effect = side

        config = _config(tmp_path, symbols=[f"s{i}" for i in range(5)])
        result = run_scan(config)
        assert result["processed_count"] == 5, "error 也应计入 processed_count"


class TestResultCountMatchesPool:
    """scan_result 条数 == 股票池大小"""

    @patch("chan_assist.scan_service._create_chan")
    def test_result_count_equals_pool_size(self, mock_create, tmp_path):
        mock_create.return_value = _make_chan_nohit()
        config = _config(tmp_path, symbols=[f"s{i}" for i in range(4)])
        result = run_scan(config)

        conn = get_connection(str(tmp_path / "regression_test.db"))
        count = conn.execute("SELECT COUNT(*) FROM scan_result WHERE run_id=?", (result["run_id"],)).fetchone()[0]
        assert count == 4
        conn.close()

    @patch("chan_assist.scan_service._create_chan")
    def test_result_count_with_errors(self, mock_create, tmp_path):
        """即使有 error，result 条数仍等于池大小"""
        call_i = [0]
        def side(symbol, config):
            call_i[0] += 1
            if call_i[0] % 2 == 0:
                raise Exception("err")
            return _make_chan_nohit()
        mock_create.side_effect = side

        config = _config(tmp_path, symbols=[f"s{i}" for i in range(6)])
        result = run_scan(config)

        conn = get_connection(str(tmp_path / "regression_test.db"))
        count = conn.execute("SELECT COUNT(*) FROM scan_result WHERE run_id=?", (result["run_id"],)).fetchone()[0]
        assert count == 6
        conn.close()


class TestSignalNeverMisbound:
    """scan_signal 不得错绑到 no_hit / error"""

    @patch("chan_assist.scan_service._create_chan")
    def test_no_signal_for_nohit_or_error(self, mock_create, tmp_path):
        call_i = [0]
        def side(symbol, config):
            call_i[0] += 1
            if call_i[0] == 3:
                raise Exception("err")
            return _make_chan_nohit()
        mock_create.side_effect = side

        config = _config(tmp_path, symbols=[f"s{i}" for i in range(4)])
        result = run_scan(config)

        conn = get_connection(str(tmp_path / "regression_test.db"))
        count = conn.execute("SELECT COUNT(*) FROM scan_signal").fetchone()[0]
        assert count == 0, "no_hit/error 不应有 scan_signal"
        conn.close()


class TestRunStatusClosure:
    """run 状态必须正确收口"""

    @patch("chan_assist.scan_service._create_chan")
    def test_run_has_finished_at(self, mock_create, tmp_path):
        mock_create.return_value = _make_chan_nohit()
        config = _config(tmp_path, symbols=["a"])
        result = run_scan(config)

        conn = get_connection(str(tmp_path / "regression_test.db"))
        run = conn.execute("SELECT finished_at FROM scan_run WHERE id=?", (result["run_id"],)).fetchone()
        assert run["finished_at"] is not None
        conn.close()

    @patch("chan_assist.scan_service._create_chan")
    def test_run_status_not_running_after_completion(self, mock_create, tmp_path):
        mock_create.return_value = _make_chan_nohit()
        config = _config(tmp_path, symbols=["a"])
        result = run_scan(config)

        conn = get_connection(str(tmp_path / "regression_test.db"))
        run = conn.execute("SELECT status FROM scan_run WHERE id=?", (result["run_id"],)).fetchone()
        assert run["status"] != "running"
        conn.close()
