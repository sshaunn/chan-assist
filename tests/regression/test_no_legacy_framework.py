"""
回归测试：锁定 legacy 框架依赖不得残留在迁入模块中。

锁定的风险点：
- @rule 装饰器残留
- RuleResult 残留
- executor / engine 依赖残留
- 全局规则注册表残留
- strategy/ 下出现独立子包
"""
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
STRATEGY_DIR = PROJECT_ROOT / "strategy"


class TestNoFrameworkResidual:
    """迁入模块中不得残留 legacy 框架依赖"""

    def _read_strategy_sources(self):
        """读取 strategy/ 下所有 .py 文件内容"""
        sources = {}
        for py_file in STRATEGY_DIR.glob("*.py"):
            sources[py_file.name] = py_file.read_text(encoding="utf-8")
        return sources

    def test_no_rule_decorator(self):
        """不得出现 @rule 装饰器"""
        for name, content in self._read_strategy_sources().items():
            assert "@rule(" not in content, f"{name} 残留 @rule 装饰器"
            assert "@rule\n" not in content, f"{name} 残留 @rule 装饰器"

    def test_no_rule_result_import(self):
        """不得 import RuleResult"""
        for name, content in self._read_strategy_sources().items():
            assert "RuleResult" not in content, f"{name} 残留 RuleResult"

    def test_no_rule_base_import(self):
        """不得 import rule_base"""
        for name, content in self._read_strategy_sources().items():
            assert "rule_base" not in content, f"{name} 残留 rule_base import"

    def test_no_executor_import(self):
        """不得 import executor"""
        for name, content in self._read_strategy_sources().items():
            assert "executor" not in content, f"{name} 残留 executor import"

    def test_no_rule_registry(self):
        """不得出现 _rule_registry 全局注册表"""
        for name, content in self._read_strategy_sources().items():
            assert "_rule_registry" not in content, f"{name} 残留 _rule_registry"

    def test_no_engine_subpackage(self):
        """strategy/ 下不得恢复 engine/ 子包"""
        assert not (STRATEGY_DIR / "engine").exists()

    def test_no_bsp_subpackage(self):
        """strategy/ 下不得恢复 bsp/ 子包"""
        assert not (STRATEGY_DIR / "bsp").exists()

    def test_no_zs_subpackage(self):
        """strategy/ 下不得恢复 zs/ 子包"""
        assert not (STRATEGY_DIR / "zs").exists()

    def test_only_approved_files(self):
        """strategy/ 只允许批准的文件"""
        approved = {
            "__init__.py", "chan_strategy.py",
            "_accessor.py", "_zs_patch.py", "_bsp_filters.py", "_bsp_modify.py",
        }
        actual = {f.name for f in STRATEGY_DIR.glob("*.py")}
        unexpected = actual - approved
        assert not unexpected, f"strategy/ 中发现未批准文件: {unexpected}"
