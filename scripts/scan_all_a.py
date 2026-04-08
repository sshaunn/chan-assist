"""
全 A 股买点扫描：筛选今天或昨天出现任意买点的股票。
使用 Tushare 数据源 + chan.py 缠论引擎。
"""
import sys
import time
import traceback
from pathlib import Path
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed

sys.path.insert(0, str(Path(__file__).resolve().parent / "chan.py"))

import tushare as ts

TUSHARE_TOKEN = "add7890f93d0f054ac82b5d71b08c7d0fb9b7894fff306a8f72b3ada"
WORKERS = 2          # 并发数（Tushare 5000分=500次/分钟，2进程足够）
HISTORY_DAYS = 365   # 拉取多少天历史数据
LOOKBACK_DAYS = 2    # 买点出现在最近几个交易日内算命中
API_DELAY = 0.15     # 每次 API 调用后等待秒数（2进程×400次/分钟=安全边际内）


def get_stock_list():
    """获取全 A 股列表并过滤"""
    ts.set_token(TUSHARE_TOKEN)
    pro = ts.pro_api()

    stocks = pro.stock_basic(
        exchange='', list_status='L',
        fields='ts_code,symbol,name,area,industry,list_date'
    )

    # 过滤
    stocks = stocks[~stocks['name'].str.contains('ST', case=False, na=False)]
    stocks = stocks[~stocks['ts_code'].str.startswith('688')]   # 科创板
    stocks = stocks[~stocks['symbol'].str.startswith('8')]      # 北交所
    stocks = stocks[~stocks['symbol'].str.startswith('43')]     # 北交所
    stocks = stocks[~stocks['symbol'].str.startswith('200')]    # B股
    stocks = stocks[~stocks['symbol'].str.startswith('900')]    # B股
    stocks = stocks[~stocks['symbol'].str.startswith('920')]    # CDR

    # 获取最近 N 个交易日
    trade_cal = pro.trade_cal(exchange='SSE', is_open=1, start_date='20260301', end_date='20260408')
    recent_dates = sorted(trade_cal['cal_date'].tolist(), reverse=True)[:LOOKBACK_DAYS]

    print(f"  股票总数(过滤后): {len(stocks)}")
    print(f"  目标交易日: {recent_dates}")

    return stocks.reset_index(drop=True), recent_dates


def scan_single_stock(args):
    """
    单只股票扫描（在子进程中执行）。
    返回 (code, name, hit_bsps) 或 (code, name, None) 表示出错。
    """
    ts_code, symbol, name, begin_time, recent_dates, api_delay = args

    # 子进程中需要重新 import 和设置
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent / "chan.py"))

    from Chan import CChan
    from ChanConfig import CChanConfig
    from Common.CEnum import AUTYPE, KL_TYPE
    from DataAPI.TushareAPI import set_token

    set_token(TUSHARE_TOKEN)

    config = CChanConfig({
        "bi_strict": True,
        "trigger_step": False,
        "divergence_rate": float("inf"),
        "bsp2_follow_1": False,
        "bsp3_follow_1": False,
        "min_zs_cnt": 0,
        "bs1_peak": False,
        "macd_algo": "peak",
        "bs_type": "1,2,3a,1p,2s,3b",
        "print_warning": False,
        "zs_algo": "normal",
    })

    try:
        import time as _time
        chan = CChan(
            code=symbol,
            begin_time=begin_time,
            end_time=None,
            data_src="custom:TushareAPI.CTushare",
            lv_list=[KL_TYPE.K_DAY],
            config=config,
            autype=AUTYPE.QFQ,
        )
        _time.sleep(api_delay)  # 限速保护

        if len(chan[0]) == 0:
            return (ts_code, name, None, "无数据")

        # 获取所有买卖点
        bsp_list = chan.get_latest_bsp(number=0)

        # 筛选：买点 + 在目标日期内
        hit_bsps = []
        for bsp in bsp_list:
            if not bsp.is_buy:
                continue
            bsp_date = f"{bsp.klu.time.year}{bsp.klu.time.month:02d}{bsp.klu.time.day:02d}"
            if bsp_date in recent_dates:
                hit_bsps.append({
                    "type": ",".join(t.value for t in bsp.type),
                    "date": bsp_date,
                    "price": round(bsp.klu.close, 2),
                })

        if hit_bsps:
            return (ts_code, name, hit_bsps, None)
        else:
            return (ts_code, name, [], None)

    except Exception as e:
        return (ts_code, name, None, str(e)[:80])


def main():
    t_start = time.time()

    print("=" * 70)
    print("  全 A 股买点扫描")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  并发: {WORKERS} workers  |  历史: {HISTORY_DAYS}天  |  回看: {LOOKBACK_DAYS}个交易日")
    print("=" * 70)

    # 1. 获取股票列表
    print("\n[1/3] 获取股票列表...")
    stocks, recent_dates = get_stock_list()

    # 2. 构造任务参数
    from datetime import timedelta
    begin_time = (datetime.now() - timedelta(days=HISTORY_DAYS)).strftime("%Y-%m-%d")

    tasks = [
        (row['ts_code'], row['symbol'], row['name'], begin_time, recent_dates, API_DELAY)
        for _, row in stocks.iterrows()
    ]

    # 3. 并行扫描
    print(f"\n[2/3] 开始扫描 {len(tasks)} 只股票...")
    results_hit = []
    errors = 0
    scanned = 0

    with ProcessPoolExecutor(max_workers=WORKERS) as executor:
        futures = {executor.submit(scan_single_stock, t): t for t in tasks}

        for future in as_completed(futures):
            scanned += 1
            ts_code, name, hit_bsps, err = future.result()

            if err:
                errors += 1
                if scanned <= 5 or errors <= 3:  # 前几个错误打出来看看
                    print(f"  [{scanned}/{len(tasks)}] {ts_code} {name}: ERROR {err}")
            elif hit_bsps:
                results_hit.append((ts_code, name, hit_bsps))
                types_str = " | ".join(f"{b['type']}@{b['date']}" for b in hit_bsps)
                print(f"  [{scanned}/{len(tasks)}] ✅ {ts_code} {name}: {types_str}")
            else:
                # 无买点，静默
                pass

            # 进度（每 200 只报告一次）
            if scanned % 200 == 0:
                elapsed = time.time() - t_start
                speed = scanned / elapsed
                eta = (len(tasks) - scanned) / speed / 60 if speed > 0 else 0
                print(f"  --- 进度: {scanned}/{len(tasks)}  命中: {len(results_hit)}  "
                      f"失败: {errors}  速度: {speed:.1f}只/秒  预计剩余: {eta:.1f}分钟 ---")

    # 4. 输出结果
    elapsed = time.time() - t_start
    print(f"\n{'='*70}")
    print(f"[3/3] 扫描完成")
    print(f"{'='*70}")
    print(f"  总扫描: {scanned}")
    print(f"  失败:   {errors}")
    print(f"  命中:   {len(results_hit)}")
    print(f"  耗时:   {elapsed:.0f}秒 ({elapsed/60:.1f}分钟)")

    if results_hit:
        print(f"\n{'='*70}")
        print(f"  候选池（{len(results_hit)} 只）")
        print(f"{'='*70}")
        print(f"  {'代码':<12} {'名称':<10} {'买点类型':<12} {'日期':<12} {'价格'}")
        print(f"  {'-'*60}")
        for ts_code, name, bsps in sorted(results_hit, key=lambda x: x[0]):
            for b in bsps:
                print(f"  {ts_code:<12} {name:<10} {b['type']:<12} {b['date']:<12} {b['price']}")

    # 保存到文件
    out_file = Path(__file__).parent / f"scan_result_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(f"全 A 股买点扫描结果\n")
        f.write(f"扫描时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"目标交易日: {recent_dates}\n")
        f.write(f"总扫描: {scanned}  命中: {len(results_hit)}  失败: {errors}\n")
        f.write(f"耗时: {elapsed:.0f}秒\n\n")
        f.write(f"{'代码':<12} {'名称':<10} {'买点类型':<12} {'日期':<12} {'价格'}\n")
        f.write(f"{'-'*60}\n")
        for ts_code, name, bsps in sorted(results_hit, key=lambda x: x[0]):
            for b in bsps:
                f.write(f"{ts_code:<12} {name:<10} {b['type']:<12} {b['date']:<12} {b['price']}\n")
    print(f"\n  结果已保存: {out_file}")


if __name__ == "__main__":
    main()
