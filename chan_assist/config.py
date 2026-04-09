"""
配置读取模块。

负责加载扫描运行所需的配置参数。
"""
import json
from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class ScanConfig:
    """扫描任务配置"""
    # 数据库路径
    db_path: str = "data/chan_assist.db"

    # 市场
    market: str = "A"

    # 策略名称
    strategy_name: str = "chan_default"

    # 批量提交频率
    commit_every: int = 50

    # 小样本模式：限制扫描股票数
    limit: Optional[int] = None

    # 指定股票列表（覆盖默认池）
    symbols: Optional[List[str]] = None

    # TuShare API token
    tushare_token: str = ""

    # 回看天数
    history_days: int = 365

    # 回看交易日（买点在最近几个交易日内算命中）
    lookback_days: int = 2

    # 目标买点类型筛选（空列表 = 全类型）
    # 有效值: "1", "1p", "2", "2s", "3a", "3b"
    target_bsp_types: List[str] = field(default_factory=list)

    # 股票池过滤配置（dict 驱动，key=过滤名，value=参数）
    # 例如: {"market_cap": {"min": 50, "max": 800}, "exclude_industries": ["银行"]}
    filters: dict = field(default_factory=dict)

    # 策略参数（传给 chan_strategy）
    strategy_params: dict = field(default_factory=lambda: {
        "divergence_rate": 0.8,
    })


def load_config(**overrides) -> ScanConfig:
    """加载配置，支持覆盖默认值"""
    return ScanConfig(**overrides)


def load_config_from_file(path: str, **overrides) -> ScanConfig:
    """从 JSON 文件加载配置，overrides 可覆盖文件中的值"""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    data.update(overrides)
    return ScanConfig(**data)
