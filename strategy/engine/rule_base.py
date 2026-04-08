"""
规则引擎基础框架。

设计原则：
  - 规则是纯函数：输入 CChan -> 输出 RuleResult
  - 规则不修改 CChan，只读取
  - 规则通过装饰器自动注册
  - 规则可组合（AND/OR）
"""
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Any


@dataclass
class RuleResult:
    """单条规则的执行结果"""
    hit: bool                       # 是否命中
    rule_name: str                  # 规则名称
    detail: str = ""                # 命中/未命中的具体说明
    data: Optional[Dict] = None     # 附加数据（供下游使用）


# 规则注册表
_rule_registry: Dict[str, Dict] = {}


def rule(name: str, desc: str, category: str = "default"):
    """规则注册装饰器"""
    def decorator(func: Callable) -> Callable:
        _rule_registry[name] = {
            "func": func,
            "name": name,
            "desc": desc,
            "category": category,
        }
        func.rule_name = name
        func.rule_desc = desc
        return func
    return decorator


def get_all_rules() -> Dict[str, Dict]:
    return _rule_registry


def get_rule(name: str) -> Callable:
    return _rule_registry[name]["func"]


def list_rules() -> List[Dict]:
    """列出所有已注册规则"""
    return [
        {"name": r["name"], "desc": r["desc"], "category": r["category"]}
        for r in _rule_registry.values()
    ]
