"""
Phase M3 集成测试：legacy strategy 迁移后与 MVP 主链路的兼容验证。

验证范围：
- run_one_symbol() 经迁移后的 strategy 路径，结果可被 persistence 消费
- hit / no_hit / error 语义不漂移
- scan_signal 只对 hit 生效
- scan_result 全量记录
"""
import pytest
from unittest.mock import patch, MagicMock
from chan_assist.config import ScanConfig
from chan_assist.db import get_connection, init_db
from chan_assist.models import ScanResult, RESULT_STATUS_HIT, RESULT_STATUS_NO_HIT, RESULT_STATUS_ERROR
from chan_assist.scan_service import run_one_symbol
from chan_assist.persistence import persist_one_result, create_scan_run


def _config_with_dates(dates):
    cfg = ScanConfig(tushare_token="fake")
    cfg.strategy_params["recent_dates"] = dates
    return cfg


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


def _make_chan(bsp_list, kline_len=100):
    chan = MagicMock()
    kl = MagicMock()
    kl.__len__ = MagicMock(return_value=kline_len)
    kl.bi_list = []
    kl.seg_list = []
    kl.zs_list = []
    chan.__getitem__ = MagicMock(return_value=kl)
    chan.get_latest_bsp.return_value = bsp_list
    return chan


class TestRunOneSymbolWithMigratedStrategy:
    """run_one_symbol 经迁移后的 strategy 路径产出结果"""

    @patch("chan_assist.scan_service._create_chan")
    def test_hit_result_consumable_by_persistence(self, mock_create, tmp_path):
        """hit 结果可被 persistence 正确消费"""
        bsp = _make_bsp(1, True, ["1"], "20260409", 10.5)
        mock_create.return_value = _make_chan([bsp])

        config = _config_with_dates(["20260409"])
        result = run_one_symbol("000001", "平安银行", config)

        assert result.status == RESULT_STATUS_HIT
        assert result.signal_code is not None

        # 实际写入 DB 验证
        conn = get_connection(str(tmp_path / "m3_compat.db"))
        init_db(conn)
        run_id = create_scan_run(conn, started_at="2026-04-09", market="A", strategy_name="test")
        result_id = persist_one_result(conn, run_id, result)
        conn.commit()

        # 验证 scan_result
        row = conn.execute("SELECT * FROM scan_result WHERE id=?", (result_id,)).fetchone()
        assert row["status"] == "hit"
        assert row["symbol"] == "000001"

        # 验证 scan_signal 存在
        sig_count = conn.execute(
            "SELECT COUNT(*) FROM scan_signal WHERE result_id=?", (result_id,)
        ).fetchone()[0]
        assert sig_count >= 1

        conn.close()

    @patch("chan_assist.scan_service._create_chan")
    def test_no_hit_result_consumable(self, mock_create, tmp_path):
        """no_hit 结果可被 persistence 消费，不写 signal"""
        mock_create.return_value = _make_chan([])

        config = _config_with_dates(["20260409"])
        result = run_one_symbol("000002", "万科A", config)

        assert result.status == RESULT_STATUS_NO_HIT

        conn = get_connection(str(tmp_path / "m3_compat.db"))
        init_db(conn)
        run_id = create_scan_run(conn, started_at="2026-04-09", market="A", strategy_name="test")
        result_id = persist_one_result(conn, run_id, result)
        conn.commit()

        row = conn.execute("SELECT * FROM scan_result WHERE id=?", (result_id,)).fetchone()
        assert row["status"] == "no_hit"

        sig_count = conn.execute(
            "SELECT COUNT(*) FROM scan_signal WHERE result_id=?", (result_id,)
        ).fetchone()[0]
        assert sig_count == 0

        conn.close()

    @patch("chan_assist.scan_service._create_chan")
    def test_error_result_consumable(self, mock_create, tmp_path):
        """error 结果可被 persistence 消费"""
        mock_create.side_effect = ConnectionError("网络超时")

        config = _config_with_dates(["20260409"])
        result = run_one_symbol("000003", "测试股", config)

        assert result.status == RESULT_STATUS_ERROR
        assert result.error_msg is not None

        conn = get_connection(str(tmp_path / "m3_compat.db"))
        init_db(conn)
        run_id = create_scan_run(conn, started_at="2026-04-09", market="A", strategy_name="test")
        result_id = persist_one_result(conn, run_id, result)
        conn.commit()

        row = conn.execute("SELECT * FROM scan_result WHERE id=?", (result_id,)).fetchone()
        assert row["status"] == "error"
        assert "网络超时" in row["error_msg"]

        sig_count = conn.execute(
            "SELECT COUNT(*) FROM scan_signal WHERE result_id=?", (result_id,)
        ).fetchone()[0]
        assert sig_count == 0

        conn.close()

    @patch("chan_assist.scan_service._create_chan")
    def test_three_state_all_persist_correctly(self, mock_create, tmp_path):
        """三态全量落库验证"""
        conn = get_connection(str(tmp_path / "m3_compat.db"))
        init_db(conn)
        run_id = create_scan_run(conn, started_at="2026-04-09", market="A", strategy_name="test")
        config = _config_with_dates(["20260409"])

        # hit
        bsp = _make_bsp(1, True, ["1"], "20260409", 10.5)
        mock_create.return_value = _make_chan([bsp])
        r_hit = run_one_symbol("s1", "n1", config)
        persist_one_result(conn, run_id, r_hit)

        # no_hit
        mock_create.return_value = _make_chan([])
        mock_create.side_effect = None
        r_nohit = run_one_symbol("s2", "n2", config)
        persist_one_result(conn, run_id, r_nohit)

        # error
        mock_create.side_effect = Exception("boom")
        r_error = run_one_symbol("s3", "n3", config)
        persist_one_result(conn, run_id, r_error)

        conn.commit()

        # 验证全量
        total = conn.execute("SELECT COUNT(*) FROM scan_result WHERE run_id=?", (run_id,)).fetchone()[0]
        assert total == 3

        hits = conn.execute("SELECT COUNT(*) FROM scan_result WHERE run_id=? AND status='hit'", (run_id,)).fetchone()[0]
        no_hits = conn.execute("SELECT COUNT(*) FROM scan_result WHERE run_id=? AND status='no_hit'", (run_id,)).fetchone()[0]
        errors = conn.execute("SELECT COUNT(*) FROM scan_result WHERE run_id=? AND status='error'", (run_id,)).fetchone()[0]
        assert hits + no_hits + errors == 3

        # signal 只关联 hit
        sigs = conn.execute(
            "SELECT r.status FROM scan_signal s JOIN scan_result r ON s.result_id = r.id WHERE r.run_id=?",
            (run_id,)
        ).fetchall()
        assert all(row["status"] == "hit" for row in sigs)

        conn.close()
