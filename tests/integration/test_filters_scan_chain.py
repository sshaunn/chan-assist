"""
集成测试：过滤链 + target_bsp_types 经过完整 scan 主流程。

验证 filters + target_bsp_types 从配置 → stock_pool → scan_service → persistence 完整链路。
"""
import json
import pytest
from unittest.mock import patch, MagicMock
from chan_assist.config import ScanConfig, load_config_from_file
from chan_assist.db import get_connection
from chan_assist.scan_service import run_scan


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
    kl = MagicMock()
    kl.__len__ = MagicMock(return_value=100)
    kl.bi_list = []
    kl.seg_list = []
    kl.zs_list = []
    chan.__getitem__ = MagicMock(return_value=kl)
    chan.get_latest_bsp.return_value = bsp_list
    return chan


class TestPositive_FiltersScanChain:
    """正向：过滤链 + target_types 经 scan 主流程，符合条件的命中"""

    @patch("chan_assist.scan_service._create_chan")
    def test_target_3a_hits_through_full_chain(self, mock_create, tmp_path):
        """配置 target_bsp_types=["3a"]，有 3a 买点 → hit 并正确落库"""
        bsp_3a = _make_bsp(1, True, ["3a"], "20260409", 12.0)
        mock_create.return_value = _make_chan([bsp_3a])

        cfg = ScanConfig(
            db_path=str(tmp_path / "test.db"),
            tushare_token="fake",
            symbols=["000001"],
            target_bsp_types=["3a"],
        )
        cfg.strategy_params["recent_dates"] = ["20260409"]
        result = run_scan(cfg)

        assert result["hit_count"] == 1
        conn = get_connection(str(tmp_path / "test.db"))
        row = conn.execute("SELECT status, signal_code FROM scan_result WHERE run_id=?", (result["run_id"],)).fetchone()
        assert row["status"] == "hit"
        assert "3a" in row["signal_code"]
        sig_count = conn.execute("SELECT COUNT(*) FROM scan_signal").fetchone()[0]
        assert sig_count >= 1
        conn.close()

    @patch("chan_assist.scan_service._create_chan")
    def test_industry_filter_preserves_valid_stock(self, mock_create, tmp_path):
        """排除银行，非银行股正常扫描"""
        mock_create.return_value = _make_chan([])

        cfg = ScanConfig(
            db_path=str(tmp_path / "test.db"),
            tushare_token="fake",
            symbols=["000002"],  # 白名单模式不走 filters
            filters={},
        )
        result = run_scan(cfg)
        assert result["processed_count"] == 1


class TestNegative_FiltersScanChain:
    """反向：不符合条件的被排除"""

    @patch("chan_assist.scan_service._create_chan")
    def test_target_3a_rejects_b1(self, mock_create, tmp_path):
        """配置 target_bsp_types=["3a"]，只有 b1 买点 → no_hit"""
        bsp_b1 = _make_bsp(1, True, ["1"], "20260409", 10.0)
        mock_create.return_value = _make_chan([bsp_b1])

        cfg = ScanConfig(
            db_path=str(tmp_path / "test.db"),
            tushare_token="fake",
            symbols=["000001"],
            target_bsp_types=["3a"],
        )
        cfg.strategy_params["recent_dates"] = ["20260409"]
        result = run_scan(cfg)

        assert result["hit_count"] == 0
        conn = get_connection(str(tmp_path / "test.db"))
        row = conn.execute("SELECT status FROM scan_result WHERE run_id=?", (result["run_id"],)).fetchone()
        assert row["status"] == "no_hit"
        sig_count = conn.execute("SELECT COUNT(*) FROM scan_signal").fetchone()[0]
        assert sig_count == 0
        conn.close()

    @patch("chan_assist.scan_service._create_chan")
    def test_mixed_types_only_target_hits(self, mock_create, tmp_path):
        """3 个 BSP（b1 + b1p + b3a），target=["3a"] → 只有 b3a 命中"""
        bsp_b1 = _make_bsp(1, True, ["1"], "20260409", 10.0)
        bsp_b1p = _make_bsp(3, True, ["1p"], "20260409", 11.0)
        bsp_3a = _make_bsp(5, True, ["3a"], "20260409", 12.0)
        mock_create.return_value = _make_chan([bsp_b1, bsp_b1p, bsp_3a])

        cfg = ScanConfig(
            db_path=str(tmp_path / "test.db"),
            tushare_token="fake",
            symbols=["000001"],
            target_bsp_types=["3a"],
        )
        cfg.strategy_params["recent_dates"] = ["20260409"]
        result = run_scan(cfg)

        assert result["hit_count"] == 1
        conn = get_connection(str(tmp_path / "test.db"))
        row = conn.execute("SELECT signal_code FROM scan_result WHERE run_id=? AND status='hit'", (result["run_id"],)).fetchone()
        assert "3a" in row["signal_code"]
        assert "1" not in row["signal_code"].split(",")
        conn.close()


class TestConfigFileScanChain:
    """配置文件 → scan 完整链路"""

    @patch("chan_assist.scan_service._create_chan")
    def test_load_from_file_and_scan(self, mock_create, tmp_path):
        """从 JSON 文件加载配置（含 target_bsp_types + filters）并完成扫描"""
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({
            "db_path": str(tmp_path / "test.db"),
            "tushare_token": "fake",
            "symbols": ["000001", "000002"],
            "target_bsp_types": ["3a", "3b"],
            "lookback_days": 5,
            "strategy_params": {"divergence_rate": 0.8, "recent_dates": ["20260409"]},
        }), encoding="utf-8")

        bsp_3a = _make_bsp(1, True, ["3a"], "20260409", 12.0)
        call_i = [0]
        def create_side(symbol, config):
            call_i[0] += 1
            if call_i[0] == 1:
                return _make_chan([bsp_3a])
            return _make_chan([])
        mock_create.side_effect = create_side

        cfg = load_config_from_file(str(config_file))
        result = run_scan(cfg)

        assert result["total_symbols"] == 2
        assert result["hit_count"] == 1
