"""
Phase 5 集成测试：run_one_symbol → chan_strategy → ScanResult 跨模块协作。
"""
import pytest
from unittest.mock import patch, MagicMock
from chan_assist.scan_service import run_one_symbol
from chan_assist.config import ScanConfig
from chan_assist.models import ScanResult, RESULT_STATUS_HIT, RESULT_STATUS_NO_HIT, RESULT_STATUS_ERROR


def _config_with_dates(dates):
    """创建带显式 recent_dates 的 config，确保测试确定性"""
    cfg = ScanConfig(tushare_token="fake_token")
    cfg.strategy_params["recent_dates"] = dates
    return cfg


def _make_bsp(is_buy, types, date_str, close, bi_idx):
    bsp = MagicMock()
    bsp.is_buy = is_buy
    bsp.type = [MagicMock(value=t) for t in types]
    year, month, day = int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8])
    bsp.klu.time.year = year
    bsp.klu.time.month = month
    bsp.klu.time.day = day
    bsp.klu.close = close
    bsp.bi.idx = bi_idx
    return bsp


def _make_chan_with_bsps(bsp_list, kline_len=100):
    chan = MagicMock()
    kl_mock = MagicMock()
    kl_mock.__len__ = MagicMock(return_value=kline_len)
    kl_mock.bi_list = []
    kl_mock.seg_list = []
    kl_mock.zs_list = []
    chan.__getitem__ = MagicMock(return_value=kl_mock)
    chan.get_latest_bsp.return_value = bsp_list
    return chan


class TestRunOneSymbolIntegration:
    """
    集成测试：mock _create_chan，让 run_one_symbol 真正调用 evaluate_signal，
    验证完整链路 run_one_symbol → evaluate_signal → ScanResult。
    """

    @patch("chan_assist.scan_service._create_chan")
    def test_hit_end_to_end(self, mock_create):
        """完整链路：mock chan 有买点 + 日期匹配 → 严格断言 hit"""
        bsp = _make_bsp(is_buy=True, types=["1"], date_str="20260409", close=10.5, bi_idx=42)
        mock_create.return_value = _make_chan_with_bsps([bsp])

        config = _config_with_dates(["20260409"])
        result = run_one_symbol("000001", "平安银行", config)

        assert isinstance(result, ScanResult)
        assert result.status == RESULT_STATUS_HIT, \
            f"命中链路应返回 hit，实际返回 {result.status}"
        assert result.symbol == "000001"
        assert result.name == "平安银行"
        assert result.signal_code is not None
        assert len(result.signals) >= 1

    @patch("chan_assist.scan_service._create_chan")
    def test_hit_with_multiple_signals(self, mock_create):
        """完整链路：多个 b1 买点命中 → hit + 多 signals"""
        bsp1 = _make_bsp(is_buy=True, types=["1"], date_str="20260409", close=10.0, bi_idx=1)
        bsp2 = _make_bsp(is_buy=True, types=["1"], date_str="20260408", close=11.0, bi_idx=3)
        mock_create.return_value = _make_chan_with_bsps([bsp1, bsp2])

        config = _config_with_dates(["20260409", "20260408"])
        result = run_one_symbol("000001", "test", config)

        assert result.status == RESULT_STATUS_HIT
        assert len(result.signals) == 2

    @patch("chan_assist.scan_service._create_chan")
    def test_no_hit_end_to_end(self, mock_create):
        """完整链路：mock chan 无买点 → no_hit"""
        mock_create.return_value = _make_chan_with_bsps([])
        result = run_one_symbol("000002", "万科A", _config_with_dates(["20260409"]))
        assert isinstance(result, ScanResult)
        assert result.status == RESULT_STATUS_NO_HIT
        assert result.signal_code is None
        assert result.signals == []

    @patch("chan_assist.scan_service._create_chan")
    def test_no_hit_buy_point_outside_date(self, mock_create):
        """完整链路：有买点但不在目标日期 → no_hit"""
        bsp = _make_bsp(is_buy=True, types=["1"], date_str="20260101", close=10.0, bi_idx=1)
        mock_create.return_value = _make_chan_with_bsps([bsp])
        result = run_one_symbol("000002", "test", _config_with_dates(["20260409"]))
        assert result.status == RESULT_STATUS_NO_HIT

    @patch("chan_assist.scan_service._create_chan")
    def test_error_end_to_end(self, mock_create):
        """完整链路：创建 chan 异常 → error"""
        mock_create.side_effect = ConnectionError("网络超时")
        result = run_one_symbol("000003", "测试股", _config_with_dates(["20260409"]))
        assert isinstance(result, ScanResult)
        assert result.status == RESULT_STATUS_ERROR
        assert "网络超时" in result.error_msg

    @patch("chan_assist.scan_service._create_chan")
    def test_empty_kline_end_to_end(self, mock_create):
        """完整链路：chan 无K线 → error"""
        mock_create.return_value = _make_chan_with_bsps([], kline_len=0)
        result = run_one_symbol("000004", "空数据", _config_with_dates(["20260409"]))
        assert result.status == RESULT_STATUS_ERROR
        assert "无K线数据" in result.error_msg

    @patch("chan_assist.scan_service._create_chan")
    def test_result_consumable_by_persistence(self, mock_create):
        """结果可被 persistence 消费（字段完整性）"""
        mock_create.return_value = _make_chan_with_bsps([])
        result = run_one_symbol("000001", "test", _config_with_dates(["20260409"]))
        for field in ("symbol", "name", "status", "signal_code", "signal_desc",
                      "score", "error_msg", "signals", "scan_time"):
            assert hasattr(result, field), f"result missing field: {field}"

    @patch("chan_assist.scan_service._create_chan")
    def test_three_states_exhaustive(self, mock_create):
        """三态穷举：hit + no_hit + error 全部覆盖"""
        config = _config_with_dates(["20260409"])

        # hit
        bsp = _make_bsp(is_buy=True, types=["1"], date_str="20260409", close=10.0, bi_idx=1)
        mock_create.return_value = _make_chan_with_bsps([bsp])
        r_hit = run_one_symbol("s1", "n1", config)

        # no_hit
        mock_create.return_value = _make_chan_with_bsps([])
        mock_create.side_effect = None
        r_nohit = run_one_symbol("s2", "n2", config)

        # error
        mock_create.side_effect = Exception("boom")
        r_error = run_one_symbol("s3", "n3", config)

        assert r_hit.status == RESULT_STATUS_HIT
        assert r_nohit.status == RESULT_STATUS_NO_HIT
        assert r_error.status == RESULT_STATUS_ERROR
