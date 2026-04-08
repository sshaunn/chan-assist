"""
中枢补充检测。

补充 chan.py 计算引擎未识别的中枢。
chan.py 的 normal 模式只用线段内反向笔构建中枢，
短线段（3笔）反向笔不足时会遗漏。本模块补充这些遗漏。
"""
from typing import List, Tuple
from strategy.accessor import get_bi_list, get_zs_list


def detect_3bi_overlap(b1, b2, b3) -> Tuple[bool, float, float]:
    """
    检测 3 根连续笔是否有重叠（构成中枢）。
    返回 (是否重叠, max_low, min_high)
    """
    min_high = min(b1._high(), b2._high(), b3._high())
    max_low = max(b1._low(), b2._low(), b3._low())
    return min_high > max_low, max_low, min_high


def detect_missing_zs(chan) -> List[dict]:
    """
    检测 chan.py 未识别但实际存在的中枢。

    算法：从 chan.py 最后一个中枢结束后开始扫描。

    原理：
      - chan.py 在有足够笔数的线段内，中枢检测是可靠的
      - 遗漏主要发生在最近的短线段（只有 3 笔，反向笔不足）
      - 不碰 chan.py 已覆盖的区域，避免重复和冲突

    流程：
      1. 找到 chan.py 最后一个中枢的 end_bi.idx
      2. 从下一笔开始，逐 3 笔检查重叠
      3. 重叠成立 -> 中枢，尝试向后扩展（不过度收窄）
      4. 输出中枢，从末尾下一笔继续
    """
    bi_list = get_bi_list(chan)
    existing_zs = get_zs_list(chan)
    extra = []

    # 扫描起点：chan.py 最后一个中枢 end_bi 之后
    if existing_zs:
        scan_after = existing_zs[-1].end_bi.idx
    else:
        scan_after = -1

    # 找到 bi_list 中的起始 index
    start_i = 0
    for idx, bi in enumerate(bi_list):
        if bi.idx > scan_after:
            start_i = idx
            break
    else:
        return extra

    i = start_i
    while i <= len(bi_list) - 3:
        b1, b2, b3 = bi_list[i], bi_list[i + 1], bi_list[i + 2]
        has_overlap, max_low, min_high = detect_3bi_overlap(b1, b2, b3)

        if not has_overlap:
            i += 1
            continue

        # 中枢成立
        zs_low = max_low
        zs_high = min_high
        init_height = zs_high - zs_low
        zs_start = i
        zs_end = i + 2

        # 向后扩展：新笔与当前区间有重叠，且不过度收窄
        j = i + 3
        while j < len(bi_list):
            next_bi = bi_list[j]
            new_low = max(zs_low, next_bi._low())
            new_high = min(zs_high, next_bi._high())

            if new_low >= new_high:
                break
            if init_height > 0 and (new_high - new_low) < init_height * 0.3:
                break

            zs_low = new_low
            zs_high = new_high
            zs_end = j
            j += 1

        extra.append({
            "bi_start": bi_list[zs_start].idx,
            "bi_end": bi_list[zs_end].idx,
            "low": zs_low,
            "high": zs_high,
            "bi_count": zs_end - zs_start + 1,
            "x_start": bi_list[zs_start].get_begin_klu().idx,
            "x_end": bi_list[zs_end].get_end_klu().idx,
        })

        i = zs_end + 1

    return extra
