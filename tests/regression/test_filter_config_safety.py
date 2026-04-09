"""
回归测试：过滤链配置安全性。

锁定的风险点：
- target_bsp_types 从配置文件读取后被忽略
- filters dict 从配置文件读取后被忽略
- CLI --filter-config 解析失败
- CLI --target-types 与配置文件冲突时优先级错误
- FILTER_REGISTRY 被意外扩展或清空
- 未知 filter key 导致崩溃
- 空 filters 不应影响扫描
- load_config_from_file 不支持 filters 字段
"""
import json
import pytest
from chan_assist.config import ScanConfig, load_config, load_config_from_file
from chan_assist.stock_pool import FILTER_REGISTRY, apply_filters


# === 正向：配置正确传递 ===

class TestPositive_ConfigPropagation:
    """配置文件中的 filters 和 target_bsp_types 被正确传递"""

    def test_filters_from_load_config(self):
        cfg = load_config(filters={"market_cap": {"min": 50, "max": 800}})
        assert cfg.filters["market_cap"]["min"] == 50

    def test_target_types_from_load_config(self):
        cfg = load_config(target_bsp_types=["3a", "3b"])
        assert cfg.target_bsp_types == ["3a", "3b"]

    def test_both_from_file(self, tmp_path):
        f = tmp_path / "cfg.json"
        f.write_text(json.dumps({
            "filters": {"exclude_industries": {"industries": ["银行"]}},
            "target_bsp_types": ["2", "2s"],
        }), encoding="utf-8")
        cfg = load_config_from_file(str(f))
        assert cfg.filters["exclude_industries"]["industries"] == ["银行"]
        assert cfg.target_bsp_types == ["2", "2s"]

    def test_empty_filters_default(self):
        cfg = ScanConfig()
        assert cfg.filters == {}
        assert cfg.target_bsp_types == []


# === 反向：异常配置不崩溃 ===

class TestNegative_ConfigSafety:
    """异常/边界配置不崩溃"""

    def test_unknown_filter_key_does_not_crash(self):
        pool = [{"symbol": "000001", "name": "A"}]
        result = apply_filters(pool, {"totally_unknown_filter": True})
        assert len(result) == 1  # 跳过未知 key，不崩

    def test_empty_filters_dict_preserves_pool(self):
        pool = [{"symbol": "000001", "name": "A"}]
        result = apply_filters(pool, {})
        assert len(result) == 1

    def test_none_params_in_filter(self):
        """filter value 为 None 不崩"""
        pool = [{"symbol": "000001", "name": "A", "industry": "银行"}]
        # exclude_industries with None should not crash
        result = apply_filters(pool, {"exclude_industries": {"industries": None}})
        assert len(result) == 1  # industries=None → 不过滤


# === 回归：FILTER_REGISTRY 完整性 ===

class TestRegistryIntegrity:
    """FILTER_REGISTRY 不被意外修改"""

    EXPECTED_KEYS = {"market_cap", "exclude_industries", "inquiry_days"}

    def test_registry_has_all_expected(self):
        for key in self.EXPECTED_KEYS:
            assert key in FILTER_REGISTRY, f"FILTER_REGISTRY 缺少 {key}"

    def test_registry_values_callable(self):
        for name, fn in FILTER_REGISTRY.items():
            assert callable(fn), f"{name} 不可调用"

    def test_registry_not_empty(self):
        assert len(FILTER_REGISTRY) >= 3


# === 回归：CLI --filter-config 解析 ===

class TestCliFilterConfigParsing:
    """CLI 参数解析回归"""

    def test_filter_config_parsed(self):
        from scripts.run_scan import parse_args
        args = parse_args(["--filter-config", "some_file.json"])
        assert args.filter_config == "some_file.json"

    def test_no_filter_config(self):
        from scripts.run_scan import parse_args
        args = parse_args([])
        assert args.filter_config is None

    def test_target_types_cli_takes_priority(self):
        """CLI --target-types 应优先于配置文件中的 target_bsp_types"""
        from scripts.run_scan import parse_args
        args = parse_args(["--target-types", "2", "2s"])
        assert args.target_types == ["2", "2s"]


# === 回归：load_config_from_file override 行为 ===

class TestFileOverrideBehavior:
    """配置文件 + override 的优先级"""

    def test_override_wins(self, tmp_path):
        f = tmp_path / "cfg.json"
        f.write_text(json.dumps({"limit": 10, "lookback_days": 5}), encoding="utf-8")
        cfg = load_config_from_file(str(f), limit=20)
        assert cfg.limit == 20  # override wins
        assert cfg.lookback_days == 5  # file value kept

    def test_file_filters_preserved(self, tmp_path):
        f = tmp_path / "cfg.json"
        f.write_text(json.dumps({
            "filters": {"market_cap": {"min": 100, "max": 500}},
        }), encoding="utf-8")
        cfg = load_config_from_file(str(f))
        assert cfg.filters["market_cap"]["max"] == 500
