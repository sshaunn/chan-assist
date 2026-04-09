"""
Phase M2 单元测试：chan_strategy.py 接入 _zs_patch + _bsp_filters 后的行为。
"""
import pytest
from unittest.mock import MagicMock, patch, call
from strategy.chan_strategy import evaluate_signal, _collect_flagged_indices


# --- Helpers ---

def _make_bi(idx, low=10, high=20, amp_val=5):
    bi = MagicMock()
    bi.idx = idx
    bi._low.return_value = low
    bi._high.return_value = high
    bi.amp.return_value = amp_val
    bi.get_begin_klu.return_value = MagicMock(idx=idx * 10)
    bi.get_end_klu.return_value = MagicMock(idx=idx * 10 + 5)
    return bi


def _make_bsp(bi_idx, is_buy, types, date_str, close):
    bi = _make_bi(bi_idx)
    bsp = MagicMock()
    bsp.bi = bi
    bsp.is_buy = is_buy
    bsp.type = [MagicMock(value=t) for t in types]
    y, m, d = int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8])
    bsp.klu.time.year = y
    bsp.klu.time.month = m
    bsp.klu.time.day = d
    bsp.klu.close = close
    bsp.relate_bsp1 = None
    return bsp


def _make_chan(bsp_list, bi_list=None):
    chan = MagicMock()
    chan.__getitem__ = MagicMock(return_value=MagicMock(
        bi_list=bi_list or [], seg_list=[], zs_list=[],
    ))
    chan.get_latest_bsp.return_value = bsp_list
    return chan


# --- Tests ---

class TestCollectFlaggedIndices:
    """_collect_flagged_indices 固定调用顺序 + 汇总"""

    def test_calls_all_four_in_correct_order(self):
        """验证固定调用顺序：detect_missing_zs → b2_retrace → b2_in_new_zs → b2_must_enter"""
        call_order = []

        def make_tracker(name, ret=None):
            def tracked(chan):
                call_order.append(name)
                return ret if ret is not None else []
            return tracked

        with patch("strategy._zs_patch.detect_missing_zs", side_effect=make_tracker("detect_missing_zs")), \
             patch("strategy._bsp_filters.b2_retrace_check", side_effect=make_tracker("b2_retrace_check")), \
             patch("strategy._bsp_filters.b2_in_new_zs", side_effect=make_tracker("b2_in_new_zs")), \
             patch("strategy._bsp_filters.b2_must_enter_zs", side_effect=make_tracker("b2_must_enter_zs")):
            chan = _make_chan([])
            _collect_flagged_indices(chan)

        assert call_order == [
            "detect_missing_zs",
            "b2_retrace_check",
            "b2_in_new_zs",
            "b2_must_enter_zs",
        ], f"调用顺序不正确: {call_order}"

    @patch("strategy._bsp_filters.b2_must_enter_zs")
    @patch("strategy._bsp_filters.b2_in_new_zs")
    @patch("strategy._bsp_filters.b2_retrace_check")
    @patch("strategy._zs_patch.detect_missing_zs", return_value=[])
    def test_merges_flagged_from_multiple_rules(self, mock_zs, mock_retrace, mock_new_zs, mock_enter):
        mock_retrace.return_value = [{"bi_idx": 10, "rule_name": "r", "reason": "r", "extra": None}]
        mock_new_zs.return_value = [{"bi_idx": 20, "rule_name": "n", "reason": "n", "extra": None}]
        mock_enter.return_value = [{"bi_idx": 10, "rule_name": "e", "reason": "e", "extra": None}]
        chan = _make_chan([])
        result = _collect_flagged_indices(chan)
        assert result == {10, 20}

    @patch("strategy._bsp_filters.b2_must_enter_zs", return_value=[])
    @patch("strategy._bsp_filters.b2_in_new_zs", return_value=[])
    @patch("strategy._bsp_filters.b2_retrace_check", return_value=[])
    @patch("strategy._zs_patch.detect_missing_zs", return_value=[])
    def test_empty_flagged_returns_empty_set(self, *_):
        chan = _make_chan([])
        result = _collect_flagged_indices(chan)
        assert result == set()


class TestEvaluateSignalWithFiltering:
    """evaluate_signal 接入过滤后的行为"""

    @patch("strategy.chan_strategy._collect_flagged_indices", return_value=set())
    def test_no_flagged_preserves_hit(self, _):
        bsp = _make_bsp(bi_idx=1, is_buy=True, types=["1"], date_str="20260409", close=10.5)
        chan = _make_chan([bsp])
        result = evaluate_signal(chan, {"recent_dates": ["20260409"]})
        assert result["hit"] is True
        assert len(result["signals"]) == 1

    @patch("strategy.chan_strategy._collect_flagged_indices", return_value={1})
    def test_flagged_bsp_skipped(self, _):
        """被 flagged 的 BSP 不参与 hit 判断"""
        bsp = _make_bsp(bi_idx=1, is_buy=True, types=["2"], date_str="20260409", close=10.0)
        chan = _make_chan([bsp])
        result = evaluate_signal(chan, {"recent_dates": ["20260409"]})
        assert result["hit"] is False
        assert result["signals"] == []

    @patch("strategy.chan_strategy._collect_flagged_indices", return_value={1})
    def test_only_flagged_skipped_others_remain(self, _):
        """只有 flagged 的被跳过，其他正常"""
        bsp_flagged = _make_bsp(bi_idx=1, is_buy=True, types=["2"], date_str="20260409", close=10.0)
        bsp_good = _make_bsp(bi_idx=5, is_buy=True, types=["1"], date_str="20260409", close=11.0)
        chan = _make_chan([bsp_flagged, bsp_good])
        result = evaluate_signal(chan, {"recent_dates": ["20260409"]})
        assert result["hit"] is True
        assert len(result["signals"]) == 1
        assert "1" in result["signal_code"]

    @patch("strategy.chan_strategy._collect_flagged_indices", return_value=set())
    def test_no_buy_point_still_no_hit(self, _):
        """无买点时仍 no_hit"""
        bsp_sell = _make_bsp(bi_idx=1, is_buy=False, types=["1"], date_str="20260409", close=10.0)
        chan = _make_chan([bsp_sell])
        result = evaluate_signal(chan, {"recent_dates": ["20260409"]})
        assert result["hit"] is False

    @patch("strategy.chan_strategy._collect_flagged_indices", return_value=set())
    def test_return_structure_unchanged(self, _):
        """返回结构不变"""
        chan = _make_chan([])
        result = evaluate_signal(chan, {"recent_dates": ["20260409"]})
        assert "hit" in result
        assert "signal_code" in result
        assert "signal_desc" in result
        assert "score" in result
        assert "signals" in result

    @patch("strategy.chan_strategy._collect_flagged_indices", return_value=set())
    def test_params_default_still_works(self, _):
        """params=None 仍可工作"""
        chan = _make_chan([])
        result = evaluate_signal(chan)
        assert result["hit"] is False


class TestExceptionPropagation:
    """异常不得被 evaluate_signal 静默吞成 no_hit（Codex M2 re-review 修复项）"""

    @patch("strategy.chan_strategy._collect_flagged_indices", side_effect=RuntimeError("过滤链内部错误"))
    def test_filter_chain_exception_propagates(self, _):
        """_collect_flagged_indices 抛异常时，evaluate_signal 必须向上传播，不得返回 no_hit"""
        chan = _make_chan([])
        with pytest.raises(RuntimeError, match="过滤链内部错误"):
            evaluate_signal(chan, {"recent_dates": ["20260409"]})

    @patch("strategy.chan_strategy._collect_flagged_indices", side_effect=ValueError("bad data"))
    def test_value_error_propagates(self, _):
        """ValueError 也不能被吞掉"""
        chan = _make_chan([])
        with pytest.raises(ValueError, match="bad data"):
            evaluate_signal(chan, {"recent_dates": ["20260409"]})


class TestBspModifyNotEnabled:
    """_bsp_modify.py 不在默认路径"""

    def test_bsp_modify_not_imported_in_chan_strategy(self):
        import inspect
        source = inspect.getsource(__import__("strategy.chan_strategy", fromlist=["chan_strategy"]))
        assert "_bsp_modify" not in source, \
            "chan_strategy.py 不应在 M2 默认路径中导入 _bsp_modify"
