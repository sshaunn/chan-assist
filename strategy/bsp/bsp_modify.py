"""
买卖点修改器。

对 chan.py 计算完成后的内存对象做买卖点增删。
只修改内存，不修改源代码。用于画图前清理或规则过滤后更新。
"""
from typing import List, Dict, Optional, Set

# 延迟导入 BSP_TYPE，避免在模块加载时就依赖 chan.py 的 sys.path
_BSP_TYPE = None


def _get_bsp_type():
    global _BSP_TYPE
    if _BSP_TYPE is None:
        from Common.CEnum import BSP_TYPE
        _BSP_TYPE = BSP_TYPE
    return _BSP_TYPE


def remove_bsp_from_chan(chan, bi_indices_to_remove: Set[int], types_to_remove: Optional[List[str]] = None):
    """
    从 CChan 内存对象中删除指定笔上的买卖点。

    参数:
        chan: CChan 对象
        bi_indices_to_remove: 要删除的笔 idx 集合
        types_to_remove: 只删除这些类型，None = 只删 b2/b2s 保留其他类型

    注意: 这只修改内存对象，不修改源代码。
    """
    BSP_TYPE = _get_bsp_type()

    if types_to_remove is None:
        types_to_remove = ["2", "2s"]

    types_enum = {BSP_TYPE(t) for t in types_to_remove}
    kl = chan[0]
    bsp_store = kl.bs_point_lst.bsp_store_dict
    bsp_flat = kl.bs_point_lst.bsp_store_flat_dict

    removed = []

    for bi_idx in bi_indices_to_remove:
        bsp = bsp_flat.get(bi_idx)
        if bsp is None:
            continue

        types_on_bsp = set(bsp.type)
        to_remove = types_on_bsp & types_enum
        to_keep = types_on_bsp - types_enum

        if not to_remove:
            continue

        if to_keep:
            # 还有其他类型保留（比如同时标了 b2+b3b，只删 b2 保留 b3b）
            bsp.type = list(to_keep)
            # 从被删类型的 store 中移除
            for bt in to_remove:
                if bt in bsp_store:
                    # bsp_store[bt] 是 tuple: (sell_list, buy_list)
                    # bt[True]=bt[1]=buy_list, bt[False]=bt[0]=sell_list
                    buy_list = bsp_store[bt][True]
                    filtered_buy = [b for b in buy_list if b.bi.idx != bi_idx]
                    buy_list.clear()
                    buy_list.extend(filtered_buy)
            # 把 bsp 加到保留类型的 store 中
            for bt in to_keep:
                if bt not in bsp_store:
                    bsp_store[bt] = ([], [])
                existing = bsp_store[bt][bsp.is_buy]
                if not any(b.bi.idx == bi_idx for b in existing):
                    existing.append(bsp)
            removed.append({"bi_idx": bi_idx, "removed_types": [t.value for t in to_remove],
                            "kept_types": [t.value for t in to_keep]})
        else:
            # 全部类型都要删
            bsp.bi.bsp = None
            for bt in to_remove:
                if bt in bsp_store:
                    buy_list = bsp_store[bt][True]
                    filtered_buy = [b for b in buy_list if b.bi.idx != bi_idx]
                    buy_list.clear()
                    buy_list.extend(filtered_buy)
            if bi_idx in bsp_flat:
                del bsp_flat[bi_idx]
            removed.append({"bi_idx": bi_idx, "removed_types": [t.value for t in to_remove],
                            "kept_types": []})

    return removed
