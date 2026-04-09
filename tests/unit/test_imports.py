"""
Phase 1 单元测试：验证所有核心模块可 import，核心接口存在。
"""
import pytest


class TestChanAssistImports:
    """验证 chan_assist 包及其所有模块可正常导入"""

    def test_import_chan_assist(self):
        import chan_assist
        assert chan_assist is not None

    def test_import_config(self):
        from chan_assist import config
        assert config is not None

    def test_import_db(self):
        from chan_assist import db
        assert db is not None

    def test_import_models(self):
        from chan_assist import models
        assert models is not None

    def test_import_persistence(self):
        from chan_assist import persistence
        assert persistence is not None

    def test_import_stock_pool(self):
        from chan_assist import stock_pool
        assert stock_pool is not None

    def test_import_scan_service(self):
        from chan_assist import scan_service
        assert scan_service is not None


class TestStrategyImports:
    """验证 strategy 包可正常导入"""

    def test_import_strategy(self):
        import strategy
        assert strategy is not None

    def test_import_chan_strategy(self):
        from strategy import chan_strategy
        assert chan_strategy is not None


class TestCoreInterfaces:
    """验证核心接口函数存在"""

    def test_run_one_symbol_exists(self):
        from chan_assist.scan_service import run_one_symbol
        assert callable(run_one_symbol)

    def test_run_scan_exists(self):
        from chan_assist.scan_service import run_scan
        assert callable(run_scan)

    def test_get_stock_pool_exists(self):
        from chan_assist.stock_pool import get_stock_pool
        assert callable(get_stock_pool)

    def test_evaluate_signal_exists(self):
        from strategy.chan_strategy import evaluate_signal
        assert callable(evaluate_signal)

    def test_load_config_exists(self):
        from chan_assist.config import load_config
        assert callable(load_config)

    def test_get_connection_exists(self):
        from chan_assist.db import get_connection
        assert callable(get_connection)

    def test_init_db_exists(self):
        from chan_assist.db import init_db
        assert callable(init_db)

    def test_create_scan_run_exists(self):
        from chan_assist.persistence import create_scan_run
        assert callable(create_scan_run)

    def test_insert_scan_result_exists(self):
        from chan_assist.persistence import insert_scan_result
        assert callable(insert_scan_result)

    def test_insert_scan_signal_exists(self):
        from chan_assist.persistence import insert_scan_signal
        assert callable(insert_scan_signal)

    def test_update_scan_run_summary_exists(self):
        from chan_assist.persistence import update_scan_run_summary
        assert callable(update_scan_run_summary)


class TestConfigDefaults:
    """验证配置类的默认值"""

    def test_scan_config_defaults(self):
        from chan_assist.config import ScanConfig
        cfg = ScanConfig()
        assert cfg.db_path == "data/chan_assist.db"
        assert cfg.market == "A"
        assert cfg.strategy_name == "chan_default"
        assert cfg.commit_every == 50
        assert cfg.limit is None
        assert cfg.symbols is None

    def test_scan_config_divergence_rate(self):
        """验证冻结参数: divergence_rate = 0.8"""
        from chan_assist.config import ScanConfig
        cfg = ScanConfig()
        assert cfg.strategy_params["divergence_rate"] == 0.8

    def test_load_config_with_overrides(self):
        from chan_assist.config import load_config
        cfg = load_config(market="HK", limit=10, commit_every=20)
        assert cfg.market == "HK"
        assert cfg.limit == 10
        assert cfg.commit_every == 20

    def test_load_config_returns_scan_config(self):
        from chan_assist.config import load_config, ScanConfig
        cfg = load_config()
        assert isinstance(cfg, ScanConfig)


class TestModels:
    """验证数据模型"""

    def test_scan_result_construction(self):
        from chan_assist.models import ScanResult
        r = ScanResult(symbol="000001", name="平安银行", status="hit")
        assert r.symbol == "000001"
        assert r.name == "平安银行"
        assert r.status == "hit"
        assert r.signals == []
        assert r.error_msg is None

    def test_scan_result_error(self):
        from chan_assist.models import ScanResult
        r = ScanResult(symbol="000002", name="万科A", status="error", error_msg="连接超时")
        assert r.status == "error"
        assert r.error_msg == "连接超时"

    def test_scan_result_no_hit(self):
        from chan_assist.models import ScanResult
        r = ScanResult(symbol="000003", name="PT金田", status="no_hit")
        assert r.status == "no_hit"
        assert r.signal_code is None


class TestCliModule:
    """验证 CLI 入口模块"""

    def test_parse_args_defaults(self):
        from scripts.run_scan import parse_args
        args = parse_args([])
        assert args.market == "A"
        assert args.db_path == "data/chan_assist.db"
        assert args.limit == 20
        assert args.symbols is None
        assert args.commit_every == 50

    def test_parse_args_with_limit(self):
        from scripts.run_scan import parse_args
        args = parse_args(["--limit", "10"])
        assert args.limit == 10

    def test_parse_args_with_symbols(self):
        from scripts.run_scan import parse_args
        args = parse_args(["--symbols", "000001", "000002"])
        assert args.symbols == ["000001", "000002"]

    def test_parse_args_with_commit_every(self):
        from scripts.run_scan import parse_args
        args = parse_args(["--commit-every", "100"])
        assert args.commit_every == 100

    def test_main_minimal_call(self, monkeypatch):
        """验证 main() 可被最小调用：monkeypatch run_scan 使其不实际执行"""
        call_log = {}

        def fake_run_scan(config):
            call_log["config"] = config
            return {"status": "ok"}

        monkeypatch.setattr("chan_assist.scan_service.run_scan", fake_run_scan)

        from scripts.run_scan import main
        main(["--market", "A", "--limit", "5"])

        assert "config" in call_log
        assert call_log["config"].market == "A"
        assert call_log["config"].limit == 5
