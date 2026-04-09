"""
CChan 数据访问器。

只读访问 chan.py 的 CChan 对象，提供统一的数据提取接口。
所有策略模块通过这里访问 chan.py 数据，不直接操作内部对象。
如果 chan.py 升级改了内部结构，只需改这个文件。
"""
from typing import List, Optional


def get_bi_list(chan) -> list:
    """获取第一级别的所有笔"""
    return list(chan[0].bi_list)


def get_seg_list(chan) -> list:
    """获取第一级别的所有线段"""
    return list(chan[0].seg_list)


def get_zs_list(chan) -> list:
    """获取第一级别的所有中枢"""
    return list(chan[0].zs_list)


def get_bsp_list(chan, number: int = 0) -> list:
    """获取买卖点列表（默认全部，按时间倒序）"""
    return chan.get_latest_bsp(number=number)


def get_buy_bsp_list(chan, number: int = 0) -> list:
    """只获取买点"""
    return [b for b in get_bsp_list(chan, number) if b.is_buy]


def get_sell_bsp_list(chan, number: int = 0) -> list:
    """只获取卖点"""
    return [b for b in get_bsp_list(chan, number) if not b.is_buy]


def bi_time_str(bi) -> str:
    """笔的结束时间字符串"""
    t = bi.get_end_klu().time
    return f"{t.year}-{t.month:02d}-{t.day:02d}"


def bi_date_int(bi) -> int:
    """笔的结束日期整数 如 20260407"""
    t = bi.get_end_klu().time
    return t.year * 10000 + t.month * 100 + t.day


def bsp_types(bsp) -> List[str]:
    """买卖点的类型列表 如 ['1', '2', '3b']"""
    return [t.value for t in bsp.type]


def find_seg_for_bi(seg_list, bi) -> Optional[object]:
    """找到笔所属的线段"""
    for seg in seg_list:
        if seg.start_bi.idx <= bi.idx <= seg.end_bi.idx:
            return seg
    return None


def find_zs_for_seg(seg) -> list:
    """获取线段内的中枢列表"""
    return list(seg.zs_lst) if seg else []
