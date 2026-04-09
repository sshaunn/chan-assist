"""
回归测试：锁定 Phase 1 code review 中发现的架构边界违规。

背景：
- Phase 1 审批失败，因为 scripts/ 下保留了业务脚本，strategy/ 下保留了规则引擎子框架
- 这些测试确保旧文件不会重新出现在批准路径中
"""
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent


class TestScriptsBoundary:
    """验证 scripts/ 只包含批准的 CLI 入口文件"""

    APPROVED_SCRIPTS = {"run_scan.py", "run_sample_charts.py"}

    def test_no_old_scan_scripts(self):
        """scan_all_a.py / scan_all_a_v2.py 不得出现在 scripts/"""
        scripts_dir = PROJECT_ROOT / "scripts"
        py_files = {f.name for f in scripts_dir.glob("*.py")}
        forbidden = {"scan_all_a.py", "scan_all_a_v2.py"}
        leaked = py_files & forbidden
        assert not leaked, f"scripts/ 中发现违规旧脚本: {leaked}"

    def test_no_test_scripts_in_scripts_dir(self):
        """test_chan_output.py / test_rules.py 不得出现在 scripts/"""
        scripts_dir = PROJECT_ROOT / "scripts"
        py_files = {f.name for f in scripts_dir.glob("*.py")}
        forbidden = {"test_chan_output.py", "test_rules.py"}
        leaked = py_files & forbidden
        assert not leaked, f"scripts/ 中发现违规测试脚本: {leaked}"

    def test_scripts_only_approved_files(self):
        """scripts/ 只应包含批准的 .py 文件"""
        scripts_dir = PROJECT_ROOT / "scripts"
        py_files = {f.name for f in scripts_dir.glob("*.py")}
        unexpected = py_files - self.APPROVED_SCRIPTS
        assert not unexpected, f"scripts/ 中发现未批准文件: {unexpected}"


class TestStrategyBoundary:
    """验证 strategy/ 只包含批准的薄策略入口"""

    APPROVED_STRATEGY_FILES = {
        "__init__.py", "chan_strategy.py",
        "_accessor.py", "_zs_patch.py", "_bsp_filters.py", "_bsp_modify.py",
    }

    def test_no_engine_subpackage(self):
        """strategy/engine/ 不得存在"""
        engine_dir = PROJECT_ROOT / "strategy" / "engine"
        assert not engine_dir.exists(), "strategy/engine/ 存在，违反薄策略边界"

    def test_no_bsp_subpackage(self):
        """strategy/bsp/ 不得存在"""
        bsp_dir = PROJECT_ROOT / "strategy" / "bsp"
        assert not bsp_dir.exists(), "strategy/bsp/ 存在，违反薄策略边界"

    def test_no_zs_subpackage(self):
        """strategy/zs/ 不得存在"""
        zs_dir = PROJECT_ROOT / "strategy" / "zs"
        assert not zs_dir.exists(), "strategy/zs/ 存在，违反薄策略边界"

    def test_no_accessor_module(self):
        """strategy/accessor.py 不得存在"""
        accessor = PROJECT_ROOT / "strategy" / "accessor.py"
        assert not accessor.exists(), "strategy/accessor.py 存在，违反薄策略边界"

    def test_strategy_only_approved_files(self):
        """strategy/ 只应包含批准的 .py 文件"""
        strategy_dir = PROJECT_ROOT / "strategy"
        py_files = {f.name for f in strategy_dir.glob("*.py")}
        unexpected = py_files - self.APPROVED_STRATEGY_FILES
        assert not unexpected, f"strategy/ 中发现未批准文件: {unexpected}"


class TestDataSourceBaseline:
    """验证批准路径中不使用 AkShare"""

    # akshare 允许在 stock_pool.py 的 filter_inquiry 中受控使用（TuShare 无问询函接口）
    AKSHARE_ALLOWED_FILES = {"stock_pool.py"}

    def test_no_akshare_import_in_chan_assist(self):
        """chan_assist/ 中不得 import akshare（stock_pool.py filter_inquiry 除外）"""
        chan_assist_dir = PROJECT_ROOT / "chan_assist"
        for py_file in chan_assist_dir.rglob("*.py"):
            if py_file.name in self.AKSHARE_ALLOWED_FILES:
                continue
            content = py_file.read_text(encoding="utf-8")
            assert "import akshare" not in content, \
                f"{py_file} 中发现 akshare import"
            assert "from akshare" not in content, \
                f"{py_file} 中发现 akshare import"

    def test_no_akshare_import_in_scripts(self):
        """scripts/ 中不得 import akshare"""
        scripts_dir = PROJECT_ROOT / "scripts"
        for py_file in scripts_dir.rglob("*.py"):
            content = py_file.read_text(encoding="utf-8")
            assert "import akshare" not in content, \
                f"{py_file} 中发现 akshare import"

    def test_no_akshare_import_in_strategy(self):
        """strategy/ 中不得 import akshare"""
        strategy_dir = PROJECT_ROOT / "strategy"
        for py_file in strategy_dir.rglob("*.py"):
            content = py_file.read_text(encoding="utf-8")
            assert "import akshare" not in content, \
                f"{py_file} 中发现 akshare import"

    def test_no_akshare_in_pyproject_dependencies(self):
        """pyproject.toml dependencies 中不得有 akshare"""
        pyproject = PROJECT_ROOT / "pyproject.toml"
        content = pyproject.read_text(encoding="utf-8")
        # 检查 dependencies 段落中不含 akshare
        in_deps = False
        for line in content.splitlines():
            if line.strip().startswith("dependencies"):
                in_deps = True
            if in_deps and "akshare" in line.lower():
                raise AssertionError(f"pyproject.toml dependencies 中仍有 akshare: {line}")
            if in_deps and line.strip() == "]":
                in_deps = False


class TestParameterBaseline:
    """验证冻结参数口径不被违规覆盖"""

    def test_divergence_rate_frozen(self):
        """divergence_rate 必须为 0.8"""
        from chan_assist.config import ScanConfig
        cfg = ScanConfig()
        assert cfg.strategy_params["divergence_rate"] == 0.8

    def test_no_inf_divergence_in_approved_paths(self):
        """批准路径中不得出现 divergence_rate = float('inf')"""
        approved_dirs = [
            PROJECT_ROOT / "scripts",
            PROJECT_ROOT / "chan_assist",
            PROJECT_ROOT / "strategy",
        ]
        for d in approved_dirs:
            for py_file in d.rglob("*.py"):
                content = py_file.read_text(encoding="utf-8")
                assert 'float("inf")' not in content or "divergence_rate" not in content, \
                    f"{py_file} 中发现 divergence_rate = float('inf')"
                assert "float('inf')" not in content or "divergence_rate" not in content, \
                    f"{py_file} 中发现 divergence_rate = float('inf')"
