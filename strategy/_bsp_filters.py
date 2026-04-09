"""
买卖点过滤规则。

对 chan.py 输出的买卖点做二次验证/过滤。
chan.py 宽松输出 -> 这里严格过滤。

每个函数返回统一 flagged 结构列表：
[{"bi_idx": int, "rule_name": str, "reason": str, "extra": dict | None}, ...]
空列表表示全部通过。
"""
from typing import List
from strategy._accessor import (
    get_bi_list, get_seg_list, get_buy_bsp_list,
    bsp_types, find_seg_for_bi, find_zs_for_seg,
)
from strategy._zs_patch import detect_missing_zs


def b2_retrace_check(chan, max_rate: float = 0.6) -> List[dict]:
    """
    检查所有 b2/b2s 的回踩比例。
    回踩比 = b2笔振幅 / 反弹笔振幅，超过 max_rate 的为假 b2。
    """
    bi_list = get_bi_list(chan)
    buy_bsps = get_buy_bsp_list(chan)
    flagged = []

    for bsp in buy_bsps:
        types = bsp_types(bsp)
        if "2" not in types and "2s" not in types:
            continue
        b2_bi = bsp.bi
        if b2_bi.idx < 1:
            continue
        break_bi = bi_list[b2_bi.idx - 1]
        if break_bi.amp() == 0:
            continue
        retrace = b2_bi.amp() / break_bi.amp()
        if retrace > max_rate:
            flagged.append({
                "bi_idx": b2_bi.idx,
                "rule_name": "b2_retrace_check",
                "reason": f"回踩比 {retrace:.0%} 超过阈值 {max_rate:.0%}",
                "extra": {"retrace": round(retrace, 4), "types": types},
            })

    return flagged


def b2_in_new_zs(chan) -> List[dict]:
    """
    检查 b2/b2s 的笔是否落在 chan.py 遗漏的三笔中枢内。

    关键区分：
      - b1 附近的中枢（b1 笔本身参与构成）-> 震荡，假 b2，过滤
      - b1 之后反弹形成的新中枢（b1 笔不参与）-> 正常回踩确认，保留
    """
    extra_zs = detect_missing_zs(chan)
    buy_bsps = get_buy_bsp_list(chan)
    flagged = []

    for bsp in buy_bsps:
        types = bsp_types(bsp)
        if "2" not in types and "2s" not in types:
            continue

        bi_idx = bsp.bi.idx

        relate_b1 = bsp.relate_bsp1
        if relate_b1 is not None:
            b1_idx = relate_b1.bi.idx
        elif bi_idx >= 2:
            b1_idx = bi_idx - 2
        else:
            continue

        for zs in extra_zs:
            if zs["bi_start"] <= bi_idx <= zs["bi_end"]:
                b1_in_zs = zs["bi_start"] <= b1_idx <= zs["bi_end"]
                if b1_in_zs:
                    flagged.append({
                        "bi_idx": bi_idx,
                        "rule_name": "b2_in_new_zs",
                        "reason": f"b1(笔{b1_idx})参与构成中枢[{zs['low']:.2f},{zs['high']:.2f}]，属于震荡",
                        "extra": {
                            "types": types,
                            "zs_range": [zs["low"], zs["high"]],
                            "zs_bi": [zs["bi_start"], zs["bi_end"]],
                        },
                    })
                    break

    return flagged


def b2_must_enter_zs(chan, tolerance: float = 0.02) -> List[dict]:
    """
    b2 的有效回踩区间：中枢的上半部分 [中轴, 上沿]，允许一定误差。

    参照中枢优先级：
      1. b1 之后新形成的中枢（补充中枢）
      2. b1 所在段的旧中枢（chan.py 识别的）
    """
    bi_list = get_bi_list(chan)
    seg_list = get_seg_list(chan)
    buy_bsps = get_buy_bsp_list(chan)
    extra_zs = detect_missing_zs(chan)
    flagged = []

    for bsp in buy_bsps:
        types = bsp_types(bsp)
        if "2" not in types and "2s" not in types:
            continue

        b2_bi = bsp.bi
        b2_low = b2_bi._low()

        relate_b1 = bsp.relate_bsp1
        if relate_b1 is None:
            if b2_bi.idx >= 2:
                b1_bi = bi_list[b2_bi.idx - 2]
            else:
                continue
        else:
            b1_bi = relate_b1.bi

        # 收集所有可参照的中枢
        candidate_zs = []

        for zs in extra_zs:
            if zs["bi_start"] >= b1_bi.idx:
                candidate_zs.append({
                    "low": zs["low"], "high": zs["high"],
                    "mid": (zs["low"] + zs["high"]) / 2,
                    "source": "new",
                })

        seg = find_seg_for_bi(seg_list, b1_bi)
        if seg:
            for zs in find_zs_for_seg(seg):
                candidate_zs.append({
                    "low": zs.low, "high": zs.high,
                    "mid": zs.mid,
                    "source": "old",
                })

        if not candidate_zs:
            continue

        # 检查 b2 低点是否落在任一中枢的 [中轴-误差, 上沿+误差] 内
        valid = False
        for zs in candidate_zs:
            zs_height = zs["high"] - zs["low"]
            tol = zs_height * tolerance
            lower_bound = zs["mid"] - tol
            upper_bound = zs["high"] + tol

            if lower_bound <= b2_low <= upper_bound:
                valid = True
                break

        if not valid:
            closest = min(candidate_zs, key=lambda z: abs(b2_low - z["mid"]))
            if b2_low > closest["high"]:
                position = "中枢上方(未进入)"
            elif b2_low > closest["mid"]:
                position = "中枢上半部(有效区间)"
            elif b2_low > closest["low"]:
                position = "中枢下半部(回撤过深)"
            else:
                position = "中枢下方(穿透)"

            flagged.append({
                "bi_idx": b2_bi.idx,
                "rule_name": "b2_must_enter_zs",
                "reason": f"回踩低点{b2_low:.2f}不在有效区间，{position}",
                "extra": {
                    "types": types,
                    "b2_low": round(b2_low, 2),
                    "closest_zs": {
                        "high": round(closest["high"], 2),
                        "mid": round(closest["mid"], 2),
                        "low": round(closest["low"], 2),
                        "source": closest["source"],
                    },
                    "position": position,
                },
            })

    return flagged
