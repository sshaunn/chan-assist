"""
买卖点过滤规则。

对 chan.py 输出的买卖点做二次验证/过滤。
chan.py 宽松输出 -> 这里严格过滤。
"""
from Common.CEnum import BSP_TYPE
from strategy.engine.rule_base import rule, RuleResult
from strategy.accessor import (
    get_bi_list, get_zs_list, get_buy_bsp_list,
    bsp_types, find_seg_for_bi, find_zs_for_seg,
)
from strategy.zs.zs_detect import detect_missing_zs


@rule(
    name="b2_retrace_check",
    desc="b2 回踩比不超过阈值",
    category="bsp_filter",
)
def b2_retrace_check(chan, max_rate: float = 0.6) -> RuleResult:
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
                "retrace": round(retrace, 4),
                "types": types,
            })

    if flagged:
        return RuleResult(
            hit=True,
            rule_name="b2_retrace_check",
            detail=f"发现 {len(flagged)} 个回踩比过高的 b2: "
                   + ", ".join(f"笔{f['bi_idx']}({f['retrace']:.0%})" for f in flagged),
            data={"flagged": flagged},
        )
    return RuleResult(hit=False, rule_name="b2_retrace_check", detail="所有 b2 回踩比正常")


@rule(
    name="b2_in_new_zs",
    desc="b2 不应落在 b1 附近的震荡中枢内（b1 之后反弹形成的新中枢除外）",
    category="bsp_filter",
)
def b2_in_new_zs(chan) -> RuleResult:
    """
    检查 b2/b2s 的笔是否落在 chan.py 遗漏的三笔中枢内。

    关键区分：
      - b1 附近的中枢（b1 笔本身参与构成）-> 震荡，假 b2，过滤
      - b1 之后反弹形成的新中枢（b1 笔不参与）-> 正常回踩确认，保留
    """
    bi_list = get_bi_list(chan)
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
                        "types": types,
                        "zs_range": f"[{zs['low']:.2f}, {zs['high']:.2f}]",
                        "zs_bi": f"笔{zs['bi_start']}~笔{zs['bi_end']}",
                        "reason": "b1 参与构成该中枢，属于震荡",
                    })
                    break

    if flagged:
        return RuleResult(
            hit=True,
            rule_name="b2_in_new_zs",
            detail=f"发现 {len(flagged)} 个落在 b1 附近震荡中枢内的 b2: "
                   + ", ".join(f"笔{f['bi_idx']}(中枢{f['zs_range']}, {f['reason']})" for f in flagged),
            data={"flagged": flagged, "extra_zs": extra_zs},
        )
    return RuleResult(hit=False, rule_name="b2_in_new_zs", detail="无 b2 落在 b1 附近震荡中枢内")


@rule(
    name="b2_must_enter_zs",
    desc="b2 的回踩低点必须落在某个中枢的 [中轴, 上沿] 区间附近",
    category="bsp_filter",
)
def b2_must_enter_zs(chan, tolerance: float = 0.02) -> RuleResult:
    """
    b2 的有效回踩区间：中枢的上半部分 [中轴, 上沿]，允许一定误差。

    参照中枢优先级：
      1. b1 之后新形成的中枢（补充中枢）
      2. b1 所在段的旧中枢（chan.py 识别的）
    """
    bi_list = get_bi_list(chan)
    seg_list = list(chan[0].seg_list)
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
                "types": types,
                "b2_low": round(b2_low, 2),
                "zs_high": round(closest["high"], 2),
                "zs_mid": round(closest["mid"], 2),
                "zs_low": round(closest["low"], 2),
                "zs_source": closest["source"],
                "position": position,
            })

    if flagged:
        return RuleResult(
            hit=True,
            rule_name="b2_must_enter_zs",
            detail=f"发现 {len(flagged)} 个回踩位置不在有效区间的 b2: "
                   + ", ".join(
                       f"笔{f['bi_idx']}(低点{f['b2_low']}, {f['zs_source']}中枢[{f['zs_low']},{f['zs_mid']},{f['zs_high']}], {f['position']})"
                       for f in flagged
                   ),
            data={"flagged": flagged},
        )
    return RuleResult(hit=False, rule_name="b2_must_enter_zs", detail="所有 b2 回踩位置在有效区间内")
