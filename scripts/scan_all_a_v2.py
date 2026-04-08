"""
全 A 股买点扫描 v2：单进程顺序执行，稳定不限速。
5000分 Tushare = 500次/分钟，单进程 delay=0.12s ≈ 480次/分钟，安全。
"""
import sys
import time
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parent / "chan.py"))

import tushare as ts
from Chan import CChan
from ChanConfig import CChanConfig
from Common.CEnum import AUTYPE, KL_TYPE
from DataAPI.TushareAPI import set_token

TUSHARE_TOKEN = "add7890f93d0f054ac82b5d71b08c7d0fb9b7894fff306a8f72b3ada"
HISTORY_DAYS = 365
LOOKBACK_DAYS = 2
API_DELAY = 0.12  # 每次请求后等待（500次/分钟上限，0.12s=~480次/分钟）

CHAN_CONFIG = CChanConfig({
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


def main():
    t_start = time.time()
    set_token(TUSHARE_TOKEN)
    ts.set_token(TUSHARE_TOKEN)
    pro = ts.pro_api()

    print("=" * 70)
    print("  全 A 股买点扫描 v2（单进程稳定版）")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # 1. 获取股票列表
    print("\n[1] 获取股票列表...")
    stocks = pro.stock_basic(exchange='', list_status='L',
                             fields='ts_code,symbol,name,list_date')
    stocks = stocks[~stocks['name'].str.contains('ST', case=False, na=False)]
    stocks = stocks[~stocks['ts_code'].str.startswith('688')]
    stocks = stocks[~stocks['symbol'].str.startswith('8')]
    stocks = stocks[~stocks['symbol'].str.startswith('43')]
    stocks = stocks[~stocks['symbol'].str.startswith('200')]
    stocks = stocks[~stocks['symbol'].str.startswith('900')]
    stocks = stocks[~stocks['symbol'].str.startswith('920')]
    stocks = stocks.reset_index(drop=True)

    # 获取最近交易日
    trade_cal = pro.trade_cal(exchange='SSE', is_open=1,
                              start_date='20260301', end_date='20260408')
    recent_dates = sorted(trade_cal['cal_date'].tolist(), reverse=True)[:LOOKBACK_DAYS]
    print(f"  股票数: {len(stocks)}  |  目标日: {recent_dates}")

    # 2. 逐只扫描
    begin_time = (datetime.now() - timedelta(days=HISTORY_DAYS)).strftime("%Y-%m-%d")
    hits = []
    errors = 0
    total = len(stocks)

    print(f"\n[2] 开始扫描...\n")
    sys.stdout.flush()

    for i, row in stocks.iterrows():
        idx = i + 1
        code = row['symbol']
        name = row['name']

        try:
            chan = CChan(
                code=code,
                begin_time=begin_time,
                end_time=None,
                data_src="custom:TushareAPI.CTushare",
                lv_list=[KL_TYPE.K_DAY],
                config=CHAN_CONFIG,
                autype=AUTYPE.QFQ,
            )
            time.sleep(API_DELAY)

            if len(chan[0]) == 0:
                errors += 1
                continue

            bsp_list = chan.get_latest_bsp(number=0)
            for bsp in bsp_list:
                if not bsp.is_buy:
                    continue
                bsp_date = f"{bsp.klu.time.year}{bsp.klu.time.month:02d}{bsp.klu.time.day:02d}"
                if bsp_date in recent_dates:
                    types_str = ",".join(t.value for t in bsp.type)
                    price = round(bsp.klu.close, 2)
                    hits.append({
                        "ts_code": row['ts_code'], "name": name,
                        "type": types_str, "date": bsp_date, "price": price,
                    })
                    print(f"  [{idx}/{total}] ✅ {row['ts_code']} {name}: {types_str}@{bsp_date} ¥{price}")
                    sys.stdout.flush()
                    break  # 每只股票只取最近一个买点

        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  [{idx}/{total}] ❌ {row['ts_code']} {name}: {str(e)[:60]}")
                sys.stdout.flush()

        # 进度报告
        if idx % 500 == 0:
            elapsed = time.time() - t_start
            speed = idx / elapsed
            eta = (total - idx) / speed / 60 if speed > 0 else 0
            print(f"\n  --- {idx}/{total} | 命中:{len(hits)} 失败:{errors} | "
                  f"{speed:.1f}只/秒 | 剩余~{eta:.0f}分钟 ---\n")
            sys.stdout.flush()

    # 3. 输出结果
    elapsed = time.time() - t_start
    print(f"\n{'='*70}")
    print(f"  扫描完成")
    print(f"  总数: {total}  命中: {len(hits)}  失败: {errors}  耗时: {elapsed/60:.1f}分钟")
    print(f"{'='*70}")

    if hits:
        # 按类型统计
        from collections import Counter
        type_counter = Counter()
        for h in hits:
            for t in h['type'].split(','):
                type_counter[t] += 1
        print(f"\n  买点类型分布:")
        for t, c in type_counter.most_common():
            print(f"    {t}: {c}只")

        # 列表
        print(f"\n  {'代码':<12} {'名称':<10} {'类型':<10} {'日期':<12} {'价格'}")
        print(f"  {'-'*58}")
        for h in sorted(hits, key=lambda x: x['ts_code']):
            print(f"  {h['ts_code']:<12} {h['name']:<10} {h['type']:<10} {h['date']:<12} {h['price']}")

    # 保存
    out_file = Path(__file__).parent / f"scan_result_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(f"全A股买点扫描结果\n")
        f.write(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"目标日: {recent_dates}\n")
        f.write(f"总数: {total}  命中: {len(hits)}  失败: {errors}  耗时: {elapsed/60:.1f}分钟\n\n")
        f.write(f"{'代码':<12} {'名称':<10} {'类型':<10} {'日期':<12} {'价格'}\n")
        f.write(f"{'-'*58}\n")
        for h in sorted(hits, key=lambda x: x['ts_code']):
            f.write(f"{h['ts_code']:<12} {h['name']:<10} {h['type']:<10} {h['date']:<12} {h['price']}\n")
    print(f"\n  结果保存: {out_file}")


if __name__ == "__main__":
    main()
