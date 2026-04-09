"""
Phase M2 集成测试：evaluate_signal 完整过滤链 — zs_patch + bsp_filters + 非侵入式过滤 + hit/no_hit。
"""
import pytest
from unittest.mock import MagicMock
from strategy.chan_strategy import evaluate_signal


# --- Helpers ---

def _make_bi(idx, low, high, amp_val):
    bi = MagicMock()
    bi.idx = idx
    bi._low.return_value = low
    bi._high.return_value = high
    bi.amp.return_value = amp_val
    bi.get_begin_klu.return_value = MagicMock(idx=idx * 10)
    bi.get_end_klu.return_value = MagicMock(idx=idx * 10 + 5)
    return bi


def _make_bsp(bi, is_buy, types, date_str, close, relate_bsp1=None):
    bsp = MagicMock()
    bsp.bi = bi
    bsp.is_buy = is_buy
    bsp.type = [MagicMock(value=t) for t in types]
    y, m, d = int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8])
    bsp.klu.time.year = y
    bsp.klu.time.month = m
    bsp.klu.time.day = d
    bsp.klu.close = close
    bsp.relate_bsp1 = relate_bsp1
    return bsp


class TestFilterChainIntegration:
    """
    完整过滤链集成测试：不 mock _collect_flagged_indices，
    让 evaluate_signal 真正调用 _zs_patch + _bsp_filters。
    """

    def test_high_retrace_b2_filtered_to_no_hit(self):
        """
        场景：一个 b2 买点，但回踩比 80% 超过阈值 60%。
        预期：被 b2_retrace_check 过滤，最终 no_hit。
        """
        bi0 = _make_bi(idx=0, low=10, high=20, amp_val=10)  # 反弹笔
        bi1 = _make_bi(idx=1, low=12, high=20, amp_val=8)   # b2 回踩笔，retrace=80%

        bsp = _make_bsp(bi1, is_buy=True, types=["2"], date_str="20260409", close=12.0)

        chan = MagicMock()
        chan.__getitem__ = MagicMock(return_value=MagicMock(
            bi_list=[bi0, bi1], seg_list=[], zs_list=[],
        ))
        chan.get_latest_bsp.return_value = [bsp]

        result = evaluate_signal(chan, {"recent_dates": ["20260409"]})
        assert result["hit"] is False, "回踩比过高的 b2 应被过滤为 no_hit"

    def test_valid_b1_not_filtered_still_hits(self):
        """
        场景：一个 b1 买点（非 b2），不受 b2 过滤规则影响。
        预期：正常命中。
        """
        bi0 = _make_bi(idx=0, low=10, high=20, amp_val=10)

        bsp = _make_bsp(bi0, is_buy=True, types=["1"], date_str="20260409", close=10.0)

        chan = MagicMock()
        chan.__getitem__ = MagicMock(return_value=MagicMock(
            bi_list=[bi0], seg_list=[], zs_list=[],
        ))
        chan.get_latest_bsp.return_value = [bsp]

        result = evaluate_signal(chan, {"recent_dates": ["20260409"]})
        assert result["hit"] is True, "合法 b1 不应被过滤"
        assert "1" in result["signal_code"]

    def test_mixed_flagged_and_valid_only_valid_hits(self):
        """
        场景：两个买点 — 一个 b2（回踩比过高被过滤），一个 b1（合法）。
        预期：只有 b1 命中。
        """
        bi0 = _make_bi(idx=0, low=10, high=20, amp_val=10)
        bi1 = _make_bi(idx=1, low=12, high=20, amp_val=8)   # retrace 80%
        bi2 = _make_bi(idx=2, low=8, high=15, amp_val=7)

        bsp_bad_b2 = _make_bsp(bi1, is_buy=True, types=["2"], date_str="20260409", close=12.0)
        bsp_good_b1 = _make_bsp(bi2, is_buy=True, types=["1"], date_str="20260409", close=8.0)

        chan = MagicMock()
        chan.__getitem__ = MagicMock(return_value=MagicMock(
            bi_list=[bi0, bi1, bi2], seg_list=[], zs_list=[],
        ))
        chan.get_latest_bsp.return_value = [bsp_bad_b2, bsp_good_b1]

        result = evaluate_signal(chan, {"recent_dates": ["20260409"]})
        assert result["hit"] is True
        assert len(result["signals"]) == 1
        assert "1" in result["signal_code"]

    def test_no_flagged_all_valid_bsps_hit(self):
        """
        场景：一个 b1 买点，无 b2 规则触发，所有候选保留。
        预期：正常命中。
        """
        bi0 = _make_bi(idx=0, low=5, high=15, amp_val=10)

        bsp = _make_bsp(bi0, is_buy=True, types=["1"], date_str="20260409", close=5.0)

        chan = MagicMock()
        chan.__getitem__ = MagicMock(return_value=MagicMock(
            bi_list=[bi0], seg_list=[], zs_list=[],
        ))
        chan.get_latest_bsp.return_value = [bsp]

        result = evaluate_signal(chan, {"recent_dates": ["20260409"]})
        assert result["hit"] is True

    def test_empty_bsp_list_no_hit(self):
        """无 BSP 时 no_hit"""
        chan = MagicMock()
        chan.__getitem__ = MagicMock(return_value=MagicMock(
            bi_list=[], seg_list=[], zs_list=[],
        ))
        chan.get_latest_bsp.return_value = []

        result = evaluate_signal(chan, {"recent_dates": ["20260409"]})
        assert result["hit"] is False
