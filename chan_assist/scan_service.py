"""
扫描总流程编排。

负责：
- 创建 scan_run
- 加载配置
- 获取股票池
- 逐只执行 run_one_symbol()
- 周期性 commit
- 汇总统计
- 更新 scan_run 状态
"""
import json
import sys
from pathlib import Path
from datetime import datetime, timedelta

from chan_assist.config import ScanConfig
from chan_assist.models import (
    ScanResult,
    RESULT_STATUS_HIT, RESULT_STATUS_ERROR,
    RUN_STATUS_SUCCESS, RUN_STATUS_PARTIAL_SUCCESS, RUN_STATUS_FAILED,
)


def _create_chan(symbol: str, config: ScanConfig):
    """
    创建单只股票的 CChan 对象。

    内部处理 chan.py 的 sys.path 和 import。
    """
    chan_py_root = str(Path(__file__).resolve().parent.parent / "chan.py")
    if chan_py_root not in sys.path:
        sys.path.insert(0, chan_py_root)

    from Chan import CChan
    from ChanConfig import CChanConfig
    from Common.CEnum import AUTYPE, KL_TYPE
    from DataAPI.TushareAPI import set_token

    if config.tushare_token:
        set_token(config.tushare_token)

    # 基础配置（不含策略参数，由 ChanConfig 内部默认值控制）
    chan_conf_dict = {
        "bi_strict": True,
        "trigger_step": False,
        "bsp2_follow_1": False,
        "bsp3_follow_1": False,
        "bs1_peak": False,
        "macd_algo": "peak",
        "bs_type": "1,2,3a,1p,2s,3b",
        "print_warning": False,
        "zs_algo": "normal",
    }
    # 冻结参数：divergence_rate 固定 0.8
    chan_conf_dict["divergence_rate"] = config.strategy_params.get("divergence_rate", 0.8)
    # 透传 strategy_params 中显式设置的其他参数（不硬编码默认值）
    for key in ("min_zs_cnt",):
        if key in config.strategy_params:
            chan_conf_dict[key] = config.strategy_params[key]

    chan_config = CChanConfig(chan_conf_dict)

    begin_time = (datetime.now() - timedelta(days=config.history_days)).strftime("%Y-%m-%d")

    chan = CChan(
        code=symbol,
        begin_time=begin_time,
        end_time=None,
        data_src="custom:TushareAPI.CTushare",
        lv_list=[KL_TYPE.K_DAY],
        config=chan_config,
        autype=AUTYPE.QFQ,
    )
    return chan


def run_one_symbol(symbol: str, name: str, config: ScanConfig) -> ScanResult:
    """
    单股执行：拉取数据 -> 调用策略判定 -> 返回 ScanResult。

    这是单股执行的稳定边界，不承担批量调度职责。
    异常会被收口为 error 状态，不会向上抛出。
    """
    from strategy.chan_strategy import evaluate_signal

    try:
        chan = _create_chan(symbol, config)

        if len(chan[0]) == 0:
            return ScanResult(
                symbol=symbol,
                name=name,
                status="error",
                error_msg="无K线数据",
            )

        eval_params = {"lookback_days": config.lookback_days}
        if "recent_dates" in config.strategy_params:
            eval_params["recent_dates"] = config.strategy_params["recent_dates"]
        if config.target_bsp_types:
            eval_params["target_bsp_types"] = config.target_bsp_types
        result = evaluate_signal(chan, eval_params)

        if result["hit"]:
            return ScanResult(
                symbol=symbol,
                name=name,
                status="hit",
                signal_code=result["signal_code"],
                signal_desc=result["signal_desc"],
                score=result["score"],
                signals=result["signals"],
            )
        else:
            return ScanResult(
                symbol=symbol,
                name=name,
                status="no_hit",
            )

    except Exception as e:
        return ScanResult(
            symbol=symbol,
            name=name,
            status="error",
            error_msg=str(e)[:200],
        )


def run_scan(config: ScanConfig) -> dict:
    """
    批量扫描主流程。

    流程:
        1. 初始化 DB + 创建 scan_run
        2. 获取股票池
        3. 逐只执行 run_one_symbol → persist_one_result
        4. 周期性 commit_every
        5. 汇总并更新 scan_run
        6. 返回 run 统计摘要

    返回: {"run_id": int, "status": str, "total_symbols": int,
           "processed_count": int, "hit_count": int, "error_count": int}
    """
    from chan_assist.db import get_connection, init_db
    from chan_assist.stock_pool import get_stock_pool
    from chan_assist.persistence import (
        create_scan_run, persist_one_result, update_scan_run_summary,
    )

    # 1. 初始化 DB
    conn = get_connection(config.db_path)
    init_db(conn)

    # 2. 获取股票池
    pool = get_stock_pool(
        market=config.market,
        limit=config.limit,
        symbols=config.symbols,
        tushare_token=config.tushare_token,
        filters_config=config.filters if config.filters else None,
    )
    total_symbols = len(pool)

    # 3. 创建 scan_run
    started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    run_id = create_scan_run(
        conn,
        started_at=started_at,
        market=config.market,
        strategy_name=config.strategy_name,
        params_json=json.dumps(config.strategy_params, ensure_ascii=False),
        total_symbols=total_symbols,
    )

    # 4. 逐只执行
    processed_count = 0
    hit_count = 0
    error_count = 0

    for item in pool:
        symbol = item["symbol"]
        name = item["name"]

        result = run_one_symbol(symbol, name, config)
        persist_one_result(conn, run_id, result)

        processed_count += 1
        if result.status == RESULT_STATUS_HIT:
            hit_count += 1
        elif result.status == RESULT_STATUS_ERROR:
            error_count += 1

        # 周期性 commit + 进度输出
        if config.commit_every > 0 and processed_count % config.commit_every == 0:
            conn.commit()
            print(f"  [{processed_count}/{total_symbols}] "
                  f"hit={hit_count} error={error_count} "
                  f"no_hit={processed_count - hit_count - error_count}")

    # 最终 commit
    conn.commit()

    # 5. 汇总并更新 scan_run
    finished_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if total_symbols == 0:
        final_status = RUN_STATUS_SUCCESS
    elif error_count == total_symbols:
        final_status = RUN_STATUS_FAILED
    elif error_count > 0:
        final_status = RUN_STATUS_PARTIAL_SUCCESS
    else:
        final_status = RUN_STATUS_SUCCESS

    update_scan_run_summary(
        conn, run_id,
        status=final_status,
        finished_at=finished_at,
        hit_count=hit_count,
        error_count=error_count,
        processed_count=processed_count,
    )

    conn.close()

    return {
        "run_id": run_id,
        "status": final_status,
        "total_symbols": total_symbols,
        "processed_count": processed_count,
        "hit_count": hit_count,
        "error_count": error_count,
    }
