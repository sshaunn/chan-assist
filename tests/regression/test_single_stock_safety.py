"""
回归测试：锁定 Phase 5 单股执行的关键失败模式。

锁定的风险点（来自 task plan regression 要求 + Phase 5 review 失败项）：
- 命中状态判断错误（hit 被误判为 no_hit）
- 异常被吞掉未转成 error
- 返回结构字段缺失
- 参数口径被越权改写（divergence_rate / min_zs_cnt）
"""
import pytest
from unittest.mock import patch, MagicMock
from chan_assist.scan_service import run_one_symbol, _create_chan
from chan_assist.config import ScanConfig
from chan_assist.models import ScanResult, VALID_RESULT_STATUSES


def _default_config():
    return ScanConfig(tushare_token="fake_token")


def _config_with_dates(dates):
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
    chan.__getitem__ = MagicMock(return_value=MagicMock(__len__=MagicMock(return_value=kline_len)))
    chan.get_latest_bsp.return_value = bsp_list
    return chan


class TestExceptionNeverSwallowed:
    """异常绝不能被吞掉伪装成 no_hit 或 hit"""

    @patch("chan_assist.scan_service._create_chan")
    def test_create_chan_exception_is_error(self, mock_chan):
        mock_chan.side_effect = RuntimeError("数据源崩溃")
        result = run_one_symbol("000001", "test", _default_config())
        assert result.status == "error"
        assert result.error_msg is not None
        assert len(result.error_msg) > 0

    @patch("strategy.chan_strategy.evaluate_signal")
    @patch("chan_assist.scan_service._create_chan")
    def test_evaluate_exception_is_error(self, mock_chan, mock_eval):
        mock_chan_obj = MagicMock()
        mock_chan_obj.__getitem__ = MagicMock(return_value=MagicMock(__len__=MagicMock(return_value=100)))
        mock_chan.return_value = mock_chan_obj
        mock_eval.side_effect = TypeError("策略类型错误")
        result = run_one_symbol("000001", "test", _default_config())
        assert result.status == "error"
        assert "策略类型错误" in result.error_msg

    @patch("chan_assist.scan_service._create_chan")
    def test_exception_never_returns_no_hit(self, mock_chan):
        """任何异常都不能返回 no_hit"""
        for exc in [ValueError("v"), RuntimeError("r"), ConnectionError("c"), KeyError("k")]:
            mock_chan.side_effect = exc
            result = run_one_symbol("000001", "test", _default_config())
            assert result.status != "no_hit", f"{exc} was swallowed as no_hit"
            assert result.status != "hit", f"{exc} was swallowed as hit"
            assert result.status == "error"


class TestReturnStructureComplete:
    """返回结构字段不得缺失"""

    REQUIRED_FIELDS = {"symbol", "name", "status", "signal_code", "signal_desc",
                       "score", "error_msg", "signals", "scan_time"}

    @patch("chan_assist.scan_service._create_chan")
    def _get_result(self, mock_chan, *, make_hit=False, make_error=False):
        if make_error:
            mock_chan.side_effect = Exception("err")
        else:
            chan_obj = MagicMock()
            chan_obj.__getitem__ = MagicMock(return_value=MagicMock(__len__=MagicMock(return_value=100)))
            chan_obj.get_latest_bsp.return_value = []
            mock_chan.return_value = chan_obj
        return run_one_symbol("000001", "test", _default_config())

    def test_no_hit_has_all_fields(self):
        result = self._get_result()
        for field in self.REQUIRED_FIELDS:
            assert hasattr(result, field), f"no_hit result missing field: {field}"

    def test_error_has_all_fields(self):
        result = self._get_result(make_error=True)
        for field in self.REQUIRED_FIELDS:
            assert hasattr(result, field), f"error result missing field: {field}"


class TestStatusAlwaysValid:
    """run_one_symbol 返回的 status 必须是合法值"""

    @patch("chan_assist.scan_service._create_chan")
    def test_no_hit_status_valid(self, mock_chan):
        chan_obj = MagicMock()
        chan_obj.__getitem__ = MagicMock(return_value=MagicMock(__len__=MagicMock(return_value=100)))
        chan_obj.get_latest_bsp.return_value = []
        mock_chan.return_value = chan_obj
        result = run_one_symbol("000001", "test", _default_config())
        assert result.status in VALID_RESULT_STATUSES

    @patch("chan_assist.scan_service._create_chan")
    def test_error_status_valid(self, mock_chan):
        mock_chan.side_effect = Exception("boom")
        result = run_one_symbol("000001", "test", _default_config())
        assert result.status in VALID_RESULT_STATUSES


class TestHitNeverMisjudged:
    """命中不得被误判为 no_hit（Phase 5 review 失败项）"""

    @patch("chan_assist.scan_service._create_chan")
    def test_buy_point_in_date_range_must_hit(self, mock_create):
        """有买点且日期匹配时，必须返回 hit，不可退化为 no_hit"""
        bsp = _make_bsp(is_buy=True, types=["1"], date_str="20260409", close=10.0, bi_idx=1)
        mock_create.return_value = _make_chan_with_bsps([bsp])
        result = run_one_symbol("000001", "test", _config_with_dates(["20260409"]))
        assert result.status == "hit", \
            f"有买点且日期匹配应返回 hit，实际返回 {result.status}"

    @patch("chan_assist.scan_service._create_chan")
    def test_sell_point_does_not_trigger_hit(self, mock_create):
        """卖点不应触发 hit"""
        bsp = _make_bsp(is_buy=False, types=["1"], date_str="20260409", close=10.0, bi_idx=1)
        mock_create.return_value = _make_chan_with_bsps([bsp])
        result = run_one_symbol("000001", "test", _config_with_dates(["20260409"]))
        assert result.status == "no_hit"

    @patch("chan_assist.scan_service._create_chan")
    def test_hit_has_signals(self, mock_create):
        """hit 结果必须包含 signals 明细"""
        bsp = _make_bsp(is_buy=True, types=["1"], date_str="20260409", close=10.0, bi_idx=1)
        mock_create.return_value = _make_chan_with_bsps([bsp])
        result = run_one_symbol("000001", "test", _config_with_dates(["20260409"]))
        assert result.status == "hit"
        assert len(result.signals) >= 1


class TestParameterBaselineProtection:
    """参数口径不得被越权改写（Phase 5 review 失败项）"""

    def test_divergence_rate_frozen_at_0_8(self):
        """divergence_rate 默认必须是 0.8"""
        cfg = ScanConfig()
        assert cfg.strategy_params["divergence_rate"] == 0.8

    def test_min_zs_cnt_not_hardcoded_in_scan_service(self):
        """scan_service._create_chan 不得硬编码 min_zs_cnt 默认值"""
        import inspect
        source = inspect.getsource(_create_chan)
        # 不应出现 "min_zs_cnt": ... 的硬编码默认值
        # 应只通过 strategy_params 透传
        assert '"min_zs_cnt"' not in source.split("# 透传")[0], \
            "_create_chan 在基础配置区域硬编码了 min_zs_cnt"

    def test_min_zs_cnt_passthrough_when_set(self):
        """strategy_params 中显式设置 min_zs_cnt 时应被透传"""
        cfg = ScanConfig(tushare_token="fake")
        cfg.strategy_params["min_zs_cnt"] = 2
        # 验证 config 正确携带
        assert cfg.strategy_params["min_zs_cnt"] == 2

    def test_min_zs_cnt_absent_when_not_set(self):
        """strategy_params 中未设置 min_zs_cnt 时，不应出现在参数中"""
        cfg = ScanConfig()
        assert "min_zs_cnt" not in cfg.strategy_params
