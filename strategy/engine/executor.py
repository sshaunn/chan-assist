"""
规则执行器。

职责：
  - 对 CChan 执行一组规则
  - 收集规则结果
  - 返回需要过滤的买卖点索引
"""
from typing import List, Dict
from .rule_base import RuleResult, get_rule


def run_rule(rule_name: str, chan, **params) -> RuleResult:
    """执行单条规则"""
    func = get_rule(rule_name)
    return func(chan, **params)


def run_filter_rules(chan, rules: List[Dict]) -> Dict:
    """
    执行一组过滤规则，返回需要被过滤的买卖点笔 idx 集合。

    rules 格式:
        [
            {"name": "b2_retrace_check", "params": {"max_rate": 0.6}},
            {"name": "b2_in_new_zs"},
            {"name": "b2_must_enter_zs"},
        ]

    返回:
        {
            "results": [RuleResult, ...],
            "flagged_bi_indices": {10, 15, ...},
            "extra_zs": [...],
        }
    """
    all_results = []
    flagged_indices = set()
    extra_zs = []

    for rule_conf in rules:
        name = rule_conf["name"]
        params = rule_conf.get("params", {})
        result = run_rule(name, chan, **params)
        all_results.append(result)

        if result.hit and result.data:
            for item in result.data.get("flagged", []):
                flagged_indices.add(item["bi_idx"])
            if "extra_zs" in result.data:
                extra_zs = result.data["extra_zs"]

    return {
        "results": all_results,
        "flagged_bi_indices": flagged_indices,
        "extra_zs": extra_zs,
    }
