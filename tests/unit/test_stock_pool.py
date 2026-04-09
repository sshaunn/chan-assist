"""
Phase 4 单元测试：stock_pool.py — 股票池获取、过滤、标准化、截取。
"""
from unittest.mock import patch
import pytest
from chan_assist.stock_pool import (
    get_stock_pool,
    normalize_symbols,
    apply_basic_filters,
)


# --- normalize_symbols ---

class TestNormalizeSymbols:
    """symbol 标准化"""

    def test_basic(self):
        assert normalize_symbols(["000001", "000002"]) == ["000001", "000002"]

    def test_dedup_preserves_order(self):
        assert normalize_symbols(["000001", "000002", "000001"]) == ["000001", "000002"]

    def test_strips_whitespace(self):
        assert normalize_symbols(["  000001 ", "000002\t"]) == ["000001", "000002"]

    def test_removes_empty_strings(self):
        assert normalize_symbols(["", "000001", "", "000002"]) == ["000001", "000002"]

    def test_removes_none_values(self):
        assert normalize_symbols([None, "000001", None]) == ["000001"]

    def test_removes_non_string(self):
        assert normalize_symbols([123, "000001", True]) == ["000001"]

    def test_all_invalid_returns_empty(self):
        assert normalize_symbols(["", None, "  ", 0]) == []

    def test_empty_input(self):
        assert normalize_symbols([]) == []


# --- apply_basic_filters ---

class TestApplyBasicFilters:
    """基础过滤"""

    def _make(self, symbol, name="test"):
        return {"symbol": symbol, "name": name}

    def test_keeps_normal_stocks(self):
        stocks = [self._make("000001", "平安银行"), self._make("600036", "招商银行")]
        assert len(apply_basic_filters(stocks)) == 2

    def test_removes_st(self):
        stocks = [self._make("000001", "平安银行"), self._make("000002", "ST万科")]
        result = apply_basic_filters(stocks)
        assert len(result) == 1
        assert result[0]["symbol"] == "000001"

    def test_removes_st_case_insensitive(self):
        stocks = [self._make("000001", "*st测试"), self._make("000002", "正常股")]
        result = apply_basic_filters(stocks)
        assert len(result) == 1
        assert result[0]["symbol"] == "000002"

    def test_removes_bse_8x(self):
        stocks = [self._make("830001", "北交所股"), self._make("000001", "正常股")]
        result = apply_basic_filters(stocks)
        assert len(result) == 1

    def test_removes_bse_43x(self):
        stocks = [self._make("430001", "北交所股"), self._make("000001", "正常股")]
        result = apply_basic_filters(stocks)
        assert len(result) == 1

    def test_removes_b_share_200(self):
        stocks = [self._make("200001", "B股"), self._make("000001", "正常股")]
        result = apply_basic_filters(stocks)
        assert len(result) == 1

    def test_removes_b_share_900(self):
        stocks = [self._make("900001", "B股"), self._make("000001", "正常股")]
        result = apply_basic_filters(stocks)
        assert len(result) == 1

    def test_removes_cdr_920(self):
        stocks = [self._make("920001", "CDR"), self._make("000001", "正常股")]
        result = apply_basic_filters(stocks)
        assert len(result) == 1

    def test_empty_input(self):
        assert apply_basic_filters([]) == []

    def test_all_filtered_returns_empty(self):
        stocks = [self._make("830001", "ST北交所"), self._make("200001", "B股")]
        assert apply_basic_filters(stocks) == []


# --- get_stock_pool (白名单模式，不依赖外部数据源) ---

class TestGetStockPoolWhitelist:
    """get_stock_pool 白名单模式"""

    def test_whitelist_basic(self):
        result = get_stock_pool(symbols=["000001", "000002"])
        assert len(result) == 2
        assert result[0]["symbol"] == "000001"
        assert result[1]["symbol"] == "000002"

    def test_whitelist_returns_dict_with_symbol_and_name(self):
        result = get_stock_pool(symbols=["000001"])
        assert "symbol" in result[0]
        assert "name" in result[0]

    def test_whitelist_with_limit(self):
        result = get_stock_pool(symbols=["000001", "000002", "000003"], limit=2)
        assert len(result) == 2

    def test_whitelist_deduplicates(self):
        result = get_stock_pool(symbols=["000001", "000002", "000001"])
        assert len(result) == 2

    def test_whitelist_strips_whitespace(self):
        result = get_stock_pool(symbols=["  000001  "])
        assert result[0]["symbol"] == "000001"

    def test_whitelist_filters_empty_symbols(self):
        result = get_stock_pool(symbols=["", "000001", ""])
        assert len(result) == 1

    def test_whitelist_all_empty_returns_empty(self):
        result = get_stock_pool(symbols=["", "", "  "])
        assert result == []

    def test_whitelist_ignores_market(self):
        """白名单模式不检查 market"""
        result = get_stock_pool(market="HK", symbols=["000001"])
        assert len(result) == 1

    def test_whitelist_does_not_require_tushare_token(self):
        """白名单模式不需要 tushare_token"""
        result = get_stock_pool(symbols=["000001"], tushare_token="")
        assert len(result) == 1


class TestGetStockPoolDefault:
    """get_stock_pool 默认模式（mock TuShare 数据源）"""

    @patch("chan_assist.stock_pool._fetch_a_share_list")
    def test_default_mode_calls_fetch(self, mock_fetch):
        mock_fetch.return_value = [
            {"symbol": "000001", "name": "平安银行"},
            {"symbol": "000002", "name": "万科A"},
            {"symbol": "830001", "name": "北交所ST"},
        ]
        result = get_stock_pool(tushare_token="fake_token")
        mock_fetch.assert_called_once_with("fake_token")
        assert len(result) == 2
        symbols = [r["symbol"] for r in result]
        assert "000001" in symbols
        assert "000002" in symbols
        assert "830001" not in symbols

    @patch("chan_assist.stock_pool._fetch_a_share_list")
    def test_default_mode_with_limit(self, mock_fetch):
        mock_fetch.return_value = [
            {"symbol": f"00000{i}", "name": f"测试{i}"}
            for i in range(10)
        ]
        result = get_stock_pool(limit=3, tushare_token="fake_token")
        assert len(result) == 3

    def test_unsupported_market_raises(self):
        with pytest.raises(ValueError, match="market"):
            get_stock_pool(market="HK", tushare_token="fake")

    def test_missing_tushare_token_raises(self):
        """默认模式必须提供 tushare_token"""
        with pytest.raises(ValueError, match="tushare_token"):
            get_stock_pool()

    def test_empty_tushare_token_raises(self):
        with pytest.raises(ValueError, match="tushare_token"):
            get_stock_pool(tushare_token="")

    @patch("chan_assist.stock_pool._fetch_a_share_list")
    def test_limit_zero_returns_all(self, mock_fetch):
        """limit=0 不截取"""
        mock_fetch.return_value = [
            {"symbol": f"00000{i}", "name": f"测试{i}"}
            for i in range(5)
        ]
        result = get_stock_pool(limit=0, tushare_token="fake_token")
        assert len(result) == 5

    @patch("chan_assist.stock_pool._fetch_a_share_list")
    def test_limit_none_returns_all(self, mock_fetch):
        mock_fetch.return_value = [
            {"symbol": f"00000{i}", "name": f"测试{i}"}
            for i in range(5)
        ]
        result = get_stock_pool(limit=None, tushare_token="fake_token")
        assert len(result) == 5
