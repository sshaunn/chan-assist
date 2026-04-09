"""
策略参数与信号判定封装。

统一策略入口，对 chan.py 输出做策略解释，提供统一的信号判定接口。

职责边界：
- 只负责"怎么判定"
- 不管理配置文件、CLI、数据库、股票池、批量调度

内部调用顺序（固定、写死、不可动态编排）：
1. detect_missing_zs — 补充中枢检测
2. b2_retrace_check — 回踩比过滤
3. b2_in_new_zs — 震荡中枢过滤
4. b2_must_enter_zs — 回踩位置过滤
5. 构建过滤后 BSP 候选视图（非侵入式，不改 chan 内存）
6. 日期匹配 + hit/no_hit 判断
"""
from typing import Optional, List
from datetime import datetime, timedelta


def _get_recent_trade_dates(lookback_days: int = 2) -> List[str]:
    """生成最近 N 个工作日的日期字符串列表（YYYYMMDD 格式）。简易实现，不排法定假日。"""
    dates = []
    d = datetime.now()
    while len(dates) < lookback_days:
        if d.weekday() < 5:  # 周一到周五
            dates.append(d.strftime("%Y%m%d"))
        d -= timedelta(days=1)
    return dates


def _collect_flagged_indices(chan) -> set:
    """
    运行三条过滤规则，收集需排除的笔索引集合。

    固定调用顺序：
    1. detect_missing_zs（补充中枢，供后续规则使用）
    2. b2_retrace_check
    3. b2_in_new_zs
    4. b2_must_enter_zs
    """
    from strategy._zs_patch import detect_missing_zs
    from strategy._bsp_filters import b2_retrace_check, b2_in_new_zs, b2_must_enter_zs

    # Step 1: 补充中枢检测（供 b2_in_new_zs / b2_must_enter_zs 内部使用）
    detect_missing_zs(chan)

    # Step 2-4: 依次执行三条过滤规则
    flagged_indices = set()
    for rule_fn in [b2_retrace_check, b2_in_new_zs, b2_must_enter_zs]:
        for item in rule_fn(chan):
            flagged_indices.add(item["bi_idx"])

    return flagged_indices


def evaluate_signal(chan, params: Optional[dict] = None) -> dict:
    """
    对单只股票的 CChan 对象进行策略判定。

    参数:
        chan: CChan 对象（chan.py 计算完成后的结果）
        params: 策略参数，可选 keys:
            - lookback_days: int (default 2) 回看交易日数
            - recent_dates: List[str] 显式传入目标日期（覆盖 lookback_days）
            - target_bsp_types: List[str] 目标买点类型（如 ["2","2s","3a","3b"]，空列表=全类型）

    返回:
        {
            "hit": bool,
            "signal_code": str or None,
            "signal_desc": str or None,
            "score": float or None,
            "signals": [...]
        }
    """
    if params is None:
        params = {}

    lookback_days = params.get("lookback_days", 2)
    recent_dates = params.get("recent_dates", None)
    if recent_dates is None:
        recent_dates = _get_recent_trade_dates(lookback_days)
    target_bsp_types = set(params.get("target_bsp_types", []))

    # 1-4: 补充中枢 + 三条过滤规则 → 收集 flagged bi_idx
    flagged_indices = _collect_flagged_indices(chan)

    # 5: 非侵入式过滤 — 遍历 BSP 时跳过 flagged 笔
    bsp_list = chan.get_latest_bsp(number=0)
    hit_signals = []
    for bsp in bsp_list:
        if not bsp.is_buy:
            continue
        if bsp.bi.idx in flagged_indices:
            continue  # 跳过被过滤的假买卖点
        if target_bsp_types:
            bsp_type_values = {t.value for t in bsp.type}
            if not bsp_type_values & target_bsp_types:
                continue  # 跳过不在目标类型中的买点
        bsp_date = f"{bsp.klu.time.year}{bsp.klu.time.month:02d}{bsp.klu.time.day:02d}"
        if bsp_date in recent_dates:
            types_str = ",".join(t.value for t in bsp.type)
            hit_signals.append({
                "signal_type": types_str,
                "signal_level": "day",
                "signal_value": str(round(bsp.klu.close, 2)),
                "extra_json": f'{{"date":"{bsp_date}","bi_idx":{bsp.bi.idx}}}',
            })

    # 6: hit / no_hit 判断
    if hit_signals:
        all_types = ",".join(s["signal_type"] for s in hit_signals)
        first_date = hit_signals[0]["extra_json"].split('"date":"')[1].split('"')[0]
        return {
            "hit": True,
            "signal_code": all_types,
            "signal_desc": f"买点信号@{first_date}",
            "score": None,
            "signals": hit_signals,
        }
    else:
        return {
            "hit": False,
            "signal_code": None,
            "signal_desc": None,
            "score": None,
            "signals": [],
        }
