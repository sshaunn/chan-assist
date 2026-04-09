#!/usr/bin/env python3
"""
从扫描结果中挑选 30 只股票，运行 chan.py 分析并生成图表。

用法:
    python scripts/run_sample_charts.py --tushare-token YOUR_TOKEN
    python scripts/run_sample_charts.py --tushare-token YOUR_TOKEN --count 10
"""
import argparse
import sys
import time
from pathlib import Path
from datetime import datetime, timedelta

# chan.py path
CHAN_PY_ROOT = str(Path(__file__).resolve().parent.parent / "chan.py")
if CHAN_PY_ROOT not in sys.path:
    sys.path.insert(0, CHAN_PY_ROOT)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 从 scan_partial_result.txt 挑选的 30 只代表性股票（覆盖不同信号类型）
SAMPLE_30 = [
    # 1类买点
    ("000006", "深振业Ａ", "1"),
    ("600016", "民生银行", "1"),
    ("600030", "中信证券", "1"),
    ("300059", "东方财富", "1"),
    ("600436", "片仔癀", "1"),
    ("600745", "闻泰科技", "1"),
    ("002371", "北方华创", "1"),
    # 1p 类买点
    ("000002", "万科Ａ", "1p"),
    ("600048", "保利发展", "1p"),
    ("600809", "山西汾酒", "1p"),
    ("600690", "海尔智家", "1p"),
    ("601628", "中国人寿", "1p"),
    ("002027", "分众传媒", "1p"),
    ("300024", "机器人", "1p"),
    # 2类买点
    ("000014", "沙河股份", "2"),
    ("600177", "雅戈尔", "2"),
    ("300014", "亿纬锂能", "2"),
    ("002202", "金风科技", "2"),
    ("600219", "南山铝业", "2"),
    # 2s 类买点
    ("000100", "TCL科技", "1p,2s"),
    ("600900", "长江电力", "2s"),
    ("601939", "建设银行", "2s"),
    ("000999", "华润三九", "2s"),
    ("300033", "同花顺", "1p,2s"),
    # 3a 类买点
    ("000554", "泰山石油", "3a"),
    ("600875", "东方电气", "3a"),
    ("600307", "酒钢宏兴", "3a"),
    # 3b / 混合
    ("002109", "兴化股份", "2,3b"),
    ("600782", "新钢股份", "1,2s"),
    ("600017", "日照港", "1,2s"),
]


def parse_args():
    parser = argparse.ArgumentParser(description="30 只样本股票缠论图表生成")
    parser.add_argument("--tushare-token", required=True, help="TuShare API token")
    parser.add_argument("--count", type=int, default=30, help="生成图表数量 (default: 30)")
    parser.add_argument("--output-dir", default="data/charts", help="图表输出目录")
    parser.add_argument("--history-days", type=int, default=365, help="历史数据天数")
    parser.add_argument("--api-delay", type=float, default=0.3, help="API 调用间隔秒数")
    return parser.parse_args()


def main():
    args = parse_args()
    import matplotlib
    matplotlib.use("Agg")  # 非交互模式

    from Chan import CChan
    from ChanConfig import CChanConfig
    from Common.CEnum import AUTYPE, KL_TYPE
    from DataAPI.TushareAPI import set_token
    from Plot.PlotDriver import CPlotDriver

    set_token(args.tushare_token)

    output_dir = PROJECT_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    chan_config = CChanConfig({
        "bi_strict": True,
        "trigger_step": False,
        "divergence_rate": 0.8,
        "bsp2_follow_1": False,
        "bsp3_follow_1": False,
        "bs1_peak": False,
        "macd_algo": "peak",
        "bs_type": "1,2,3a,1p,2s,3b",
        "print_warning": False,
        "zs_algo": "normal",
    })

    begin_time = (datetime.now() - timedelta(days=args.history_days)).strftime("%Y-%m-%d")
    samples = SAMPLE_30[:args.count]

    print(f"=" * 70)
    print(f"  缠论图表生成 — {len(samples)} 只样本股票")
    print(f"  输出目录: {output_dir}")
    print(f"  历史天数: {args.history_days}")
    print(f"=" * 70)

    success = 0
    errors = 0

    for i, (symbol, name, bsp_type) in enumerate(samples, 1):
        print(f"  [{i}/{len(samples)}] {symbol} {name} ({bsp_type})...", end=" ", flush=True)
        try:
            chan = CChan(
                code=symbol,
                begin_time=begin_time,
                end_time=None,
                data_src="custom:TushareAPI.CTushare",
                lv_list=[KL_TYPE.K_DAY],
                config=chan_config,
                autype=AUTYPE.QFQ,
            )

            if len(chan[0]) == 0:
                print("无数据，跳过")
                errors += 1
                continue

            # 过滤假买卖点：收集 flagged → 从 chan 内存中移除（画图场景必须改内存）
            from strategy.chan_strategy import _collect_flagged_indices  # noqa: E402
            from strategy._bsp_modify import remove_bsp_from_chan  # noqa: E402
            flagged = _collect_flagged_indices(chan)
            if flagged:
                removed = remove_bsp_from_chan(chan, flagged)
                if removed:
                    print(f"过滤{len(removed)}个假BSP ", end="", flush=True)

            plot_config = {
                "plot_kline": True,
                "plot_bi": True,
                "plot_seg": True,
                "plot_zs": True,
                "plot_bsp": True,
                "plot_macd": True,
            }
            plot_para = {
                "figure": {
                    "x_range": 200,
                    "w": 24,
                    "h": 10,
                },
            }

            driver = CPlotDriver(chan, plot_config, plot_para)
            filename = f"{symbol}_{name.strip()}_{bsp_type.replace(',', '_')}.png"
            filepath = output_dir / filename
            driver.save2img(str(filepath))

            import matplotlib.pyplot as plt
            plt.close("all")

            print(f"OK -> {filename}")
            success += 1

        except Exception as e:
            print(f"ERROR: {str(e)[:60]}")
            errors += 1

        time.sleep(args.api_delay)

    print(f"\n{'=' * 70}")
    print(f"  完成: 成功 {success}, 失败 {errors}")
    print(f"  图表目录: {output_dir}")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
