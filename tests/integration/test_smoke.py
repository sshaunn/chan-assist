"""
Phase 1 集成冒烟测试：验证主入口和核心模块能连起来 import。
"""
import pytest


class TestProjectSmoke:
    """项目骨架冒烟测试"""

    def test_full_import_chain(self):
        """验证从 CLI -> scan_service -> config/models/stock_pool/persistence/db 的完整导入链"""
        from scripts.run_scan import parse_args, main
        from chan_assist.config import load_config, ScanConfig
        from chan_assist.scan_service import run_one_symbol, run_scan
        from chan_assist.stock_pool import get_stock_pool
        from chan_assist.models import ScanResult
        from chan_assist.db import get_connection, init_db
        from chan_assist.persistence import (
            create_scan_run,
            insert_scan_result,
            insert_scan_signal,
            update_scan_run_summary,
        )
        from strategy.chan_strategy import evaluate_signal

        # 所有导入成功即通过
        assert True

    def test_config_to_scan_service_integration(self):
        """验证 config 能被 scan_service 消费"""
        from chan_assist.config import load_config
        from chan_assist.scan_service import run_one_symbol

        config = load_config(limit=5)
        # run_one_symbol 尚未实现，但签名应能接受 config
        # 验证函数签名存在即可
        import inspect
        sig = inspect.signature(run_one_symbol)
        params = list(sig.parameters.keys())
        assert "symbol" in params
        assert "config" in params

    def test_models_dataclass_fields(self):
        """验证 ScanResult 包含所有必需字段"""
        from chan_assist.models import ScanResult
        import dataclasses
        field_names = {f.name for f in dataclasses.fields(ScanResult)}
        required = {"symbol", "name", "status", "signal_code", "signal_desc",
                     "score", "error_msg", "raw_snapshot_json", "signals"}
        assert required.issubset(field_names)

    def test_cli_parse_and_config_roundtrip(self):
        """验证 CLI 参数 -> ScanConfig 的完整链路"""
        from scripts.run_scan import parse_args
        from chan_assist.config import load_config

        args = parse_args(["--market", "A", "--limit", "10", "--commit-every", "20"])
        config = load_config(
            market=args.market,
            limit=args.limit,
            commit_every=args.commit_every,
        )
        assert config.market == "A"
        assert config.limit == 10
        assert config.commit_every == 20

    def test_db_connection_creates_file(self, tmp_path):
        """验证 get_connection 能在临时目录创建 SQLite 文件"""
        from chan_assist.db import get_connection
        db_path = str(tmp_path / "test.db")
        conn = get_connection(db_path)
        assert conn is not None
        # 验证能执行最基本的 SQL
        cursor = conn.execute("SELECT 1")
        assert cursor.fetchone()[0] == 1
        conn.close()
