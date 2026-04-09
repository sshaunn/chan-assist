"""
Phase 4 集成测试：stock_pool 与 scan_service / config 的模块协作。
"""
import pytest
from chan_assist.config import load_config
from chan_assist.stock_pool import get_stock_pool


FAKE_STOCKS = [
    {"symbol": "000001", "name": "平安银行"},
    {"symbol": "000002", "name": "万科A"},
    {"symbol": "600036", "name": "招商银行"},
    {"symbol": "830001", "name": "北交所股"},
    {"symbol": "000010", "name": "ST测试"},
]


@pytest.fixture(autouse=True)
def mock_fetch(monkeypatch):
    """所有测试都 mock TuShare 数据源，不做真实网络调用"""
    monkeypatch.setattr(
        "chan_assist.stock_pool._fetch_a_share_list",
        lambda token: list(FAKE_STOCKS),
    )


class TestStockPoolConfigIntegration:
    """stock_pool 与 ScanConfig 参数消费的集成"""

    def test_config_symbols_fed_to_stock_pool(self):
        """ScanConfig.symbols 能被 get_stock_pool 消费"""
        config = load_config(symbols=["600036", "000001"])
        pool = get_stock_pool(
            market=config.market,
            limit=config.limit,
            symbols=config.symbols,
            tushare_token=config.tushare_token,
        )
        assert len(pool) == 2
        symbols = [s["symbol"] for s in pool]
        assert "600036" in symbols
        assert "000001" in symbols

    def test_config_limit_fed_to_stock_pool(self):
        """ScanConfig.limit 能被 get_stock_pool 消费"""
        config = load_config(limit=2, tushare_token="fake_token")
        pool = get_stock_pool(
            market=config.market,
            limit=config.limit,
            symbols=config.symbols,
            tushare_token=config.tushare_token,
        )
        assert len(pool) == 2

    def test_default_config_returns_filtered_pool(self):
        """默认 ScanConfig 走默认模式，返回过滤后的池"""
        config = load_config(tushare_token="fake_token")
        pool = get_stock_pool(
            market=config.market,
            limit=config.limit,
            symbols=config.symbols,
            tushare_token=config.tushare_token,
        )
        # 830001 和 ST 被过滤
        assert len(pool) == 3
        symbols = [s["symbol"] for s in pool]
        assert "830001" not in symbols
        assert all("ST" not in s["name"].upper() for s in pool)


class TestStockPoolOutputConsumable:
    """stock_pool 输出可被后续流程消费"""

    def test_output_has_required_keys(self):
        """每个元素必须有 symbol 和 name"""
        pool = get_stock_pool(symbols=["000001", "000002"])
        for item in pool:
            assert "symbol" in item
            assert "name" in item

    def test_output_symbols_are_strings(self):
        pool = get_stock_pool(symbols=["000001"])
        assert isinstance(pool[0]["symbol"], str)

    def test_whitelist_and_default_output_same_shape(self):
        """白名单模式和默认模式输出相同结构"""
        whitelist_pool = get_stock_pool(symbols=["000001"])
        default_pool = get_stock_pool(limit=1, tushare_token="fake_token")
        assert set(whitelist_pool[0].keys()) == set(default_pool[0].keys())

    def test_pool_can_be_iterated_for_scan(self):
        """pool 可以直接迭代，提取 symbol 和 name 给 run_one_symbol"""
        pool = get_stock_pool(symbols=["000001", "000002"])
        processed = []
        for item in pool:
            processed.append((item["symbol"], item["name"]))
        assert len(processed) == 2
        assert processed[0] == ("000001", "")
