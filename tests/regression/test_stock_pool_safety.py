"""
回归测试：锁定 stock_pool 的输入清理与边界安全。

锁定的风险点（来自 task plan regression 要求）：
- 重复 symbol 未去重
- 空 symbol / 非法 symbol 未过滤
- limit 行为不稳定
- 白名单输入覆盖默认池失效
"""
import pytest
from chan_assist.stock_pool import get_stock_pool, normalize_symbols


FAKE_DEFAULT_STOCKS = [
    {"symbol": "000001", "name": "平安银行"},
    {"symbol": "000002", "name": "万科A"},
    {"symbol": "600036", "name": "招商银行"},
]


@pytest.fixture(autouse=True)
def mock_fetch(monkeypatch):
    monkeypatch.setattr(
        "chan_assist.stock_pool._fetch_a_share_list",
        lambda token: list(FAKE_DEFAULT_STOCKS),
    )


class TestDuplicateSymbolDedup:
    """重复 symbol 必须被去重"""

    def test_whitelist_dedup(self):
        pool = get_stock_pool(symbols=["000001", "000002", "000001", "000002"])
        assert len(pool) == 2

    def test_normalize_dedup(self):
        result = normalize_symbols(["a", "b", "a", "c", "b"])
        assert result == ["a", "b", "c"]


class TestEmptyAndInvalidSymbolFiltering:
    """空 symbol / 非法 symbol 必须被过滤"""

    def test_empty_string_filtered(self):
        pool = get_stock_pool(symbols=["", "000001", ""])
        assert len(pool) == 1
        assert pool[0]["symbol"] == "000001"

    def test_whitespace_only_filtered(self):
        pool = get_stock_pool(symbols=["   ", "000001"])
        assert len(pool) == 1

    def test_none_in_list_filtered(self):
        result = normalize_symbols([None, "000001"])
        assert result == ["000001"]

    def test_all_invalid_returns_empty(self):
        pool = get_stock_pool(symbols=["", None, "  "])
        assert pool == []


class TestLimitBehavior:
    """limit 截取行为必须稳定"""

    def test_limit_truncates(self):
        pool = get_stock_pool(symbols=["a", "b", "c", "d", "e"], limit=3)
        assert len(pool) == 3

    def test_limit_larger_than_pool_returns_all(self):
        pool = get_stock_pool(symbols=["a", "b"], limit=100)
        assert len(pool) == 2

    def test_limit_one(self):
        pool = get_stock_pool(symbols=["a", "b", "c"], limit=1)
        assert len(pool) == 1

    def test_limit_none_returns_all(self):
        pool = get_stock_pool(symbols=["a", "b", "c"])
        assert len(pool) == 3

    def test_limit_zero_returns_all(self):
        """limit=0 不截取"""
        pool = get_stock_pool(symbols=["a", "b", "c"], limit=0)
        assert len(pool) == 3


class TestWhitelistOverridesDefault:
    """白名单必须覆盖默认池"""

    def test_whitelist_ignores_default_fetch(self):
        """白名单模式不应返回默认池的内容"""
        pool = get_stock_pool(symbols=["999999"])
        assert len(pool) == 1
        assert pool[0]["symbol"] == "999999"

    def test_whitelist_not_affected_by_filters(self):
        """白名单 symbol 不经过 apply_basic_filters"""
        pool = get_stock_pool(symbols=["830001"])  # 北交所 symbol
        assert len(pool) == 1
        assert pool[0]["symbol"] == "830001"
