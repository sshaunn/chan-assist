"""
Phase 6 集成测试：CLI → run_scan → stock_pool → run_one_symbol → persistence → DB 完整闭环。
"""
import pytest
from unittest.mock import patch, MagicMock
from chan_assist.config import ScanConfig
from chan_assist.db import get_connection, init_db
from chan_assist.models import ScanResult
from chan_assist.scan_service import run_scan


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


def _config(tmp_path, symbols, commit_every=50):
    cfg = ScanConfig(
        db_path=str(tmp_path / "test.db"),
        tushare_token="fake",
        symbols=symbols,
        commit_every=commit_every,
    )
    cfg.strategy_params["recent_dates"] = ["20260409"]
    return cfg


class TestScanFullLoop:
    """完整批量扫描闭环"""

    @patch("chan_assist.scan_service._create_chan")
    def test_full_loop_three_states(self, mock_create, tmp_path):
        """
        完整链路：3 只股票 → hit + no_hit + error
        验证 scan_run / scan_result / scan_signal 全部正确
        """
        # 配置 mock：第一只 hit，第二只 no_hit，第三只 error
        buy_bsp = _make_bsp(is_buy=True, types=["1"], date_str="20260409", close=10.5, bi_idx=1)
        chan_hit = _make_chan_with_bsps([buy_bsp])
        chan_nohit = _make_chan_with_bsps([])
        chan_error_side = Exception("数据源超时")

        call_count = [0]
        def create_side_effect(symbol, config):
            call_count[0] += 1
            if call_count[0] == 1:
                return chan_hit
            elif call_count[0] == 2:
                return chan_nohit
            else:
                raise chan_error_side

        mock_create.side_effect = create_side_effect

        config = _config(tmp_path, symbols=["000001", "000002", "000003"])
        result = run_scan(config)

        # 验证返回摘要
        assert result["total_symbols"] == 3
        assert result["processed_count"] == 3
        assert result["hit_count"] == 1
        assert result["error_count"] == 1
        assert result["status"] == "partial_success"

        # 验证数据库内容
        conn = get_connection(str(tmp_path / "test.db"))

        # scan_run
        run = conn.execute("SELECT * FROM scan_run WHERE id=?", (result["run_id"],)).fetchone()
        assert run["status"] == "partial_success"
        assert run["total_symbols"] == 3
        assert run["hit_count"] == 1
        assert run["error_count"] == 1
        assert run["processed_count"] == 3
        assert run["finished_at"] is not None

        # scan_result: 必须 3 条
        results = conn.execute(
            "SELECT * FROM scan_result WHERE run_id=? ORDER BY id", (result["run_id"],)
        ).fetchall()
        assert len(results) == 3
        assert results[0]["status"] == "hit"
        assert results[1]["status"] == "no_hit"
        assert results[2]["status"] == "error"
        assert results[2]["error_msg"] is not None

        # scan_signal: 只关联 hit
        signals = conn.execute("SELECT * FROM scan_signal").fetchall()
        assert len(signals) == 1
        assert signals[0]["result_id"] == results[0]["id"]

        conn.close()

    @patch("chan_assist.scan_service._create_chan")
    def test_result_count_equals_pool_size(self, mock_create, tmp_path):
        """scan_result 条数 == 股票池大小"""
        mock_create.return_value = _make_chan_with_bsps([])

        config = _config(tmp_path, symbols=["a", "b", "c", "d", "e"])
        result = run_scan(config)

        conn = get_connection(str(tmp_path / "test.db"))
        count = conn.execute("SELECT COUNT(*) FROM scan_result WHERE run_id=?", (result["run_id"],)).fetchone()[0]
        assert count == 5
        assert count == result["total_symbols"]
        conn.close()

    @patch("chan_assist.scan_service._create_chan")
    def test_commit_every_with_db(self, mock_create, tmp_path):
        """commit_every 不破坏数据完整性"""
        mock_create.return_value = _make_chan_with_bsps([])

        config = _config(tmp_path, symbols=[f"s{i}" for i in range(7)], commit_every=3)
        result = run_scan(config)

        conn = get_connection(str(tmp_path / "test.db"))
        count = conn.execute("SELECT COUNT(*) FROM scan_result WHERE run_id=?", (result["run_id"],)).fetchone()[0]
        assert count == 7
        assert result["processed_count"] == 7
        conn.close()

    @patch("chan_assist.scan_service._create_chan")
    def test_signal_only_linked_to_hit(self, mock_create, tmp_path):
        """scan_signal 只关联 hit 结果（DB 级验证）"""
        buy_bsp = _make_bsp(is_buy=True, types=["1"], date_str="20260409", close=10.0, bi_idx=1)

        def create_side(symbol, config):
            if symbol == "hit1":
                return _make_chan_with_bsps([buy_bsp])
            else:
                return _make_chan_with_bsps([])

        mock_create.side_effect = create_side

        config = _config(tmp_path, symbols=["hit1", "nohit1", "nohit2"])
        result = run_scan(config)

        conn = get_connection(str(tmp_path / "test.db"))
        rows = conn.execute(
            "SELECT r.status FROM scan_signal s JOIN scan_result r ON s.result_id = r.id"
        ).fetchall()
        assert all(row["status"] == "hit" for row in rows)
        assert len(rows) == 1
        conn.close()

    @patch("chan_assist.scan_service._create_chan")
    def test_counts_closure(self, mock_create, tmp_path):
        """hit + no_hit + error == total_symbols"""
        buy_bsp = _make_bsp(is_buy=True, types=["1"], date_str="20260409", close=10.0, bi_idx=1)

        call_i = [0]
        def create_side(symbol, config):
            call_i[0] += 1
            if call_i[0] <= 2:
                return _make_chan_with_bsps([buy_bsp])
            elif call_i[0] <= 4:
                return _make_chan_with_bsps([])
            else:
                raise Exception("err")

        mock_create.side_effect = create_side

        config = _config(tmp_path, symbols=[f"s{i}" for i in range(5)])
        result = run_scan(config)

        conn = get_connection(str(tmp_path / "test.db"))
        hits = conn.execute("SELECT COUNT(*) FROM scan_result WHERE run_id=? AND status='hit'", (result["run_id"],)).fetchone()[0]
        no_hits = conn.execute("SELECT COUNT(*) FROM scan_result WHERE run_id=? AND status='no_hit'", (result["run_id"],)).fetchone()[0]
        errors = conn.execute("SELECT COUNT(*) FROM scan_result WHERE run_id=? AND status='error'", (result["run_id"],)).fetchone()[0]
        assert hits + no_hits + errors == 5
        assert hits == 2
        assert no_hits == 2
        assert errors == 1
        conn.close()
