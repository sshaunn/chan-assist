"""
回归测试：锁定 Phase M2 的关键风险。

锁定的风险点：
- chan_strategy.py 变厚偷偷恢复规则框架
- _bsp_modify.py 被默认接入主路径
- 过滤逻辑误删所有候选（空 flagged 时不应过滤任何 BSP）
- 某条规则未被执行
- 返回结构字段漂移
- 异常被静默吞成 no_hit（Codex M2 re-review 修复项）
"""
import inspect
import pytest
from unittest.mock import MagicMock, patch
from strategy.chan_strategy import evaluate_signal, _collect_flagged_indices


class TestNoBspModifyInDefaultPath:
    """_bsp_modify.py 不在 M2 默认路径"""

    def test_no_bsp_modify_import(self):
        source = inspect.getsource(
            __import__("strategy.chan_strategy", fromlist=["chan_strategy"])
        )
        assert "_bsp_modify" not in source

    def test_no_remove_bsp_from_chan(self):
        source = inspect.getsource(
            __import__("strategy.chan_strategy", fromlist=["chan_strategy"])
        )
        assert "remove_bsp_from_chan" not in source


class TestNoFrameworkRestoredInChanStrategy:
    """chan_strategy.py 不得恢复规则框架"""

    def test_no_registry(self):
        source = inspect.getsource(
            __import__("strategy.chan_strategy", fromlist=["chan_strategy"])
        )
        assert "registry" not in source.lower()
        assert "_rule_registry" not in source

    def test_no_rule_decorator(self):
        source = inspect.getsource(
            __import__("strategy.chan_strategy", fromlist=["chan_strategy"])
        )
        assert "@rule" not in source

    def test_no_executor(self):
        source = inspect.getsource(
            __import__("strategy.chan_strategy", fromlist=["chan_strategy"])
        )
        assert "executor" not in source.lower()
        assert "run_filter_rules" not in source


class TestEmptyFlaggedNeverKillsAllCandidates:
    """空 flagged 不应误删任何候选"""

    @patch("strategy.chan_strategy._collect_flagged_indices", return_value=set())
    def test_empty_flagged_preserves_all_hits(self, _):
        bi = MagicMock()
        bi.idx = 1
        bsp = MagicMock()
        bsp.bi = bi
        bsp.is_buy = True
        bsp.type = [MagicMock(value="1")]
        bsp.klu.time.year = 2026
        bsp.klu.time.month = 4
        bsp.klu.time.day = 9
        bsp.klu.close = 10.0

        chan = MagicMock()
        chan.get_latest_bsp.return_value = [bsp]

        result = evaluate_signal(chan, {"recent_dates": ["20260409"]})
        assert result["hit"] is True, "空 flagged 时不应过滤任何候选"
        assert len(result["signals"]) == 1


class TestAllRulesExecuted:
    """三条规则都必须被执行"""

    @patch("strategy._bsp_filters.b2_must_enter_zs", return_value=[])
    @patch("strategy._bsp_filters.b2_in_new_zs", return_value=[])
    @patch("strategy._bsp_filters.b2_retrace_check", return_value=[])
    @patch("strategy._zs_patch.detect_missing_zs", return_value=[])
    def test_all_four_called(self, mock_zs, mock_retrace, mock_new_zs, mock_enter):
        chan = MagicMock()
        chan.__getitem__ = MagicMock(return_value=MagicMock(
            bi_list=[], seg_list=[], zs_list=[],
        ))
        chan.get_latest_bsp.return_value = []
        _collect_flagged_indices(chan)
        assert mock_zs.called, "detect_missing_zs 未被调用"
        assert mock_retrace.called, "b2_retrace_check 未被调用"
        assert mock_new_zs.called, "b2_in_new_zs 未被调用"
        assert mock_enter.called, "b2_must_enter_zs 未被调用"


class TestFixedCallOrderLocked:
    """固定调用顺序不能被改乱（Codex M2 review 修复项）"""

    def test_order_is_zs_then_retrace_then_new_zs_then_enter(self):
        """回归锁定：detect_missing_zs → b2_retrace_check → b2_in_new_zs → b2_must_enter_zs"""
        call_order = []

        def tracker(name):
            def fn(chan):
                call_order.append(name)
                return []
            return fn

        with patch("strategy._zs_patch.detect_missing_zs", side_effect=tracker("detect_missing_zs")), \
             patch("strategy._bsp_filters.b2_retrace_check", side_effect=tracker("b2_retrace_check")), \
             patch("strategy._bsp_filters.b2_in_new_zs", side_effect=tracker("b2_in_new_zs")), \
             patch("strategy._bsp_filters.b2_must_enter_zs", side_effect=tracker("b2_must_enter_zs")):
            chan = MagicMock()
            chan.__getitem__ = MagicMock(return_value=MagicMock(
                bi_list=[], seg_list=[], zs_list=[],
            ))
            chan.get_latest_bsp.return_value = []
            _collect_flagged_indices(chan)

        expected = ["detect_missing_zs", "b2_retrace_check", "b2_in_new_zs", "b2_must_enter_zs"]
        assert call_order == expected, \
            f"固定调用顺序被改乱: 期望 {expected}，实际 {call_order}"


class TestExceptionNeverSwallowedToNoHit:
    """异常不能被静默吞成 no_hit（Codex M2 re-review 修复项）"""

    @patch("strategy.chan_strategy._collect_flagged_indices", side_effect=RuntimeError("filter crash"))
    def test_runtime_error_propagates_not_swallowed(self, _):
        """RuntimeError 必须向上传播，不能返回 {hit: False}"""
        chan = MagicMock()
        chan.get_latest_bsp.return_value = []
        with pytest.raises(RuntimeError, match="filter crash"):
            evaluate_signal(chan, {"recent_dates": ["20260409"]})

    @patch("strategy.chan_strategy._collect_flagged_indices", side_effect=Exception("generic error"))
    def test_generic_exception_propagates(self, _):
        """任意 Exception 也不能被吞掉"""
        chan = MagicMock()
        chan.get_latest_bsp.return_value = []
        with pytest.raises(Exception, match="generic error"):
            evaluate_signal(chan, {"recent_dates": ["20260409"]})

    def test_no_try_except_in_evaluate_signal(self):
        """evaluate_signal 中不应有 try/except（异常由上层 run_one_symbol 收口）"""
        import inspect
        source = inspect.getsource(evaluate_signal)
        assert "try:" not in source, "evaluate_signal 不应包含 try/except"
        assert "except" not in source, "evaluate_signal 不应包含 try/except"


class TestReturnStructureStable:
    """返回结构不得漂移"""

    REQUIRED_KEYS = {"hit", "signal_code", "signal_desc", "score", "signals"}

    @patch("strategy.chan_strategy._collect_flagged_indices", return_value=set())
    def test_hit_structure(self, _):
        bi = MagicMock()
        bi.idx = 1
        bsp = MagicMock()
        bsp.bi = bi
        bsp.is_buy = True
        bsp.type = [MagicMock(value="1")]
        bsp.klu.time.year, bsp.klu.time.month, bsp.klu.time.day = 2026, 4, 9
        bsp.klu.close = 10.0
        chan = MagicMock()
        chan.get_latest_bsp.return_value = [bsp]
        result = evaluate_signal(chan, {"recent_dates": ["20260409"]})
        assert set(result.keys()) == self.REQUIRED_KEYS

    @patch("strategy.chan_strategy._collect_flagged_indices", return_value=set())
    def test_no_hit_structure(self, _):
        chan = MagicMock()
        chan.get_latest_bsp.return_value = []
        result = evaluate_signal(chan, {"recent_dates": ["20260409"]})
        assert set(result.keys()) == self.REQUIRED_KEYS
