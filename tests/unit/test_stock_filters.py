"""
股票池可配置过滤链测试：每个过滤函数的正反用例。

正用例（positive）：符合条件的股票保留
反用例（negative）：不符合条件的股票被过滤
"""
import json
import pytest
from chan_assist.stock_pool import (
    filter_market_cap,
    filter_exclude_industries,
    filter_inquiry,
    apply_filters,
    FILTER_REGISTRY,
)
from chan_assist.config import ScanConfig, load_config, load_config_from_file


# === filter_exclude_industries ===

class TestPositive_IndustryFilter:
    """符合条件（不在排除列表）的股票保留"""

    def test_non_bank_preserved(self):
        pool = [
            {"symbol": "000001", "name": "平安银行", "industry": "银行"},
            {"symbol": "000002", "name": "万科A", "industry": "房地产"},
            {"symbol": "600036", "name": "招商银行", "industry": "银行"},
        ]
        result = filter_exclude_industries(pool, industries=["银行"])
        symbols = [s["symbol"] for s in result]
        assert "000002" in symbols
        assert len(result) == 1

    def test_no_exclusion_preserves_all(self):
        pool = [
            {"symbol": "000001", "name": "A", "industry": "银行"},
            {"symbol": "000002", "name": "B", "industry": "房地产"},
        ]
        result = filter_exclude_industries(pool, industries=[])
        assert len(result) == 2

    def test_none_industries_preserves_all(self):
        pool = [{"symbol": "000001", "name": "A", "industry": "银行"}]
        result = filter_exclude_industries(pool, industries=None)
        assert len(result) == 1


class TestNegative_IndustryFilter:
    """在排除列表中的股票被过滤"""

    def test_bank_filtered(self):
        pool = [{"symbol": "000001", "name": "平安银行", "industry": "银行"}]
        result = filter_exclude_industries(pool, industries=["银行"])
        assert len(result) == 0

    def test_multiple_industries_filtered(self):
        pool = [
            {"symbol": "000001", "name": "A", "industry": "银行"},
            {"symbol": "000002", "name": "B", "industry": "保险"},
            {"symbol": "000003", "name": "C", "industry": "房地产"},
        ]
        result = filter_exclude_industries(pool, industries=["银行", "保险"])
        assert len(result) == 1
        assert result[0]["symbol"] == "000003"

    def test_missing_industry_field_preserved(self):
        """没有 industry 字段的股票不被排除"""
        pool = [{"symbol": "000001", "name": "A"}]
        result = filter_exclude_industries(pool, industries=["银行"])
        assert len(result) == 1


# === filter_market_cap ===

class TestPositive_MarketCapFilter:
    """市值在区间内的保留"""

    def test_in_range_preserved(self):
        pool = [
            {"symbol": "000001", "name": "A"},
            {"symbol": "000002", "name": "B"},
        ]
        # mock: 不传 token → 直接返回原池（查询失败不过滤）
        result = filter_market_cap(pool, min=50, max=800, tushare_token="")
        assert len(result) == 2  # 无 token 时不过滤

    def test_no_token_preserves_all(self):
        pool = [{"symbol": "000001", "name": "A"}]
        result = filter_market_cap(pool, min=50, max=800)
        assert len(result) == 1


class TestNegative_MarketCapFilter:
    """市值不在区间内的被过滤（需 mock TuShare）"""

    def test_filter_applies_with_mock(self, monkeypatch):
        """通过 monkeypatch 模拟 TuShare daily_basic"""
        import pandas as pd

        pool = [
            {"symbol": "000001", "name": "小盘股"},
            {"symbol": "000002", "name": "中盘股"},
            {"symbol": "000003", "name": "大盘股"},
        ]

        fake_df = pd.DataFrame({
            "ts_code": ["000001.SZ", "000002.SZ", "000003.SZ"],
            "total_mv": [
                30 * 10000,     # 30 亿 → 低于 min
                200 * 10000,    # 200 亿 → 在区间内
                1000 * 10000,   # 1000 亿 → 高于 max
            ],
        })

        class FakePro:
            def daily_basic(self, **kwargs):
                return fake_df

        def fake_set_token(t):
            pass

        def fake_pro_api():
            return FakePro()

        import tushare
        monkeypatch.setattr(tushare, "set_token", fake_set_token)
        monkeypatch.setattr(tushare, "pro_api", fake_pro_api)

        result = filter_market_cap(pool, min=50, max=800, tushare_token="fake")
        symbols = [s["symbol"] for s in result]
        assert "000001" not in symbols  # 30 亿 < 50 亿
        assert "000002" in symbols      # 200 亿 在区间
        assert "000003" not in symbols  # 1000 亿 > 800 亿
        assert len(result) == 1


# === filter_inquiry ===

class TestPositive_InquiryFilter:
    """无问询函的股票保留"""

    def test_days_zero_preserves_all(self):
        pool = [{"symbol": "000001", "name": "A"}]
        result = filter_inquiry(pool, days=0)
        assert len(result) == 1

    def test_negative_days_preserves_all(self):
        pool = [{"symbol": "000001", "name": "A"}]
        result = filter_inquiry(pool, days=-1)
        assert len(result) == 1


class TestNegative_InquiryFilter:
    """有问询函的股票被过滤"""

    def test_inquiry_stock_filtered(self, monkeypatch):
        import pandas as pd

        pool = [
            {"symbol": "000001", "name": "正常股"},
            {"symbol": "002046", "name": "国机精工"},
        ]

        def fake_notice(symbol, date):
            return pd.DataFrame({
                "代码": ["002046"],
                "名称": ["国机精工"],
                "公告标题": ["深交所:国机精工_监管函"],
                "公告类型": ["风险提示"],
                "公告日期": [date],
                "网址": ["http://example.com"],
            })

        import akshare
        monkeypatch.setattr(akshare, "stock_notice_report", fake_notice)

        result = filter_inquiry(pool, days=1)
        symbols = [s["symbol"] for s in result]
        assert "000001" in symbols
        assert "002046" not in symbols

    def test_clean_stock_preserved(self, monkeypatch):
        import pandas as pd

        pool = [{"symbol": "000001", "name": "正常股"}]

        def fake_notice(symbol, date):
            return pd.DataFrame({
                "代码": [],
                "名称": [],
                "公告标题": [],
                "公告类型": [],
                "公告日期": [],
                "网址": [],
            })

        import akshare
        monkeypatch.setattr(akshare, "stock_notice_report", fake_notice)

        result = filter_inquiry(pool, days=1)
        assert len(result) == 1


# === apply_filters (过滤链编排) ===

class TestPositive_ApplyFilters:
    """过滤链编排正向"""

    def test_empty_config_preserves_all(self):
        pool = [{"symbol": "000001", "name": "A", "industry": "银行"}]
        result = apply_filters(pool, {})
        assert len(result) == 1

    def test_unknown_filter_skipped(self):
        pool = [{"symbol": "000001", "name": "A"}]
        result = apply_filters(pool, {"nonexistent_filter": True})
        assert len(result) == 1


class TestNegative_ApplyFilters:
    """过滤链编排反向"""

    def test_industry_filter_via_chain(self):
        pool = [
            {"symbol": "000001", "name": "A", "industry": "银行"},
            {"symbol": "000002", "name": "B", "industry": "房地产"},
        ]
        result = apply_filters(pool, {
            "exclude_industries": {"industries": ["银行"]},
        })
        assert len(result) == 1
        assert result[0]["symbol"] == "000002"

    def test_multiple_filters_chain(self):
        """多个过滤条件叠加"""
        pool = [
            {"symbol": "000001", "name": "A", "industry": "银行"},
            {"symbol": "000002", "name": "B", "industry": "保险"},
            {"symbol": "000003", "name": "C", "industry": "房地产"},
        ]
        result = apply_filters(pool, {
            "exclude_industries": {"industries": ["银行", "保险"]},
        })
        assert len(result) == 1
        assert result[0]["industry"] == "房地产"


# === FILTER_REGISTRY ===

class TestFilterRegistry:
    """注册表完整性"""

    def test_registry_has_market_cap(self):
        assert "market_cap" in FILTER_REGISTRY

    def test_registry_has_exclude_industries(self):
        assert "exclude_industries" in FILTER_REGISTRY

    def test_registry_has_inquiry_days(self):
        assert "inquiry_days" in FILTER_REGISTRY

    def test_all_registry_values_callable(self):
        for name, fn in FILTER_REGISTRY.items():
            assert callable(fn), f"{name} is not callable"


# === Config 层 ===

class TestConfigFilters:
    """ScanConfig.filters"""

    def test_default_empty(self):
        cfg = ScanConfig()
        assert cfg.filters == {}

    def test_set_filters(self):
        cfg = ScanConfig(filters={"market_cap": {"min": 50, "max": 800}})
        assert cfg.filters["market_cap"]["min"] == 50

    def test_load_config_with_filters(self):
        cfg = load_config(filters={"exclude_industries": {"industries": ["银行"]}})
        assert "exclude_industries" in cfg.filters


class TestConfigFromFile:
    """从 JSON 文件加载配置"""

    def test_load_from_json(self, tmp_path):
        config_file = tmp_path / "scan_config.json"
        config_file.write_text(json.dumps({
            "tushare_token": "test_token",
            "limit": 10,
            "filters": {
                "market_cap": {"min": 50, "max": 800},
                "exclude_industries": {"industries": ["银行"]},
            },
        }), encoding="utf-8")
        cfg = load_config_from_file(str(config_file))
        assert cfg.tushare_token == "test_token"
        assert cfg.limit == 10
        assert cfg.filters["market_cap"]["min"] == 50

    def test_override_file_values(self, tmp_path):
        config_file = tmp_path / "scan_config.json"
        config_file.write_text(json.dumps({
            "limit": 10,
        }), encoding="utf-8")
        cfg = load_config_from_file(str(config_file), limit=20)
        assert cfg.limit == 20


# === CLI 层 ===

class TestCliFilterConfig:
    """CLI --filter-config 参数"""

    def test_parse_filter_config(self):
        from scripts.run_scan import parse_args
        args = parse_args(["--filter-config", "my_filters.json"])
        assert args.filter_config == "my_filters.json"

    def test_no_filter_config_is_none(self):
        from scripts.run_scan import parse_args
        args = parse_args([])
        assert args.filter_config is None
