"""
Phase 7 集成测试：MVP 验证与质量闸门。

小样本验证 + 全量验证 checklist：
- scan_run.total_symbols 正确
- processed_count 正确
- scan_result 数量 == 扫描股票数
- hit + no_hit + error == total_symbols
- scan_signal 仅关联 hit
- 单股异常可定位到具体 symbol
- commit_every 不破坏闭合
- 运行结束后 run 状态正确收口
"""
import pytest
from unittest.mock import patch, MagicMock
from chan_assist.config import ScanConfig
from chan_assist.db import get_connection, init_db
from chan_assist.scan_service import run_scan


# --- Helpers ---

def _make_bsp(is_buy, types, date_str, close, bi_idx):
    bsp = MagicMock()
    bsp.is_buy = is_buy
    bsp.type = [MagicMock(value=t) for t in types]
    y, m, d = int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8])
    bsp.klu.time.year = y
    bsp.klu.time.month = m
    bsp.klu.time.day = d
    bsp.klu.close = close
    bsp.bi.idx = bi_idx
    return bsp


def _chan_hit(date="20260409"):
    bsp = _make_bsp(True, ["1"], date, 10.5, 1)
    chan = MagicMock()
    chan.__getitem__ = MagicMock(return_value=MagicMock(__len__=MagicMock(return_value=100)))
    chan.get_latest_bsp.return_value = [bsp]
    return chan


def _chan_nohit():
    chan = MagicMock()
    chan.__getitem__ = MagicMock(return_value=MagicMock(__len__=MagicMock(return_value=100)))
    chan.get_latest_bsp.return_value = []
    return chan


def _config(tmp_path, symbols, commit_every=50):
    cfg = ScanConfig(
        db_path=str(tmp_path / "validation.db"),
        tushare_token="fake",
        symbols=symbols,
        commit_every=commit_every,
    )
    cfg.strategy_params["recent_dates"] = ["20260409"]
    return cfg


# --- Validation Tests ---

class TestSmallSampleValidation:
    """小样本验证：10 只股票覆盖三态"""

    @patch("chan_assist.scan_service._create_chan")
    def test_10_symbol_sample(self, mock_create, tmp_path):
        """
        10 只股票：3 hit + 4 no_hit + 3 error
        验证全链路：CLI config → run_scan → DB 完整可审计
        """
        call_i = [0]
        def create_side(symbol, config):
            call_i[0] += 1
            if call_i[0] <= 3:
                return _chan_hit()
            elif call_i[0] <= 7:
                return _chan_nohit()
            else:
                raise Exception(f"err_{symbol}")
        mock_create.side_effect = create_side

        symbols = [f"S{i:04d}" for i in range(10)]
        config = _config(tmp_path, symbols=symbols, commit_every=4)
        result = run_scan(config)

        # 返回摘要验证
        assert result["total_symbols"] == 10
        assert result["processed_count"] == 10
        assert result["hit_count"] == 3
        assert result["error_count"] == 3
        assert result["status"] == "partial_success"

        # DB 验证
        conn = get_connection(str(tmp_path / "validation.db"))

        # scan_run
        run = conn.execute("SELECT * FROM scan_run WHERE id=?", (result["run_id"],)).fetchone()
        assert run["total_symbols"] == 10
        assert run["processed_count"] == 10
        assert run["hit_count"] == 3
        assert run["error_count"] == 3
        assert run["finished_at"] is not None
        assert run["status"] == "partial_success"

        # scan_result 数量 == 10
        results = conn.execute(
            "SELECT * FROM scan_result WHERE run_id=? ORDER BY id", (result["run_id"],)
        ).fetchall()
        assert len(results) == 10

        # 三态闭合
        hits = sum(1 for r in results if r["status"] == "hit")
        no_hits = sum(1 for r in results if r["status"] == "no_hit")
        errors = sum(1 for r in results if r["status"] == "error")
        assert hits + no_hits + errors == 10
        assert hits == 3
        assert no_hits == 4
        assert errors == 3

        # scan_signal 仅关联 hit
        signals = conn.execute("SELECT * FROM scan_signal").fetchall()
        assert len(signals) == 3  # 3 hits × 1 signal each
        for sig in signals:
            r = conn.execute(
                "SELECT status FROM scan_result WHERE id=?", (sig["result_id"],)
            ).fetchone()
            assert r["status"] == "hit"

        # error 可定位到具体 symbol
        error_results = [r for r in results if r["status"] == "error"]
        for er in error_results:
            assert er["error_msg"] is not None
            assert len(er["error_msg"]) > 0
            assert er["symbol"] is not None

        conn.close()


def _run_checklist(tmp_path, n_hit=1, n_nohit=2, n_error=1, commit_every=50):
    """Helper: 运行指定三态比例的扫描并返回 (summary, conn)"""
    total = n_hit + n_nohit + n_error
    call_i = [0]
    def create_side(symbol, config):
        call_i[0] += 1
        if call_i[0] <= n_hit:
            return _chan_hit()
        elif call_i[0] <= n_hit + n_nohit:
            return _chan_nohit()
        else:
            raise Exception(f"error_{symbol}")

    symbols = [f"V{i:04d}" for i in range(total)]
    config = _config(tmp_path, symbols=symbols, commit_every=commit_every)

    with patch("chan_assist.scan_service._create_chan", side_effect=create_side):
        summary = run_scan(config)

    conn = get_connection(str(tmp_path / "validation.db"))
    return summary, conn


class TestValidationChecklist:
    """全量验证 checklist 逐条验证"""

    def test_checklist_total_symbols_correct(self, tmp_path):
        summary, conn = _run_checklist(tmp_path, n_hit=2, n_nohit=3, n_error=1)
        run = conn.execute("SELECT total_symbols FROM scan_run WHERE id=?", (summary["run_id"],)).fetchone()
        assert run["total_symbols"] == 6
        assert summary["total_symbols"] == 6
        conn.close()

    def test_checklist_processed_count_correct(self, tmp_path):
        summary, conn = _run_checklist(tmp_path, n_hit=1, n_nohit=2, n_error=1)
        run = conn.execute("SELECT processed_count FROM scan_run WHERE id=?", (summary["run_id"],)).fetchone()
        assert run["processed_count"] == 4
        assert summary["processed_count"] == 4
        conn.close()

    def test_checklist_result_count_equals_total(self, tmp_path):
        summary, conn = _run_checklist(tmp_path, n_hit=1, n_nohit=2, n_error=2)
        count = conn.execute(
            "SELECT COUNT(*) FROM scan_result WHERE run_id=?", (summary["run_id"],)
        ).fetchone()[0]
        assert count == summary["total_symbols"]
        conn.close()

    def test_checklist_three_state_closure(self, tmp_path):
        summary, conn = _run_checklist(tmp_path, n_hit=2, n_nohit=3, n_error=1)
        rid = summary["run_id"]
        h = conn.execute("SELECT COUNT(*) FROM scan_result WHERE run_id=? AND status='hit'", (rid,)).fetchone()[0]
        n = conn.execute("SELECT COUNT(*) FROM scan_result WHERE run_id=? AND status='no_hit'", (rid,)).fetchone()[0]
        e = conn.execute("SELECT COUNT(*) FROM scan_result WHERE run_id=? AND status='error'", (rid,)).fetchone()[0]
        assert h + n + e == summary["total_symbols"]
        conn.close()

    def test_checklist_signal_only_hit(self, tmp_path):
        summary, conn = _run_checklist(tmp_path, n_hit=2, n_nohit=2, n_error=1)
        bad = conn.execute(
            "SELECT COUNT(*) FROM scan_signal s "
            "JOIN scan_result r ON s.result_id = r.id "
            "WHERE r.run_id = ? AND r.status != 'hit'", (summary["run_id"],)
        ).fetchone()[0]
        assert bad == 0
        conn.close()

    def test_checklist_error_traceable_to_symbol(self, tmp_path):
        summary, conn = _run_checklist(tmp_path, n_hit=0, n_nohit=0, n_error=3)
        errors = conn.execute(
            "SELECT symbol, error_msg FROM scan_result WHERE run_id=? AND status='error'",
            (summary["run_id"],)
        ).fetchall()
        for er in errors:
            assert er["symbol"] is not None
            assert er["error_msg"] is not None
            assert len(er["error_msg"]) > 0
        conn.close()

    def test_checklist_commit_every_preserves_closure(self, tmp_path):
        summary, conn = _run_checklist(tmp_path, n_hit=3, n_nohit=4, n_error=2, commit_every=3)
        count = conn.execute(
            "SELECT COUNT(*) FROM scan_result WHERE run_id=?", (summary["run_id"],)
        ).fetchone()[0]
        assert count == 9
        assert summary["processed_count"] == 9
        conn.close()

    def test_checklist_run_status_not_running(self, tmp_path):
        summary, conn = _run_checklist(tmp_path, n_hit=1, n_nohit=1, n_error=0)
        run = conn.execute("SELECT status, finished_at FROM scan_run WHERE id=?", (summary["run_id"],)).fetchone()
        assert run["status"] != "running"
        assert run["finished_at"] is not None
        conn.close()


class TestAbnormalScenarioValidation:
    """偏异常场景验证"""

    @patch("chan_assist.scan_service._create_chan")
    def test_all_error_run(self, mock_create, tmp_path):
        """全部 error 不崩溃，run 状态 = failed"""
        mock_create.side_effect = Exception("全部失败")
        config = _config(tmp_path, symbols=["a", "b", "c"])
        result = run_scan(config)
        assert result["status"] == "failed"
        assert result["error_count"] == 3
        assert result["processed_count"] == 3

        conn = get_connection(str(tmp_path / "validation.db"))
        count = conn.execute("SELECT COUNT(*) FROM scan_result").fetchone()[0]
        assert count == 3
        conn.close()

    @patch("chan_assist.scan_service._create_chan")
    def test_single_symbol_run(self, mock_create, tmp_path):
        """单只股票运行"""
        mock_create.return_value = _chan_nohit()
        config = _config(tmp_path, symbols=["000001"])
        result = run_scan(config)
        assert result["total_symbols"] == 1
        assert result["processed_count"] == 1
        assert result["status"] == "success"
