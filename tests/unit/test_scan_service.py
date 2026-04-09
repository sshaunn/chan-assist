"""
Phase 5 单元测试：scan_service.py — run_one_symbol 单股执行边界。
"""
import pytest
from unittest.mock import patch, MagicMock
from chan_assist.scan_service import run_one_symbol
from chan_assist.config import ScanConfig
from chan_assist.models import ScanResult


def _default_config():
    return ScanConfig(tushare_token="fake_token")


class TestRunOneSymbolHit:
    """run_one_symbol hit 场景"""

    @patch("strategy.chan_strategy.evaluate_signal")
    @patch("chan_assist.scan_service._create_chan")
    def test_hit_returns_correct_status(self, mock_chan, mock_eval):
        mock_chan_obj = MagicMock()
        mock_chan_obj.__getitem__ = MagicMock(return_value=MagicMock(__len__=MagicMock(return_value=100)))
        mock_chan.return_value = mock_chan_obj
        mock_eval.return_value = {
            "hit": True,
            "signal_code": "1",
            "signal_desc": "买点@20260409",
            "score": 0.85,
            "signals": [{"signal_type": "1", "signal_level": "day", "signal_value": "10.5"}],
        }
        result = run_one_symbol("000001", "平安银行", _default_config())
        assert isinstance(result, ScanResult)
        assert result.status == "hit"
        assert result.signal_code == "1"
        assert result.signal_desc == "买点@20260409"
        assert result.score == 0.85
        assert len(result.signals) == 1

    @patch("strategy.chan_strategy.evaluate_signal")
    @patch("chan_assist.scan_service._create_chan")
    def test_hit_preserves_symbol_and_name(self, mock_chan, mock_eval):
        mock_chan_obj = MagicMock()
        mock_chan_obj.__getitem__ = MagicMock(return_value=MagicMock(__len__=MagicMock(return_value=100)))
        mock_chan.return_value = mock_chan_obj
        mock_eval.return_value = {
            "hit": True, "signal_code": "1", "signal_desc": "x",
            "score": None, "signals": [],
        }
        result = run_one_symbol("600036", "招商银行", _default_config())
        assert result.symbol == "600036"
        assert result.name == "招商银行"


class TestRunOneSymbolNoHit:
    """run_one_symbol no_hit 场景"""

    @patch("strategy.chan_strategy.evaluate_signal")
    @patch("chan_assist.scan_service._create_chan")
    def test_no_hit_returns_correct_status(self, mock_chan, mock_eval):
        mock_chan_obj = MagicMock()
        mock_chan_obj.__getitem__ = MagicMock(return_value=MagicMock(__len__=MagicMock(return_value=100)))
        mock_chan.return_value = mock_chan_obj
        mock_eval.return_value = {
            "hit": False, "signal_code": None, "signal_desc": None,
            "score": None, "signals": [],
        }
        result = run_one_symbol("000002", "万科A", _default_config())
        assert result.status == "no_hit"
        assert result.signal_code is None
        assert result.signals == []


class TestRunOneSymbolError:
    """run_one_symbol error 场景"""

    @patch("chan_assist.scan_service._create_chan")
    def test_exception_becomes_error(self, mock_chan):
        mock_chan.side_effect = Exception("连接超时")
        result = run_one_symbol("000003", "测试股", _default_config())
        assert result.status == "error"
        assert "连接超时" in result.error_msg

    @patch("chan_assist.scan_service._create_chan")
    def test_error_msg_truncated_to_200(self, mock_chan):
        mock_chan.side_effect = Exception("x" * 500)
        result = run_one_symbol("000003", "测试股", _default_config())
        assert len(result.error_msg) <= 200

    @patch("chan_assist.scan_service._create_chan")
    def test_empty_kline_returns_error(self, mock_chan):
        mock_chan_obj = MagicMock()
        mock_chan_obj.__getitem__ = MagicMock(return_value=MagicMock(__len__=MagicMock(return_value=0)))
        mock_chan.return_value = mock_chan_obj
        result = run_one_symbol("000004", "空数据股", _default_config())
        assert result.status == "error"
        assert "无K线数据" in result.error_msg

    @patch("strategy.chan_strategy.evaluate_signal")
    @patch("chan_assist.scan_service._create_chan")
    def test_strategy_exception_becomes_error(self, mock_chan, mock_eval):
        """策略层异常也被收口为 error"""
        mock_chan_obj = MagicMock()
        mock_chan_obj.__getitem__ = MagicMock(return_value=MagicMock(__len__=MagicMock(return_value=100)))
        mock_chan.return_value = mock_chan_obj
        mock_eval.side_effect = RuntimeError("策略内部错误")
        result = run_one_symbol("000005", "异常股", _default_config())
        assert result.status == "error"
        assert "策略内部错误" in result.error_msg


class TestRunOneSymbolNeverSwallowsErrors:
    """异常不能被吞掉伪装成 no_hit 或 hit"""

    @patch("chan_assist.scan_service._create_chan")
    def test_exception_never_becomes_no_hit(self, mock_chan):
        mock_chan.side_effect = ValueError("bad input")
        result = run_one_symbol("000001", "test", _default_config())
        assert result.status != "no_hit"
        assert result.status == "error"

    @patch("chan_assist.scan_service._create_chan")
    def test_exception_never_becomes_hit(self, mock_chan):
        mock_chan.side_effect = ValueError("bad input")
        result = run_one_symbol("000001", "test", _default_config())
        assert result.status != "hit"
        assert result.status == "error"
