"""
Phase M1 单元测试：legacy strategy 迁入模块 — import、纯函数化、统一返回结构。

覆盖要求（含 Codex M1 review 修复项）：
- 模块可 import
- 三条规则是普通函数
- 空结果返回空列表
- 非空结果字段完整且一致（bi_idx / rule_name / reason / extra）
- 统一契约跨规则校验
- _bsp_filters.py 通过 _accessor 访问 chan.py 数据
"""
import inspect
import pytest
from unittest.mock import MagicMock


REQUIRED_FLAGGED_KEYS = {"bi_idx", "rule_name", "reason", "extra"}


class TestModuleImports:
    """各模块可 import"""

    def test_import_accessor(self):
        from strategy import _accessor
        assert _accessor is not None

    def test_import_zs_patch(self):
        from strategy import _zs_patch
        assert _zs_patch is not None

    def test_import_bsp_filters(self):
        from strategy import _bsp_filters
        assert _bsp_filters is not None

    def test_import_bsp_modify(self):
        from strategy import _bsp_modify
        assert _bsp_modify is not None


class TestAccessorFunctions:
    """_accessor.py 函数存在且可调用"""

    def test_get_bi_list_callable(self):
        from strategy._accessor import get_bi_list
        assert callable(get_bi_list)

    def test_get_bsp_list_callable(self):
        from strategy._accessor import get_bsp_list
        assert callable(get_bsp_list)

    def test_get_buy_bsp_list_callable(self):
        from strategy._accessor import get_buy_bsp_list
        assert callable(get_buy_bsp_list)

    def test_bsp_types_callable(self):
        from strategy._accessor import bsp_types
        assert callable(bsp_types)

    def test_find_seg_for_bi_callable(self):
        from strategy._accessor import find_seg_for_bi
        assert callable(find_seg_for_bi)


class TestFiltersArePlainFunctions:
    """三条过滤规则是普通函数，不是装饰器注册的"""

    def test_b2_retrace_check_is_plain_function(self):
        from strategy._bsp_filters import b2_retrace_check
        assert callable(b2_retrace_check)
        assert not hasattr(b2_retrace_check, "rule_name")
        assert not hasattr(b2_retrace_check, "rule_desc")

    def test_b2_in_new_zs_is_plain_function(self):
        from strategy._bsp_filters import b2_in_new_zs
        assert callable(b2_in_new_zs)
        assert not hasattr(b2_in_new_zs, "rule_name")

    def test_b2_must_enter_zs_is_plain_function(self):
        from strategy._bsp_filters import b2_must_enter_zs
        assert callable(b2_must_enter_zs)
        assert not hasattr(b2_must_enter_zs, "rule_name")


class TestFilterReturnStructure:
    """三条规则返回统一 flagged 结构"""

    def _make_chan_no_bsp(self):
        """构造一个没有买卖点的 fake chan"""
        chan = MagicMock()
        chan.__getitem__ = MagicMock(return_value=MagicMock(
            bi_list=[], seg_list=[], zs_list=[],
        ))
        chan.get_latest_bsp.return_value = []
        return chan

    def test_b2_retrace_check_returns_list(self):
        from strategy._bsp_filters import b2_retrace_check
        result = b2_retrace_check(self._make_chan_no_bsp())
        assert isinstance(result, list)

    def test_b2_in_new_zs_returns_list(self):
        from strategy._bsp_filters import b2_in_new_zs
        result = b2_in_new_zs(self._make_chan_no_bsp())
        assert isinstance(result, list)

    def test_b2_must_enter_zs_returns_list(self):
        from strategy._bsp_filters import b2_must_enter_zs
        result = b2_must_enter_zs(self._make_chan_no_bsp())
        assert isinstance(result, list)

    def test_empty_bsp_returns_empty_list(self):
        """无买卖点时应返回空列表"""
        from strategy._bsp_filters import b2_retrace_check, b2_in_new_zs, b2_must_enter_zs
        chan = self._make_chan_no_bsp()
        assert b2_retrace_check(chan) == []
        assert b2_in_new_zs(chan) == []
        assert b2_must_enter_zs(chan) == []


class TestDetectMissingZs:
    """_zs_patch.py detect_missing_zs 基本行为"""

    def test_callable(self):
        from strategy._zs_patch import detect_missing_zs
        assert callable(detect_missing_zs)

    def test_returns_list(self):
        from strategy._zs_patch import detect_missing_zs
        chan = MagicMock()
        chan.__getitem__ = MagicMock(return_value=MagicMock(
            bi_list=[], zs_list=[],
        ))
        chan.get_latest_bsp.return_value = []
        result = detect_missing_zs(chan)
        assert isinstance(result, list)

    def test_empty_bi_list_returns_empty(self):
        from strategy._zs_patch import detect_missing_zs
        chan = MagicMock()
        chan.__getitem__ = MagicMock(return_value=MagicMock(
            bi_list=[], zs_list=[],
        ))
        result = detect_missing_zs(chan)
        assert result == []


# --- Helpers for non-empty flagged tests ---

def _make_bi(idx, low, high, amp_val):
    """构造 fake 笔对象"""
    bi = MagicMock()
    bi.idx = idx
    bi._low.return_value = low
    bi._high.return_value = high
    bi.amp.return_value = amp_val
    bi.get_begin_klu.return_value = MagicMock(idx=idx * 10)
    bi.get_end_klu.return_value = MagicMock(idx=idx * 10 + 5)
    return bi


def _make_bsp_obj(bi, is_buy, types_str_list, relate_bsp1=None):
    """构造 fake BSP 对象"""
    bsp = MagicMock()
    bsp.bi = bi
    bsp.is_buy = is_buy
    bsp.type = [MagicMock(value=t) for t in types_str_list]
    bsp.relate_bsp1 = relate_bsp1
    return bsp


class TestNonEmptyFlaggedOutput:
    """三条规则的非空 flagged 输出 + 统一结构断言（Codex M1 review 修复项）"""

    def test_b2_retrace_check_flags_high_retrace(self):
        """回踩比超过阈值时，b2_retrace_check 应返回非空 flagged"""
        from strategy._bsp_filters import b2_retrace_check

        # 构造：bi[0] 是反弹笔（amp=10），bi[1] 是 b2 回踩笔（amp=8, retrace=80%>60%）
        bi0 = _make_bi(idx=0, low=10, high=20, amp_val=10)
        bi1 = _make_bi(idx=1, low=12, high=20, amp_val=8)
        bsp = _make_bsp_obj(bi1, is_buy=True, types_str_list=["2"])

        chan = MagicMock()
        chan.__getitem__ = MagicMock(return_value=MagicMock(
            bi_list=[bi0, bi1], seg_list=[], zs_list=[],
        ))
        chan.get_latest_bsp.return_value = [bsp]

        result = b2_retrace_check(chan, max_rate=0.6)
        assert len(result) >= 1
        item = result[0]
        # 统一结构断言
        assert set(item.keys()) == REQUIRED_FLAGGED_KEYS
        assert isinstance(item["bi_idx"], int)
        assert isinstance(item["rule_name"], str)
        assert item["rule_name"] == "b2_retrace_check"
        assert isinstance(item["reason"], str)
        assert len(item["reason"]) > 0
        assert item["extra"] is None or isinstance(item["extra"], dict)

    def test_b2_in_new_zs_flags_oscillation(self):
        """b2 落在 b1 附近震荡中枢时，b2_in_new_zs 应返回非空 flagged"""
        from strategy._bsp_filters import b2_in_new_zs

        # 构造 3 根笔形成重叠（中枢），b1 在笔0，b2 在笔2
        bi0 = _make_bi(idx=0, low=10, high=15, amp_val=5)
        bi1 = _make_bi(idx=1, low=11, high=16, amp_val=5)
        bi2 = _make_bi(idx=2, low=10.5, high=14, amp_val=3.5)

        b1_bsp = _make_bsp_obj(bi0, is_buy=True, types_str_list=["1"])
        b2_bsp = _make_bsp_obj(bi2, is_buy=True, types_str_list=["2"], relate_bsp1=b1_bsp)

        chan = MagicMock()
        chan.__getitem__ = MagicMock(return_value=MagicMock(
            bi_list=[bi0, bi1, bi2], seg_list=[], zs_list=[],
        ))
        chan.get_latest_bsp.return_value = [b1_bsp, b2_bsp]

        result = b2_in_new_zs(chan)
        assert len(result) >= 1
        item = result[0]
        assert set(item.keys()) == REQUIRED_FLAGGED_KEYS
        assert isinstance(item["bi_idx"], int)
        assert item["rule_name"] == "b2_in_new_zs"
        assert isinstance(item["reason"], str)

    def test_b2_must_enter_zs_flags_invalid_position(self):
        """b2 回踩位置不在有效区间时，b2_must_enter_zs 应返回非空 flagged"""
        from strategy._bsp_filters import b2_must_enter_zs

        # 构造：b1 在笔0，b2 在笔2，b2 低点远高于中枢上沿
        bi0 = _make_bi(idx=0, low=10, high=15, amp_val=5)
        bi1 = _make_bi(idx=1, low=11, high=16, amp_val=5)
        bi2 = _make_bi(idx=2, low=20, high=25, amp_val=5)  # b2 低点=20，远高于中枢

        # 构造一个旧中枢（chan.py 识别的），区间 [10, 14]
        fake_zs = MagicMock()
        fake_zs.low = 10
        fake_zs.high = 14
        fake_zs.mid = 12

        # 构造线段，包含该中枢
        fake_seg = MagicMock()
        fake_seg.start_bi = MagicMock(idx=0)
        fake_seg.end_bi = MagicMock(idx=2)
        fake_seg.zs_lst = [fake_zs]

        b1_bsp = _make_bsp_obj(bi0, is_buy=True, types_str_list=["1"])
        b2_bsp = _make_bsp_obj(bi2, is_buy=True, types_str_list=["2"], relate_bsp1=b1_bsp)

        chan = MagicMock()
        chan.__getitem__ = MagicMock(return_value=MagicMock(
            bi_list=[bi0, bi1, bi2],
            seg_list=[fake_seg],
            zs_list=[],
        ))
        chan.get_latest_bsp.return_value = [b1_bsp, b2_bsp]

        result = b2_must_enter_zs(chan)
        assert len(result) >= 1
        item = result[0]
        assert set(item.keys()) == REQUIRED_FLAGGED_KEYS
        assert isinstance(item["bi_idx"], int)
        assert item["rule_name"] == "b2_must_enter_zs"
        assert isinstance(item["reason"], str)
        assert isinstance(item["extra"], dict)


class TestUnifiedFlaggedContract:
    """跨三条规则的统一契约测试：防止后续某条规则返回对象或字段漂移"""

    def test_all_rules_return_same_key_set(self):
        """三条规则非空结果必须包含完全相同的 key 集合"""
        from strategy._bsp_filters import b2_retrace_check, b2_in_new_zs, b2_must_enter_zs

        # 复用上面的 fake 数据触发每条规则
        # b2_retrace_check
        bi0 = _make_bi(0, 10, 20, 10)
        bi1 = _make_bi(1, 12, 20, 8)
        bsp_retrace = _make_bsp_obj(bi1, True, ["2"])
        chan_retrace = MagicMock()
        chan_retrace.__getitem__ = MagicMock(return_value=MagicMock(
            bi_list=[bi0, bi1], seg_list=[], zs_list=[]))
        chan_retrace.get_latest_bsp.return_value = [bsp_retrace]
        r1 = b2_retrace_check(chan_retrace, max_rate=0.6)

        # b2_in_new_zs
        bi_a = _make_bi(0, 10, 15, 5)
        bi_b = _make_bi(1, 11, 16, 5)
        bi_c = _make_bi(2, 10.5, 14, 3.5)
        b1 = _make_bsp_obj(bi_a, True, ["1"])
        b2 = _make_bsp_obj(bi_c, True, ["2"], relate_bsp1=b1)
        chan_zs = MagicMock()
        chan_zs.__getitem__ = MagicMock(return_value=MagicMock(
            bi_list=[bi_a, bi_b, bi_c], seg_list=[], zs_list=[]))
        chan_zs.get_latest_bsp.return_value = [b1, b2]
        r2 = b2_in_new_zs(chan_zs)

        # b2_must_enter_zs
        bi_x = _make_bi(0, 10, 15, 5)
        bi_y = _make_bi(1, 11, 16, 5)
        bi_z = _make_bi(2, 20, 25, 5)
        fake_zs = MagicMock(low=10, high=14, mid=12)
        fake_seg = MagicMock(start_bi=MagicMock(idx=0), end_bi=MagicMock(idx=2), zs_lst=[fake_zs])
        b1_e = _make_bsp_obj(bi_x, True, ["1"])
        b2_e = _make_bsp_obj(bi_z, True, ["2"], relate_bsp1=b1_e)
        chan_enter = MagicMock()
        chan_enter.__getitem__ = MagicMock(return_value=MagicMock(
            bi_list=[bi_x, bi_y, bi_z], seg_list=[fake_seg], zs_list=[]))
        chan_enter.get_latest_bsp.return_value = [b1_e, b2_e]
        r3 = b2_must_enter_zs(chan_enter)

        # 全部非空
        assert len(r1) >= 1, "b2_retrace_check should flag"
        assert len(r2) >= 1, "b2_in_new_zs should flag"
        assert len(r3) >= 1, "b2_must_enter_zs should flag"

        # key 集合完全一致
        for items, name in [(r1, "retrace"), (r2, "in_new_zs"), (r3, "must_enter")]:
            for item in items:
                assert set(item.keys()) == REQUIRED_FLAGGED_KEYS, \
                    f"{name} returned keys {set(item.keys())} != {REQUIRED_FLAGGED_KEYS}"
                assert isinstance(item["bi_idx"], int)
                assert isinstance(item["rule_name"], str)
                assert isinstance(item["reason"], str)
                assert item["extra"] is None or isinstance(item["extra"], dict)


class TestAccessorConvergence:
    """_bsp_filters.py 必须通过 _accessor 访问 chan.py 数据（Codex M1 review 修复项）"""

    def test_bsp_filters_no_direct_chan_access(self):
        """_bsp_filters.py 中不得直接访问 chan[0].seg_list / chan[0].bi_list 等"""
        source = inspect.getsource(__import__("strategy._bsp_filters", fromlist=["_bsp_filters"]))
        # 不应出现 chan[0]. 的直接访问
        assert "chan[0]." not in source, \
            "_bsp_filters.py 仍有直接 chan[0].xxx 访问，应通过 _accessor"

    def test_accessor_get_seg_list_used(self):
        """_bsp_filters.py 应导入并使用 get_seg_list"""
        from strategy._bsp_filters import get_seg_list
        assert callable(get_seg_list)
