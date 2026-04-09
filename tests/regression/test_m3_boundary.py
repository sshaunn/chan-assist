"""
回归测试：Phase M3 兼容收口与边界回归保护。

锁定的风险点：
- _bsp_modify.py 被默认接入主路径
- 架构边界白名单被放宽过头
- strategy/ 恢复 engine/bsp/zs 子包
- 迁移后 strategy 破坏 run_one_symbol 输出契约
- hit/no_hit/error 语义漂移
- scan_signal 错绑到 no_hit/error
- side effect 路径污染默认行为
"""
import inspect
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from chan_assist.models import ScanResult, VALID_RESULT_STATUSES
from chan_assist.scan_service import run_one_symbol
from chan_assist.config import ScanConfig
from strategy.chan_strategy import evaluate_signal

PROJECT_ROOT = Path(__file__).parent.parent.parent
STRATEGY_DIR = PROJECT_ROOT / "strategy"


class TestBspModifyStillOff:
    """_bsp_modify.py 不在默认主路径"""

    def test_evaluate_signal_no_bsp_modify(self):
        src = inspect.getsource(evaluate_signal)
        assert "_bsp_modify" not in src
        assert "remove_bsp_from_chan" not in src

    def test_collect_flagged_no_bsp_modify(self):
        from strategy.chan_strategy import _collect_flagged_indices
        src = inspect.getsource(_collect_flagged_indices)
        assert "_bsp_modify" not in src
        assert "remove_bsp_from_chan" not in src


class TestWhitelistNotOverBroadened:
    """架构边界白名单只允许批准的文件，不多不少"""

    ALLOWED = {
        "__init__.py", "chan_strategy.py",
        "_accessor.py", "_zs_patch.py", "_bsp_filters.py", "_bsp_modify.py",
    }

    def test_strategy_only_allowed_files(self):
        actual = {f.name for f in STRATEGY_DIR.glob("*.py")}
        extra = actual - self.ALLOWED
        assert not extra, f"strategy/ 中发现超出白名单的文件: {extra}"

    def test_no_subpackage_engine(self):
        assert not (STRATEGY_DIR / "engine").exists()

    def test_no_subpackage_bsp(self):
        assert not (STRATEGY_DIR / "bsp").exists()

    def test_no_subpackage_zs(self):
        assert not (STRATEGY_DIR / "zs").exists()

    def test_no_public_export_of_internals(self):
        """strategy/__init__.py 不应对外导出内部模块"""
        init_file = STRATEGY_DIR / "__init__.py"
        content = init_file.read_text(encoding="utf-8")
        assert "_accessor" not in content
        assert "_zs_patch" not in content
        assert "_bsp_filters" not in content
        assert "_bsp_modify" not in content


class TestRunOneSymbolOutputContract:
    """迁移后 run_one_symbol 输出必须符合 MVP 主链路契约"""

    def _config(self):
        cfg = ScanConfig(tushare_token="fake")
        cfg.strategy_params["recent_dates"] = ["20260409"]
        return cfg

    @patch("chan_assist.scan_service._create_chan")
    def test_hit_returns_valid_scan_result(self, mock_create):
        bi = MagicMock()
        bi.idx = 1
        bi._low.return_value = 10
        bi._high.return_value = 20
        bi.amp.return_value = 5
        bi.get_begin_klu.return_value = MagicMock(idx=10)
        bi.get_end_klu.return_value = MagicMock(idx=15)
        bsp = MagicMock()
        bsp.bi = bi
        bsp.is_buy = True
        bsp.type = [MagicMock(value="1")]
        bsp.klu.time.year, bsp.klu.time.month, bsp.klu.time.day = 2026, 4, 9
        bsp.klu.close = 10.5
        bsp.relate_bsp1 = None
        kl = MagicMock()
        kl.__len__ = MagicMock(return_value=100)
        kl.bi_list = []
        kl.seg_list = []
        kl.zs_list = []
        chan = MagicMock()
        chan.__getitem__ = MagicMock(return_value=kl)
        chan.get_latest_bsp.return_value = [bsp]
        mock_create.return_value = chan

        result = run_one_symbol("000001", "test", self._config())
        assert isinstance(result, ScanResult)
        assert result.status in VALID_RESULT_STATUSES

    @patch("chan_assist.scan_service._create_chan")
    def test_no_hit_has_no_signals(self, mock_create):
        kl = MagicMock()
        kl.__len__ = MagicMock(return_value=100)
        kl.bi_list = []
        kl.seg_list = []
        kl.zs_list = []
        chan = MagicMock()
        chan.__getitem__ = MagicMock(return_value=kl)
        chan.get_latest_bsp.return_value = []
        mock_create.return_value = chan

        result = run_one_symbol("000002", "test", self._config())
        assert result.status == "no_hit"
        assert result.signals == []

    @patch("chan_assist.scan_service._create_chan")
    def test_error_has_error_msg(self, mock_create):
        mock_create.side_effect = RuntimeError("crash")
        result = run_one_symbol("000003", "test", self._config())
        assert result.status == "error"
        assert result.error_msg is not None
        assert len(result.error_msg) > 0


class TestScanSignalSemantics:
    """scan_signal 只对 hit 生效，no_hit/error 不得产生 signal 数据"""

    @patch("chan_assist.scan_service._create_chan")
    def test_no_hit_result_has_empty_signals_list(self, mock_create):
        kl = MagicMock()
        kl.__len__ = MagicMock(return_value=100)
        kl.bi_list = []
        kl.seg_list = []
        kl.zs_list = []
        chan = MagicMock()
        chan.__getitem__ = MagicMock(return_value=kl)
        chan.get_latest_bsp.return_value = []
        mock_create.return_value = chan

        cfg = ScanConfig(tushare_token="fake")
        cfg.strategy_params["recent_dates"] = ["20260409"]
        result = run_one_symbol("000001", "test", cfg)
        assert result.status == "no_hit"
        assert result.signals == []

    @patch("chan_assist.scan_service._create_chan")
    def test_error_result_has_empty_signals_list(self, mock_create):
        mock_create.side_effect = Exception("err")
        cfg = ScanConfig(tushare_token="fake")
        result = run_one_symbol("000001", "test", cfg)
        assert result.status == "error"
        assert result.signals == []
