"""
target_bsp_types 筛选功能测试：正反用例。

正用例（positive）：目标类型命中 → hit
反用例（negative）：非目标类型不命中 → no_hit
"""
import pytest
from unittest.mock import MagicMock, patch
from strategy.chan_strategy import evaluate_signal
from chan_assist.config import ScanConfig


# --- Helpers ---

def _make_bsp(bi_idx, is_buy, types, date_str, close):
    bi = MagicMock()
    bi.idx = bi_idx
    bi._low.return_value = 10
    bi._high.return_value = 20
    bi.amp.return_value = 5
    bi.get_begin_klu.return_value = MagicMock(idx=bi_idx * 10)
    bi.get_end_klu.return_value = MagicMock(idx=bi_idx * 10 + 5)
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


def _make_chan(bsp_list):
    chan = MagicMock()
    chan.get_latest_bsp.return_value = bsp_list
    return chan


DATES = ["20260409"]
NO_FILTER = patch("strategy.chan_strategy._collect_flagged_indices", return_value=set())


# === 正用例：目标类型命中 ===

class TestPositive_TargetTypeHits:
    """目标类型买点存在且在日期范围内 → hit"""

    @NO_FILTER
    def test_b2_in_target_hits(self, _):
        """目标 ["2"]，BSP 类型 2 → hit"""
        bsp = _make_bsp(1, True, ["2"], "20260409", 10.0)
        result = evaluate_signal(_make_chan([bsp]), {
            "recent_dates": DATES,
            "target_bsp_types": ["2"],
        })
        assert result["hit"] is True
        assert "2" in result["signal_code"]

    @NO_FILTER
    def test_b3a_in_target_hits(self, _):
        """目标 ["3a"]，BSP 类型 3a → hit"""
        bsp = _make_bsp(1, True, ["3a"], "20260409", 10.0)
        result = evaluate_signal(_make_chan([bsp]), {
            "recent_dates": DATES,
            "target_bsp_types": ["3a"],
        })
        assert result["hit"] is True

    @NO_FILTER
    def test_multi_target_types_hit(self, _):
        """目标 ["2","2s","3a","3b"]，BSP 类型 2s → hit"""
        bsp = _make_bsp(1, True, ["2s"], "20260409", 10.0)
        result = evaluate_signal(_make_chan([bsp]), {
            "recent_dates": DATES,
            "target_bsp_types": ["2", "2s", "3a", "3b"],
        })
        assert result["hit"] is True

    @NO_FILTER
    def test_bsp_has_mixed_types_partial_match_hits(self, _):
        """BSP 同时标 1+2s，目标包含 2s → hit（交集非空）"""
        bsp = _make_bsp(1, True, ["1", "2s"], "20260409", 10.0)
        result = evaluate_signal(_make_chan([bsp]), {
            "recent_dates": DATES,
            "target_bsp_types": ["2s"],
        })
        assert result["hit"] is True

    @NO_FILTER
    def test_empty_target_means_all_types(self, _):
        """target_bsp_types 为空列表 → 全类型命中（默认行为）"""
        bsp = _make_bsp(1, True, ["1"], "20260409", 10.0)
        result = evaluate_signal(_make_chan([bsp]), {
            "recent_dates": DATES,
            "target_bsp_types": [],
        })
        assert result["hit"] is True

    @NO_FILTER
    def test_no_target_param_means_all_types(self, _):
        """不传 target_bsp_types → 全类型命中（向后兼容）"""
        bsp = _make_bsp(1, True, ["1"], "20260409", 10.0)
        result = evaluate_signal(_make_chan([bsp]), {
            "recent_dates": DATES,
        })
        assert result["hit"] is True


# === 反用例：非目标类型不命中 ===

class TestNegative_NonTargetTypeFiltered:
    """非目标类型买点 → no_hit"""

    @NO_FILTER
    def test_b1_not_in_target_nohit(self, _):
        """目标 ["2","3a"]，BSP 类型 1 → no_hit"""
        bsp = _make_bsp(1, True, ["1"], "20260409", 10.0)
        result = evaluate_signal(_make_chan([bsp]), {
            "recent_dates": DATES,
            "target_bsp_types": ["2", "3a"],
        })
        assert result["hit"] is False
        assert result["signals"] == []

    @NO_FILTER
    def test_b1p_not_in_target_nohit(self, _):
        """目标 ["2","2s"]，BSP 类型 1p → no_hit"""
        bsp = _make_bsp(1, True, ["1p"], "20260409", 10.0)
        result = evaluate_signal(_make_chan([bsp]), {
            "recent_dates": DATES,
            "target_bsp_types": ["2", "2s"],
        })
        assert result["hit"] is False

    @NO_FILTER
    def test_only_target_types_pass_others_skipped(self, _):
        """3 个 BSP：b1 + b2 + b3a，目标 ["3a"] → 只有 b3a 命中"""
        bsp_b1 = _make_bsp(1, True, ["1"], "20260409", 10.0)
        bsp_b2 = _make_bsp(3, True, ["2"], "20260409", 11.0)
        bsp_b3a = _make_bsp(5, True, ["3a"], "20260409", 12.0)
        result = evaluate_signal(_make_chan([bsp_b1, bsp_b2, bsp_b3a]), {
            "recent_dates": DATES,
            "target_bsp_types": ["3a"],
        })
        assert result["hit"] is True
        assert len(result["signals"]) == 1
        assert "3a" in result["signal_code"]

    @NO_FILTER
    def test_all_bsps_outside_target_nohit(self, _):
        """全部 BSP 都不在目标类型 → no_hit"""
        bsp1 = _make_bsp(1, True, ["1"], "20260409", 10.0)
        bsp2 = _make_bsp(3, True, ["1p"], "20260409", 11.0)
        result = evaluate_signal(_make_chan([bsp1, bsp2]), {
            "recent_dates": DATES,
            "target_bsp_types": ["3b"],
        })
        assert result["hit"] is False

    @NO_FILTER
    def test_target_filter_combined_with_flagged_filter(self, _mock):
        """target_types + flagged 双重过滤：b2 被 flagged，b3a 在目标内 → 只有 b3a 命中"""
        _mock.return_value = {3}  # b2 at bi_idx=3 被 flagged
        bsp_b2 = _make_bsp(3, True, ["2"], "20260409", 11.0)
        bsp_b3a = _make_bsp(5, True, ["3a"], "20260409", 12.0)
        result = evaluate_signal(_make_chan([bsp_b2, bsp_b3a]), {
            "recent_dates": DATES,
            "target_bsp_types": ["2", "3a"],
        })
        assert result["hit"] is True
        assert len(result["signals"]) == 1
        assert "3a" in result["signal_code"]


# === Config 层 ===

class TestConfigTargetBspTypes:
    """ScanConfig.target_bsp_types"""

    def test_default_empty(self):
        cfg = ScanConfig()
        assert cfg.target_bsp_types == []

    def test_set_target_types(self):
        cfg = ScanConfig(target_bsp_types=["2", "2s", "3a", "3b"])
        assert cfg.target_bsp_types == ["2", "2s", "3a", "3b"]


# === CLI 层 ===

class TestCliTargetTypes:
    """CLI --target-types 参数"""

    def test_parse_target_types(self):
        from scripts.run_scan import parse_args
        args = parse_args(["--target-types", "2", "2s", "3a"])
        assert args.target_types == ["2", "2s", "3a"]

    def test_no_target_types_is_none(self):
        from scripts.run_scan import parse_args
        args = parse_args([])
        assert args.target_types is None
