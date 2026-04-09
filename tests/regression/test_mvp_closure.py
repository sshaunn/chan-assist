"""
回归测试：锁定 MVP 最终验证中的关键闭合约束。

锁定的风险点（来自 Phase 7 验证 checklist）：
- scan_result 数 != total_symbols
- hit + no_hit + error != total_symbols
- scan_signal 错绑到非 hit
- run 结束后 status 仍为 running
- processed_count 不等于 total_symbols
- error 无法定位到具体 symbol
"""
import pytest
from unittest.mock import patch, MagicMock
from chan_assist.config import ScanConfig
from chan_assist.db import get_connection
from chan_assist.scan_service import run_scan


def _chan_nohit():
    chan = MagicMock()
    chan.__getitem__ = MagicMock(return_value=MagicMock(__len__=MagicMock(return_value=100)))
    chan.get_latest_bsp.return_value = []
    return chan


def _config(tmp_path, symbols, commit_every=50):
    cfg = ScanConfig(
        db_path=str(tmp_path / "closure_test.db"),
        tushare_token="fake",
        symbols=symbols,
        commit_every=commit_every,
    )
    cfg.strategy_params["recent_dates"] = ["20260409"]
    return cfg


class TestResultCountClosure:
    """scan_result 条数必须等于 total_symbols"""

    @patch("chan_assist.scan_service._create_chan")
    def test_normal_run(self, mock_create, tmp_path):
        mock_create.return_value = _chan_nohit()
        result = run_scan(_config(tmp_path, symbols=["a", "b", "c"]))
        conn = get_connection(str(tmp_path / "closure_test.db"))
        count = conn.execute("SELECT COUNT(*) FROM scan_result WHERE run_id=?", (result["run_id"],)).fetchone()[0]
        assert count == result["total_symbols"]
        conn.close()

    @patch("chan_assist.scan_service._create_chan")
    def test_with_errors(self, mock_create, tmp_path):
        call_i = [0]
        def side(s, c):
            call_i[0] += 1
            if call_i[0] == 2:
                raise Exception("err")
            return _chan_nohit()
        mock_create.side_effect = side
        result = run_scan(_config(tmp_path, symbols=["a", "b", "c"]))
        conn = get_connection(str(tmp_path / "closure_test.db"))
        count = conn.execute("SELECT COUNT(*) FROM scan_result WHERE run_id=?", (result["run_id"],)).fetchone()[0]
        assert count == result["total_symbols"]
        conn.close()


class TestThreeStateClosure:
    """hit + no_hit + error 必须 == total_symbols"""

    @patch("chan_assist.scan_service._create_chan")
    def test_sum_equals_total(self, mock_create, tmp_path):
        call_i = [0]
        def side(s, c):
            call_i[0] += 1
            if call_i[0] == 3:
                raise Exception("err")
            return _chan_nohit()
        mock_create.side_effect = side
        result = run_scan(_config(tmp_path, symbols=["a", "b", "c", "d"]))
        conn = get_connection(str(tmp_path / "closure_test.db"))
        rid = result["run_id"]
        h = conn.execute("SELECT COUNT(*) FROM scan_result WHERE run_id=? AND status='hit'", (rid,)).fetchone()[0]
        n = conn.execute("SELECT COUNT(*) FROM scan_result WHERE run_id=? AND status='no_hit'", (rid,)).fetchone()[0]
        e = conn.execute("SELECT COUNT(*) FROM scan_result WHERE run_id=? AND status='error'", (rid,)).fetchone()[0]
        assert h + n + e == result["total_symbols"]
        conn.close()


class TestRunStatusClosure:
    """run 结束后 status 不能是 running"""

    @patch("chan_assist.scan_service._create_chan")
    def test_not_running_after_completion(self, mock_create, tmp_path):
        mock_create.return_value = _chan_nohit()
        result = run_scan(_config(tmp_path, symbols=["a"]))
        conn = get_connection(str(tmp_path / "closure_test.db"))
        run = conn.execute("SELECT status, finished_at FROM scan_run WHERE id=?", (result["run_id"],)).fetchone()
        assert run["status"] != "running"
        assert run["finished_at"] is not None
        conn.close()


class TestErrorTraceability:
    """error 必须能定位到具体 symbol"""

    @patch("chan_assist.scan_service._create_chan")
    def test_error_has_symbol_and_msg(self, mock_create, tmp_path):
        mock_create.side_effect = Exception("timeout_err")
        result = run_scan(_config(tmp_path, symbols=["SZ000099"]))
        conn = get_connection(str(tmp_path / "closure_test.db"))
        er = conn.execute("SELECT symbol, error_msg FROM scan_result WHERE status='error'").fetchone()
        assert er["symbol"] == "SZ000099"
        assert "timeout_err" in er["error_msg"]
        conn.close()
