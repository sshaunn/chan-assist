"""
Phase 5 单元测试：strategy/chan_strategy.py — 策略判定入口。

注意：M2 后 evaluate_signal 内部会调用过滤链。
本文件测试的是日期匹配/hit判断逻辑，过滤链通过 mock _collect_flagged_indices 隔离。
"""
import pytest
from unittest.mock import MagicMock, patch
from strategy.chan_strategy import evaluate_signal, _get_recent_trade_dates


@pytest.fixture(autouse=True)
def _mock_filter_chain():
    """本文件所有测试 mock 掉过滤链，只测日期匹配逻辑"""
    with patch("strategy.chan_strategy._collect_flagged_indices", return_value=set()):
        yield


# --- Helpers to build fake chan.py objects ---

def _make_bsp(is_buy, types, date_str, close, bi_idx):
    """构造一个 fake BSP 对象"""
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


def _make_chan(bsp_list):
    """构造一个 fake CChan 对象"""
    chan = MagicMock()
    chan.get_latest_bsp.return_value = bsp_list
    return chan


# --- Tests ---

class TestEvaluateSignalHit:
    """evaluate_signal 命中场景"""

    def test_hit_single_buy_point(self):
        bsp = _make_bsp(is_buy=True, types=["1"], date_str="20260409", close=10.5, bi_idx=42)
        chan = _make_chan([bsp])
        result = evaluate_signal(chan, {"recent_dates": ["20260409"]})
        assert result["hit"] is True
        assert result["signal_code"] == "1"
        assert "20260409" in result["signal_desc"]
        assert len(result["signals"]) == 1
        assert result["signals"][0]["signal_type"] == "1"
        assert result["signals"][0]["signal_value"] == "10.5"

    def test_hit_multiple_types(self):
        bsp = _make_bsp(is_buy=True, types=["1", "2s"], date_str="20260409", close=12.0, bi_idx=5)
        chan = _make_chan([bsp])
        result = evaluate_signal(chan, {"recent_dates": ["20260409"]})
        assert result["hit"] is True
        assert "1,2s" in result["signal_code"]

    def test_hit_multiple_bsps(self):
        bsp1 = _make_bsp(is_buy=True, types=["1"], date_str="20260409", close=10.0, bi_idx=1)
        bsp2 = _make_bsp(is_buy=True, types=["2"], date_str="20260408", close=11.0, bi_idx=3)
        chan = _make_chan([bsp1, bsp2])
        result = evaluate_signal(chan, {"recent_dates": ["20260409", "20260408"]})
        assert result["hit"] is True
        assert len(result["signals"]) == 2


class TestEvaluateSignalNoHit:
    """evaluate_signal 未命中场景"""

    def test_no_buy_points(self):
        bsp = _make_bsp(is_buy=False, types=["1"], date_str="20260409", close=10.0, bi_idx=1)
        chan = _make_chan([bsp])
        result = evaluate_signal(chan, {"recent_dates": ["20260409"]})
        assert result["hit"] is False
        assert result["signal_code"] is None
        assert result["signals"] == []

    def test_buy_point_outside_date_range(self):
        bsp = _make_bsp(is_buy=True, types=["1"], date_str="20260101", close=10.0, bi_idx=1)
        chan = _make_chan([bsp])
        result = evaluate_signal(chan, {"recent_dates": ["20260409"]})
        assert result["hit"] is False

    def test_empty_bsp_list(self):
        chan = _make_chan([])
        result = evaluate_signal(chan, {"recent_dates": ["20260409"]})
        assert result["hit"] is False
        assert result["signals"] == []


class TestEvaluateSignalReturnStructure:
    """返回结构完整性"""

    def test_hit_has_all_fields(self):
        bsp = _make_bsp(is_buy=True, types=["1"], date_str="20260409", close=10.0, bi_idx=1)
        chan = _make_chan([bsp])
        result = evaluate_signal(chan, {"recent_dates": ["20260409"]})
        assert "hit" in result
        assert "signal_code" in result
        assert "signal_desc" in result
        assert "score" in result
        assert "signals" in result

    def test_no_hit_has_all_fields(self):
        chan = _make_chan([])
        result = evaluate_signal(chan, {"recent_dates": ["20260409"]})
        assert "hit" in result
        assert "signal_code" in result
        assert "signal_desc" in result
        assert "score" in result
        assert "signals" in result

    def test_signal_detail_structure(self):
        bsp = _make_bsp(is_buy=True, types=["1"], date_str="20260409", close=10.0, bi_idx=1)
        chan = _make_chan([bsp])
        result = evaluate_signal(chan, {"recent_dates": ["20260409"]})
        sig = result["signals"][0]
        assert "signal_type" in sig
        assert "signal_level" in sig
        assert "signal_value" in sig
        assert "extra_json" in sig

    def test_default_params(self):
        """params=None 应使用默认值"""
        chan = _make_chan([])
        result = evaluate_signal(chan)
        assert result["hit"] is False


class TestGetRecentTradeDates:
    """日期生成辅助"""

    def test_returns_requested_count(self):
        dates = _get_recent_trade_dates(3)
        assert len(dates) == 3

    def test_returns_yyyymmdd_format(self):
        dates = _get_recent_trade_dates(1)
        assert len(dates[0]) == 8
        assert dates[0].isdigit()
