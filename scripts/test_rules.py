"""
规则引擎测试脚本（新目录结构）。
"""
import sys
from pathlib import Path

# chan-assist 根目录和 chan.py 子模块都需要在 path 中
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "chan.py"))

from Chan import CChan
from ChanConfig import CChanConfig
from Common.CEnum import AUTYPE, KL_TYPE
from DataAPI.TushareAPI import set_token

# 导入策略层（import 时自动注册规则）
from strategy.bsp.rules_bsp_filter import b2_retrace_check, b2_in_new_zs, b2_must_enter_zs
from strategy.engine.rule_base import list_rules
from strategy.engine.executor import run_filter_rules
from strategy.bsp.bsp_modify import remove_bsp_from_chan
from strategy.accessor import get_buy_bsp_list, bsp_types, bi_time_str

set_token("add7890f93d0f054ac82b5d71b08c7d0fb9b7894fff306a8f72b3ada")

CONFIG = CChanConfig({
    "bi_strict": True, "trigger_step": False,
    "divergence_rate": float("inf"),
    "bsp2_follow_1": False, "bsp3_follow_1": False,
    "min_zs_cnt": 0, "bs1_peak": False,
    "macd_algo": "peak", "bs_type": "1,2,3a,1p,2s,3b",
    "print_warning": False, "zs_algo": "normal",
})

FILTER_RULES = [
    {"name": "b2_retrace_check", "params": {"max_rate": 0.6}},
    {"name": "b2_in_new_zs"},
    {"name": "b2_must_enter_zs", "params": {"tolerance": 0.02}},
]

TEST_STOCKS = [
    ("000001", "平安银行"),
    ("600875", "东方电气"),
    ("002109", "兴化股份"),
    ("002322", "理工能科"),
    ("300014", "亿纬锂能"),
]


def test_stock(code: str, name: str):
    print(f"\n{'='*55}")
    print(f"  {code} {name}")
    print(f"{'='*55}")

    chan = CChan(
        code=code, begin_time="2025-04-08", end_time="2026-04-08",
        data_src="custom:TushareAPI.CTushare", lv_list=[KL_TYPE.K_DAY],
        config=CONFIG, autype=AUTYPE.QFQ,
    )

    buys_before = get_buy_bsp_list(chan)
    print(f"  过滤前: {', '.join(f'笔{b.bi.idx}[{','.join(bsp_types(b))}]' for b in buys_before) or '无'}")

    result = run_filter_rules(chan, FILTER_RULES)

    for r in result["results"]:
        if r.hit:
            print(f"  {r.rule_name}: {r.detail}")

    if result["flagged_bi_indices"]:
        removed = remove_bsp_from_chan(chan, result["flagged_bi_indices"])
        for r in removed:
            kept = f", 保留[{','.join(r['kept_types'])}]" if r["kept_types"] else ""
            print(f"  删除 笔{r['bi_idx']}[{','.join(r['removed_types'])}]{kept}")

    buys_after = get_buy_bsp_list(chan)
    print(f"  过滤后: {', '.join(f'笔{b.bi.idx}[{','.join(bsp_types(b))}]' for b in buys_after) or '无'}")

    if result.get("extra_zs"):
        print(f"  补充中枢: {len(result['extra_zs'])}")
        for z in result["extra_zs"]:
            print(f"    笔{z['bi_start']}~笔{z['bi_end']} [{z['low']:.2f}, {z['high']:.2f}]")


def main():
    print("=" * 55)
    print("  规则引擎测试（新目录结构）")
    print("=" * 55)

    rules = list_rules()
    print(f"\n  已注册规则: {len(rules)} 条")
    for r in rules:
        print(f"    [{r['category']}] {r['name']}: {r['desc']}")

    import time
    for code, name in TEST_STOCKS:
        test_stock(code, name)
        time.sleep(0.12)

    print(f"\n{'='*55}")
    print("  测试完成")
    print(f"{'='*55}")


if __name__ == "__main__":
    main()
