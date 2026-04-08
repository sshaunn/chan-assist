"""
chan.py 结构输出验证脚本
随机拉取几只股票，验证分型/笔/线段/中枢/买卖点是否正常输出。
使用 Tushare Pro 作为数据源。
"""
import sys
import time
from pathlib import Path
from datetime import datetime, timedelta

# 将 chan.py 目录加入 path
sys.path.insert(0, str(Path(__file__).resolve().parent / "chan.py"))

from Chan import CChan
from ChanConfig import CChanConfig
from Common.CEnum import AUTYPE, BSP_TYPE, DATA_SRC, FX_TYPE, KL_TYPE

# 初始化 Tushare token
from DataAPI.TushareAPI import set_token
set_token("add7890f93d0f054ac82b5d71b08c7d0fb9b7894fff306a8f72b3ada")


# ── 测试用的股票列表（不同板块各取一只）──
TEST_STOCKS = [
    ("000001", "平安银行"),    # 深圳主板
    ("600519", "贵州茅台"),    # 上海主板
    ("002475", "立讯精密"),    # 中小板
    ("300750", "宁德时代"),    # 创业板
]

# ── CChanConfig 参数 ──
CHAN_CONFIG = CChanConfig({
    "bi_strict": True,
    "trigger_step": False,
    "skip_step": 0,
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

# 数据源：通过 custom: 机制加载 Tushare
DATA_SOURCE = "custom:TushareAPI.CTushare"


def format_time(t):
    """CTime -> str"""
    return f"{t.year}-{t.month:02d}-{t.day:02d}"


def test_single_stock(code: str, name: str):
    """对单只股票跑 chan.py，输出结构摘要"""
    begin_time = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
    end_time = datetime.now().strftime("%Y-%m-%d")

    print(f"\n{'='*70}")
    print(f"  {code} {name}")
    print(f"  数据范围: {begin_time} ~ {end_time}  |  数据源: Tushare  |  级别: 日线")
    print(f"{'='*70}")

    t0 = time.time()
    try:
        chan = CChan(
            code=code,
            begin_time=begin_time,
            end_time=end_time,
            data_src=DATA_SOURCE,
            lv_list=[KL_TYPE.K_DAY],
            config=CHAN_CONFIG,
            autype=AUTYPE.QFQ,
        )
    except Exception as e:
        print(f"  [ERROR] 计算失败: {e}")
        return None
    elapsed = time.time() - t0

    kl_list = chan[0]  # 第一级别 (日线) 的 CKLine_List

    # ── 1. K 线基本信息 ──
    raw_klu_count = sum(len(klc.lst) for klc in kl_list.lst)
    combined_klc_count = len(kl_list.lst)
    print(f"\n  [K线]")
    print(f"    原始 K 线数: {raw_klu_count}")
    print(f"    合并 K 线数: {combined_klc_count}")
    if combined_klc_count > 0:
        first_t = kl_list.lst[0].lst[0].time
        last_t = kl_list.lst[-1].lst[-1].time
        print(f"    时间范围: {format_time(first_t)} ~ {format_time(last_t)}")

    # ── 2. 分型 ──
    fx_top_count = sum(1 for klc in kl_list.lst if klc.fx == FX_TYPE.TOP)
    fx_bottom_count = sum(1 for klc in kl_list.lst if klc.fx == FX_TYPE.BOTTOM)
    print(f"\n  [分型]")
    print(f"    顶分型数: {fx_top_count}")
    print(f"    底分型数: {fx_bottom_count}")

    # 最近 3 个分型
    recent_fx = [(klc.fx, klc.lst[-1].time, klc.high, klc.low)
                 for klc in kl_list.lst if klc.fx != FX_TYPE.UNKNOWN]
    if recent_fx:
        print(f"    最近分型:")
        for fx_type, t, h, l in recent_fx[-3:]:
            label = "顶" if fx_type == FX_TYPE.TOP else "底"
            print(f"      {label}分型 @ {format_time(t)}  高={h:.2f}  低={l:.2f}")

    # ── 3. 笔 ──
    bi_list = list(kl_list.bi_list)
    bi_sure = [b for b in bi_list if b.is_sure]
    bi_unsure = [b for b in bi_list if not b.is_sure]
    print(f"\n  [笔]")
    print(f"    总笔数: {len(bi_list)}  (确认: {len(bi_sure)}, 未确认: {len(bi_unsure)})")

    if bi_list:
        print(f"    最近 3 笔:")
        for bi in bi_list[-3:]:
            dir_str = "↑" if bi.dir.name == "UP" else "↓"
            sure_str = "确认" if bi.is_sure else "未确认"
            begin_t = format_time(bi.begin_klc.lst[0].time)
            end_t = format_time(bi.end_klc.lst[-1].time)
            print(f"      笔{bi.idx} {dir_str} {begin_t}→{end_t}  "
                  f"起={bi.get_begin_val():.2f} 止={bi.get_end_val():.2f}  "
                  f"振幅={bi.amp():.2f}  [{sure_str}]")

    # ── 4. 线段 ──
    seg_list = list(kl_list.seg_list)
    print(f"\n  [线段]")
    print(f"    总线段数: {len(seg_list)}")

    if seg_list:
        print(f"    最近 3 段:")
        for seg in seg_list[-3:]:
            dir_str = "↑" if seg.dir.name == "UP" else "↓"
            sure_str = "确认" if seg.is_sure else "未确认"
            begin_t = format_time(seg.start_bi.begin_klc.lst[0].time)
            end_t = format_time(seg.end_bi.end_klc.lst[-1].time)
            bi_cnt = seg.end_bi.idx - seg.start_bi.idx + 1
            print(f"      段{seg.idx} {dir_str} {begin_t}→{end_t}  "
                  f"含{bi_cnt}笔  起={seg.get_begin_val():.2f} 止={seg.get_end_val():.2f}  [{sure_str}]")

    # ── 5. 中枢 ──
    zs_list = list(kl_list.zs_list)
    print(f"\n  [中枢]")
    print(f"    总中枢数: {len(zs_list)}")

    if zs_list:
        print(f"    最近 3 个中枢:")
        for zs in zs_list[-3:]:
            begin_t = format_time(zs.begin.time)
            end_t = format_time(zs.end.time)
            print(f"      中枢 {begin_t}→{end_t}  "
                  f"区间=[{zs.low:.2f}, {zs.high:.2f}]  中轴={zs.mid:.2f}  "
                  f"极值=[{zs.peak_low:.2f}, {zs.peak_high:.2f}]")

    # ── 6. 买卖点 ──
    bsp_list = chan.get_latest_bsp(number=0)  # 所有买卖点
    buy_points = [b for b in bsp_list if b.is_buy]
    sell_points = [b for b in bsp_list if not b.is_buy]
    print(f"\n  [买卖点]")
    print(f"    总数: {len(bsp_list)}  (买点: {len(buy_points)}, 卖点: {len(sell_points)})")

    if bsp_list:
        print(f"    最近 5 个买卖点:")
        for bsp in bsp_list[:5]:  # get_latest_bsp 已按时间倒序
            bs_str = "买" if bsp.is_buy else "卖"
            types_str = ",".join(t.value for t in bsp.type)
            t_str = format_time(bsp.klu.time)
            print(f"      {bs_str}点 [{types_str}] @ {t_str}  价格={bsp.klu.close:.2f}")

    # ── 7. 最近买卖点与当前距离 ──
    if buy_points:
        latest_buy = buy_points[0]
        buy_t = format_time(latest_buy.klu.time)
        last_close = kl_list.lst[-1].lst[-1].close
        dist_pct = (last_close - latest_buy.klu.close) / latest_buy.klu.close * 100
        print(f"\n  [最近买点距今]")
        print(f"    最近买点: {','.join(t.value for t in latest_buy.type)} @ {buy_t}  价格={latest_buy.klu.close:.2f}")
        print(f"    当前价格: {last_close:.2f}  距买点: {dist_pct:+.1f}%")

    print(f"\n  [计算耗时] {elapsed:.2f}s")
    return chan


def main():
    print("=" * 70)
    print("  chan.py 结构输出验证测试")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Python: {sys.version.split()[0]}")
    print("=" * 70)

    results = {}
    for code, name in TEST_STOCKS:
        chan = test_single_stock(code, name)
        results[code] = chan is not None

    # ── 汇总 ──
    print(f"\n{'='*70}")
    print("  汇总")
    print(f"{'='*70}")
    for code, name in TEST_STOCKS:
        status = "OK" if results[code] else "FAIL"
        print(f"  [{status}] {code} {name}")

    success = sum(1 for v in results.values() if v)
    print(f"\n  成功: {success}/{len(TEST_STOCKS)}")


if __name__ == "__main__":
    main()
