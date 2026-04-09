"""
Phase 6 单元测试：run_scan 批量扫描逻辑。
"""
import pytest
from unittest.mock import patch, MagicMock
from chan_assist.config import ScanConfig
from chan_assist.models import (
    ScanResult,
    RUN_STATUS_SUCCESS, RUN_STATUS_PARTIAL_SUCCESS, RUN_STATUS_FAILED,
)
from chan_assist.scan_service import run_scan


def _config(tmp_path, symbols, commit_every=50):
    return ScanConfig(
        db_path=str(tmp_path / "test.db"),
        tushare_token="fake",
        symbols=symbols,
        commit_every=commit_every,
    )


def _chan_nohit():
    chan = MagicMock()
    chan.__getitem__ = MagicMock(return_value=MagicMock(__len__=MagicMock(return_value=100)))
    chan.get_latest_bsp.return_value = []
    return chan


class TestRunScanStatusLogic:
    """run 状态流转"""

    @patch("chan_assist.scan_service._create_chan")
    def test_all_no_hit_returns_success(self, mock_create, tmp_path):
        mock_create.return_value = _chan_nohit()
        result = run_scan(_config(tmp_path, symbols=["a", "b"]))
        assert result["status"] == RUN_STATUS_SUCCESS

    @patch("chan_assist.scan_service._create_chan")
    def test_some_errors_returns_partial_success(self, mock_create, tmp_path):
        call_i = [0]
        def side(symbol, config):
            call_i[0] += 1
            if call_i[0] == 2:
                raise Exception("err")
            return _chan_nohit()
        mock_create.side_effect = side
        result = run_scan(_config(tmp_path, symbols=["a", "b"]))
        assert result["status"] == RUN_STATUS_PARTIAL_SUCCESS

    @patch("chan_assist.scan_service._create_chan")
    def test_all_errors_returns_failed(self, mock_create, tmp_path):
        mock_create.side_effect = Exception("err")
        result = run_scan(_config(tmp_path, symbols=["a", "b"]))
        assert result["status"] == RUN_STATUS_FAILED


class TestRunScanCounts:
    """统计闭合"""

    @patch("chan_assist.scan_service._create_chan")
    def test_counts_correct(self, mock_create, tmp_path):
        bsp = MagicMock()
        bsp.is_buy = True
        bsp.type = [MagicMock(value="1")]
        bsp.klu.time.year, bsp.klu.time.month, bsp.klu.time.day = 2026, 4, 9
        bsp.klu.close = 10.0
        bsp.bi.idx = 1

        chan_hit = MagicMock()
        chan_hit.__getitem__ = MagicMock(return_value=MagicMock(__len__=MagicMock(return_value=100)))
        chan_hit.get_latest_bsp.return_value = [bsp]

        call_i = [0]
        def side(symbol, config):
            call_i[0] += 1
            if call_i[0] <= 2:
                return chan_hit
            elif call_i[0] == 3:
                return _chan_nohit()
            else:
                raise Exception("err")
        mock_create.side_effect = side

        cfg = _config(tmp_path, symbols=["a", "b", "c", "d"])
        cfg.strategy_params["recent_dates"] = ["20260409"]
        result = run_scan(cfg)

        assert result["total_symbols"] == 4
        assert result["processed_count"] == 4
        assert result["hit_count"] == 2
        assert result["error_count"] == 1

    @patch("chan_assist.scan_service._create_chan")
    def test_processed_count_equals_total(self, mock_create, tmp_path):
        mock_create.return_value = _chan_nohit()
        result = run_scan(_config(tmp_path, symbols=["a", "b", "c"]))
        assert result["processed_count"] == result["total_symbols"]

    @patch("chan_assist.scan_service._create_chan")
    def test_empty_pool(self, mock_create, tmp_path):
        """空白名单 (全空字符串) → 空池 → 0 results"""
        result = run_scan(_config(tmp_path, symbols=["", "  "]))
        assert result["total_symbols"] == 0
        assert result["processed_count"] == 0
        assert result["status"] == RUN_STATUS_SUCCESS


class TestCommitEvery:
    """commit_every 参数行为"""

    @patch("chan_assist.scan_service._create_chan")
    def test_commit_every_does_not_lose_data(self, mock_create, tmp_path):
        mock_create.return_value = _chan_nohit()
        result = run_scan(_config(tmp_path, symbols=[f"s{i}" for i in range(7)], commit_every=3))
        assert result["processed_count"] == 7

        from chan_assist.db import get_connection
        conn = get_connection(str(tmp_path / "test.db"))
        count = conn.execute("SELECT COUNT(*) FROM scan_result WHERE run_id=?", (result["run_id"],)).fetchone()[0]
        assert count == 7
        conn.close()

    @patch("chan_assist.scan_service._create_chan")
    def test_commit_every_1(self, mock_create, tmp_path):
        mock_create.return_value = _chan_nohit()
        result = run_scan(_config(tmp_path, symbols=["a", "b", "c"], commit_every=1))
        assert result["processed_count"] == 3
