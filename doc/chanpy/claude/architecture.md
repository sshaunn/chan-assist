# 全 A 股缠论候选池筛选系统 — 架构设计文档

> 基于 chan.py 公开版代码实际能力 + 目标系统需求的落地设计。
> 生成时间：2026-04-08

---

# 1. 项目目标重新定义

**目标**：构建一个"全 A 股缠论候选池筛选系统"——每日（或盘中）自动扫描全 A 股，按可配置的缠论规则筛选出候选池，并以非技术用户能理解的方式展示结果与原因。

**不是什么**：
- 不是自动交易系统（不下单、不管仓位、不做风控）
- 不是完整回测平台（不计算 PnL、不做绩效归因）
- 不是缠论教学工具（不解释缠论理论本身）
- 不是通用量化平台（只做缠论维度的筛选）

**核心价值**：把"一个人盯盘画图找买点"变成"系统每天自动算完，告诉你今天哪些票符合条件，为什么"。

---

# 2. chan.py 在该系统中的正确定位

## 2.1 适合做什么

chan.py 适合作为**缠论结构计算引擎**——系统的计算核心层。以下能力可以直接复用：

| 能力 | 复用方式 | 对应代码 |
|------|----------|----------|
| K 线合并 + 分型识别 | 直接调用 | `KLine_List.add_single_klu()` |
| 笔识别（多算法） | 直接调用 | `BiList.update_bi()` |
| 线段识别（3 种算法） | 直接调用 | `SegListChan/DYH/Def` |
| 中枢识别与合并 | 直接调用 | `ZSList.cal_bi_zs()` |
| 理论买卖点（6 种） | 直接调用 | `BSPointList.cal()` |
| MACD 背驰判定 | 直接调用 | `ZS.is_divergence()` |
| 多级别递归分析 | 直接调用 | `Chan.load_iterator()` |
| 数据源接入（Akshare） | 直接复用 | `DataAPI/AkshareAPI.py` |
| 批量扫描参考实现 | 参考借鉴 | `App/ashare_bsp_scanner_gui.py` |

## 2.2 不适合做什么

| 能力 | 原因 | 需要自建 |
|------|------|----------|
| 规则引擎 | 公开版无 cbsp，买卖点逻辑硬编码 | 自建规则层 |
| 结果存储 | 无数据库/持久化 | 自建存储层 |
| 调度管理 | 无定时任务 | 自建调度层 |
| 结果解释 | 无自然语言输出 | 自建解释层 + LLM |
| 性能优化 | 单线程串行扫描 | 自建并行/缓存层 |
| 配置管理 | ConfigWithCheck 是运行时的，非持久化 | 自建配置管理 |

## 2.3 应该放在哪一层

```
┌────────────────────────────────────────┐
│  展示 & 交互层（Streamlit / Web）      │  ← 自建
├────────────────────────────────────────┤
│  LLM 解释层                            │  ← 自建
├────────────────────────────────────────┤
│  规则引擎层                            │  ← 自建（核心差异化）
├────────────────────────────────────────┤
│  结构摘要层（chan → 标准化快照）        │  ← 自建（薄适配层）
├────────────────────────────────────────┤
│  缠论计算引擎  ← chan.py 在此          │  ← 直接复用
├────────────────────────────────────────┤
│  数据接入层                            │  ← 部分复用 chan.py DataAPI
├────────────────────────────────────────┤
│  调度 & 存储层                         │  ← 自建
└────────────────────────────────────────┘
```

**chan.py = 黑盒计算引擎**。上层不应直接操作 chan.py 内部对象（CBi、CSeg 等），而是通过一层"结构摘要"转成标准化数据结构后再传给规则引擎。

---

# 3. 系统边界与一句话定义

> **一句话定义**：一个基于缠论结构计算的全 A 股定期筛选系统，支持可插拔规则配置、结构化结果存储、LLM 辅助的自然语言解释。

**边界定义**：

| 在边界内 | 在边界外 |
|----------|----------|
| 全 A 股缠论结构计算 | 实盘下单 |
| 可配置规则筛选 | 仓位管理 |
| 候选池输出与存储 | PnL 回测 |
| 每只股票的入池原因 | 因子研究 |
| 自然语言解释 | 缠论教学 |
| 定时扫描 | 实时盯盘（第二阶段） |
| 日线 + 分钟线多级别 | 高频（Tick 级别） |

---

# 4. 推荐的系统分层架构

## 4.1 总体分层

```
┌─────────────────────────────────────────────────────────────┐
│ 第 8 层：前端展示层                                          │
│ Streamlit UI / API                                          │
├─────────────────────────────────────────────────────────────┤
│ 第 7 层：LLM 解释层                                         │
│ 结构化结果 → 自然语言改写                                    │
├─────────────────────────────────────────────────────────────┤
│ 第 6 层：结果存储层                                          │
│ SQLite (MVP) → PostgreSQL (扩展)                            │
├─────────────────────────────────────────────────────────────┤
│ 第 5 层：扫描调度层                                          │
│ APScheduler / cron + 多进程池                                │
├─────────────────────────────────────────────────────────────┤
│ 第 4 层：规则引擎层                               ← 核心    │
│ Python 插件注册 + AND/OR 组合 + 时间窗口                     │
├─────────────────────────────────────────────────────────────┤
│ 第 3 层：结构摘要层                                          │
│ CChan → ChanSnapshot（标准化 dataclass）                     │
├─────────────────────────────────────────────────────────────┤
│ 第 2 层：缠论计算引擎                                        │
│ chan.py (CChan + CChanConfig)  ← 黑盒复用                    │
├─────────────────────────────────────────────────────────────┤
│ 第 1 层：数据接入层                                          │
│ Akshare + CSV + 可选 Tushare  ← 部分复用 chan.py DataAPI     │
├─────────────────────────────────────────────────────────────┤
│ 第 0 层：配置管理层                                          │
│ YAML 配置 + 规则注册表                                       │
└─────────────────────────────────────────────────────────────┘
```

## 4.2 各层详解

### 第 1 层：数据接入层

| 项目 | 说明 |
|------|------|
| **作用** | 获取全 A 股列表 + 历史/实时 K 线数据 |
| **复用 chan.py** | 部分。`DataAPI/AkshareAPI.py` 可复用，但股票列表获取需额外写（参考 `ashare_bsp_scanner_gui.py:get_tradable_stocks()`） |
| **需要新写** | 股票池管理（过滤 ST/停牌/新股）、数据缓存、多数据源降级 |
| **上下游** | 输出 → 第 2 层（每只股票的 K 线数据） |
| **MVP** | 直接用 Akshare，复用 `get_tradable_stocks()` 逻辑 |

### 第 2 层：缠论计算引擎

| 项目 | 说明 |
|------|------|
| **作用** | 输入 K 线 → 输出完整缠论结构（分型/笔/段/中枢/买卖点） |
| **复用 chan.py** | **完全复用**。`CChan(code, begin_time, ..., config=config)` 一行调用 |
| **需要新写** | 无。只需封装异常处理和超时控制 |
| **上下游** | 输入 ← 第 1 层；输出 → 第 3 层（CChan 对象） |
| **MVP** | 直接实例化 `CChan`，try-except 包一层 |

### 第 3 层：结构摘要层（关键适配层）

| 项目 | 说明 |
|------|------|
| **作用** | 把 CChan 对象转换成标准化 dataclass，解耦上层与 chan.py 内部结构 |
| **复用 chan.py** | 不复用。从 chan.py 对象提取数据，输出自定义数据结构 |
| **需要新写** | `ChanSnapshot` dataclass（下面详细设计） |
| **上下游** | 输入 ← CChan 对象；输出 → 第 4 层（ChanSnapshot） |
| **MVP** | 一个 `extract_snapshot(chan: CChan) -> ChanSnapshot` 函数 |

**为什么需要这层**：
1. 规则引擎不应直接访问 `chan[0].bi_list` 这样的 chan.py 内部 API——如果 chan.py 升级改了内部结构，只需改这层
2. 让规则可以用简单的属性访问判断条件（如 `snapshot.latest_fx_type == "BOTTOM"`），而不需理解 chan.py 链表遍历
3. 摘要可以序列化存储，供后续查询/回溯

### 第 4 层：规则引擎层（核心，下面重点设计）

| 项目 | 说明 |
|------|------|
| **作用** | 对 ChanSnapshot 应用可配置规则，判断是否入池 |
| **复用 chan.py** | 不复用 |
| **需要新写** | 规则注册、规则组合、规则执行器 |
| **上下游** | 输入 ← ChanSnapshot；输出 → 第 6 层（命中结果） |
| **MVP** | Python 装饰器注册 + YAML 组合配置 |

### 第 5 层：扫描调度层

| 项目 | 说明 |
|------|------|
| **作用** | 控制扫描节奏（每日/盘中）、并行计算、进度管理 |
| **复用 chan.py** | 不复用 |
| **需要新写** | 调度器 + 多进程/多线程计算池 |
| **上下游** | 编排第 1-4 层的执行顺序 |
| **MVP** | `ProcessPoolExecutor` + cron 触发 |

### 第 6 层：结果存储层

| 项目 | 说明 |
|------|------|
| **作用** | 持久化每次扫描结果、历史候选池 |
| **复用 chan.py** | 不复用 |
| **需要新写** | SQLite 表设计 + ORM |
| **上下游** | 输入 ← 第 4 层结果；输出 → 第 7/8 层 |
| **MVP** | SQLite + SQLAlchemy / 纯 sqlite3 |

### 第 7 层：LLM 解释层

| 项目 | 说明 |
|------|------|
| **作用** | 把结构化命中结果翻译成人话 |
| **复用 chan.py** | 不复用 |
| **需要新写** | Prompt 模板 + LLM 调用 |
| **上下游** | 输入 ← 第 6 层的结构化数据；输出 → 第 8 层的自然语言文本 |
| **MVP** | Claude/GPT API + 固定 prompt 模板 |

### 第 8 层：前端展示层

| 项目 | 说明 |
|------|------|
| **作用** | 用户查看候选池、筛选、查看详情 |
| **复用 chan.py** | Plot 模块可参考，但建议用更轻量的方案 |
| **需要新写** | Streamlit 页面 |
| **上下游** | 输入 ← 第 6/7 层 |
| **MVP** | Streamlit 单页应用 |

### 第 0 层：配置管理层

| 项目 | 说明 |
|------|------|
| **作用** | 管理 chan.py 计算参数 + 规则配置 + 系统配置 |
| **复用 chan.py** | CChanConfig 直接复用 |
| **需要新写** | YAML 配置加载、规则配置解析 |
| **MVP** | 一个 `config.yaml` 文件 |

---

# 5. 候选池规则引擎设计

这是整个系统的核心差异化部分。

## 5.1 设计原则

1. **规则是纯函数**：输入 `ChanSnapshot` → 输出 `RuleResult`（命中/未命中 + 原因）
2. **规则可独立测试**：每条规则可以单独跑单元测试
3. **规则可组合**：AND / OR / NOT
4. **规则可插拔**：加新规则 = 加一个 Python 文件，不改现有代码
5. **规则与计算分离**：规则不调用 chan.py，只读 ChanSnapshot

## 5.2 第一阶段方案：Python 函数 + 装饰器注册

**理由**：
- 你懂 Python，DSL/JSON 在这个阶段是过度设计
- 规则逻辑复杂（需要访问嵌套数据结构、做数值比较、处理时间窗口），JSON 表达不了
- Python 函数天然支持 IDE 补全、类型检查、断点调试
- 装饰器注册可以自动发现规则，不需要手动维护注册表

### 5.2.1 ChanSnapshot — 结构摘要 dataclass

```python
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime
from enum import Enum

@dataclass
class FxInfo:
    """分型信息"""
    type: str              # "TOP" / "BOTTOM"
    time: datetime         # 分型所在 K 线时间
    price: float           # 分型极值价格
    klc_idx: int           # 合并 K 线索引
    is_sure: bool          # 是否已确认

@dataclass
class BiInfo:
    """笔信息"""
    idx: int
    dir: str               # "UP" / "DOWN"
    begin_time: datetime
    end_time: datetime
    begin_val: float       # 起点价格
    end_val: float         # 终点价格
    amp: float             # 振幅
    is_sure: bool
    macd_area: float       # MACD 面积（用于背驰判断）
    klu_cnt: int           # 包含 K 线数量
    parent_seg_idx: Optional[int]  # 所属线段索引

@dataclass
class SegInfo:
    """线段信息"""
    idx: int
    dir: str               # "UP" / "DOWN"
    begin_time: datetime
    end_time: datetime
    begin_val: float
    end_val: float
    bi_cnt: int            # 包含笔数
    is_sure: bool
    zs_cnt: int            # 内含中枢数

@dataclass
class ZsInfo:
    """中枢信息"""
    low: float             # 中枢下沿
    high: float            # 中枢上沿
    mid: float             # 中枢中轴
    peak_low: float        # 极低
    peak_high: float       # 极高
    begin_time: datetime
    end_time: datetime
    bi_cnt: int            # 涉及笔数
    is_sure: bool

@dataclass
class BspInfo:
    """买卖点信息"""
    types: List[str]       # ["1", "1p", "2", ...] 可能同时属于多种类型
    is_buy: bool
    time: datetime
    price: float
    bi_idx: int
    divergence_rate: Optional[float]  # 背驰率
    is_seg_bsp: bool       # 是否是线段级买卖点

@dataclass
class ChanSnapshot:
    """一次 CChan 计算的标准化快照"""
    # 基础信息
    code: str
    name: str
    last_price: float
    last_time: datetime
    kl_type: str           # 主级别，如 "K_DAY"

    # 分型
    latest_fx: Optional[FxInfo]          # 最新分型
    latest_bottom_fx: Optional[FxInfo]   # 最近底分型
    latest_top_fx: Optional[FxInfo]      # 最近顶分型

    # 笔
    bi_list: List[BiInfo]                # 最近 N 根笔（默认 20）
    latest_bi: Optional[BiInfo]          # 最新笔
    latest_sure_bi: Optional[BiInfo]     # 最新确认笔

    # 线段
    seg_list: List[SegInfo]              # 最近 N 条线段
    latest_seg: Optional[SegInfo]        # 最新线段

    # 中枢
    zs_list: List[ZsInfo]               # 最近 N 个中枢
    latest_zs: Optional[ZsInfo]          # 最新中枢

    # 买卖点
    bsp_list: List[BspInfo]              # 所有买卖点
    latest_buy_bsp: Optional[BspInfo]    # 最近买点
    latest_sell_bsp: Optional[BspInfo]   # 最近卖点

    # 指标摘要
    latest_macd: Optional[float]         # 最新 MACD 柱值
    latest_rsi: Optional[float]          # 最新 RSI
    latest_boll_position: Optional[str]  # "ABOVE_UP" / "IN_BAND" / "BELOW_DOWN"

    # 多级别（如果有）
    sub_level_snapshot: Optional['ChanSnapshot'] = None  # 次级别快照
```

### 5.2.2 规则定义协议

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class RuleResult:
    """单条规则的执行结果"""
    hit: bool                       # 是否命中
    rule_name: str                  # 规则名称
    rule_desc: str                  # 规则描述（人话）
    detail: Optional[str] = None    # 命中细节（如 "日线最近买点类型: 1类, 时间: 2026-04-07"）
    confidence: float = 1.0         # 置信度 0~1（预留，第一阶段全部为 1.0）

# --- 规则注册器 ---
_rule_registry = {}

def rule(name: str, desc: str, category: str = "default"):
    """规则注册装饰器"""
    def decorator(func):
        _rule_registry[name] = {
            "func": func,
            "name": name,
            "desc": desc,
            "category": category,
        }
        func.rule_name = name
        func.rule_desc = desc
        return func
    return decorator

def get_all_rules():
    return _rule_registry

def get_rule(name: str):
    return _rule_registry[name]["func"]
```

### 5.2.3 规则实现示例

```python
# rules/bsp_rules.py

from datetime import datetime, timedelta
from engine.rule_base import rule, RuleResult
from engine.snapshot import ChanSnapshot

@rule(
    name="recent_buy_bsp",
    desc="近 N 天内出现买点",
    category="bsp"
)
def recent_buy_bsp(snapshot: ChanSnapshot, days: int = 3) -> RuleResult:
    """检查近 N 天内是否有买点"""
    if snapshot.latest_buy_bsp is None:
        return RuleResult(hit=False, rule_name="recent_buy_bsp", rule_desc="无买点")

    cutoff = datetime.now() - timedelta(days=days)
    bsp = snapshot.latest_buy_bsp

    if bsp.time >= cutoff:
        return RuleResult(
            hit=True,
            rule_name="recent_buy_bsp",
            rule_desc=f"近{days}天出现买点",
            detail=f"买点类型: {','.join(bsp.types)}, 时间: {bsp.time.strftime('%Y-%m-%d')}, 价格: {bsp.price:.2f}"
        )
    return RuleResult(hit=False, rule_name="recent_buy_bsp", rule_desc=f"近{days}天无买点")


@rule(
    name="recent_bottom_fx",
    desc="近 N 天形成有效底分型",
    category="fx"
)
def recent_bottom_fx(snapshot: ChanSnapshot, days: int = 2) -> RuleResult:
    """检查近 N 天是否形成确认的底分型"""
    fx = snapshot.latest_bottom_fx
    if fx is None:
        return RuleResult(hit=False, rule_name="recent_bottom_fx", rule_desc="无底分型")

    cutoff = datetime.now() - timedelta(days=days)
    if fx.time >= cutoff and fx.is_sure:
        return RuleResult(
            hit=True,
            rule_name="recent_bottom_fx",
            rule_desc=f"近{days}天形成确认底分型",
            detail=f"底分型时间: {fx.time.strftime('%Y-%m-%d')}, 价格: {fx.price:.2f}"
        )
    return RuleResult(hit=False, rule_name="recent_bottom_fx", rule_desc=f"近{days}天无确认底分型")


@rule(
    name="new_bi_formed",
    desc="最近形成新的向上笔",
    category="bi"
)
def new_bi_formed(snapshot: ChanSnapshot, days: int = 3) -> RuleResult:
    """检查近 N 天是否形成了新的向上笔"""
    bi = snapshot.latest_sure_bi
    if bi is None:
        return RuleResult(hit=False, rule_name="new_bi_formed", rule_desc="无确认笔")

    cutoff = datetime.now() - timedelta(days=days)
    if bi.end_time >= cutoff and bi.dir == "UP":
        return RuleResult(
            hit=True,
            rule_name="new_bi_formed",
            rule_desc=f"近{days}天形成新向上笔",
            detail=f"笔方向: UP, 结束: {bi.end_time.strftime('%Y-%m-%d')}, 振幅: {bi.amp:.2f}"
        )
    return RuleResult(hit=False, rule_name="new_bi_formed", rule_desc=f"近{days}天无新向上笔")


@rule(
    name="zs_breakout",
    desc="中枢突破",
    category="zs"
)
def zs_breakout(snapshot: ChanSnapshot) -> RuleResult:
    """检查最新价格是否突破最近中枢上沿"""
    zs = snapshot.latest_zs
    if zs is None:
        return RuleResult(hit=False, rule_name="zs_breakout", rule_desc="无中枢")

    if snapshot.last_price > zs.high:
        return RuleResult(
            hit=True,
            rule_name="zs_breakout",
            rule_desc="价格突破中枢上沿",
            detail=f"当前价: {snapshot.last_price:.2f}, 中枢上沿: {zs.high:.2f}, 突破幅度: {(snapshot.last_price/zs.high - 1)*100:.1f}%"
        )
    return RuleResult(hit=False, rule_name="zs_breakout", rule_desc="未突破中枢")


@rule(
    name="multi_level_resonance",
    desc="多级别共振（日线+次级别同时出现买点信号）",
    category="multi_level"
)
def multi_level_resonance(snapshot: ChanSnapshot, days: int = 3) -> RuleResult:
    """日线级别有买点 + 次级别也有买点"""
    if snapshot.sub_level_snapshot is None:
        return RuleResult(hit=False, rule_name="multi_level_resonance", rule_desc="无次级别数据")

    cutoff = datetime.now() - timedelta(days=days)
    day_bsp = snapshot.latest_buy_bsp
    sub_bsp = snapshot.sub_level_snapshot.latest_buy_bsp

    day_hit = day_bsp is not None and day_bsp.time >= cutoff
    sub_hit = sub_bsp is not None and sub_bsp.time >= cutoff

    if day_hit and sub_hit:
        return RuleResult(
            hit=True,
            rule_name="multi_level_resonance",
            rule_desc=f"日线+次级别近{days}天同时出现买点",
            detail=f"日线买点: {','.join(day_bsp.types)} @ {day_bsp.time.strftime('%Y-%m-%d')}; "
                   f"次级别买点: {','.join(sub_bsp.types)} @ {sub_bsp.time.strftime('%Y-%m-%d %H:%M')}"
        )
    return RuleResult(hit=False, rule_name="multi_level_resonance", rule_desc="未形成多级别共振")
```

### 5.2.4 规则组合

```python
# engine/rule_combiner.py

from dataclasses import dataclass, field
from typing import List, Dict, Any

@dataclass
class RuleRef:
    """一条规则引用（含参数）"""
    name: str
    params: Dict[str, Any] = field(default_factory=dict)

@dataclass
class RuleSet:
    """规则集（可组合）"""
    name: str
    desc: str
    mode: str = "AND"             # "AND" / "OR"
    rules: List[RuleRef] = field(default_factory=list)
    min_hit_count: int = 0        # OR 模式下最少命中几条（0 = 至少 1 条）

# YAML 配置示例 → 解析成 RuleSet
"""
rule_sets:
  - name: "conservative_buy"
    desc: "保守买入候选"
    mode: "AND"
    rules:
      - name: "recent_buy_bsp"
        params: {days: 3}
      - name: "recent_bottom_fx"
        params: {days: 3}

  - name: "aggressive_buy"
    desc: "激进买入候选"
    mode: "OR"
    rules:
      - name: "recent_buy_bsp"
        params: {days: 5}
      - name: "zs_breakout"
      - name: "new_bi_formed"
        params: {days: 3}

  - name: "multi_level_buy"
    desc: "多级别共振买入"
    mode: "AND"
    rules:
      - name: "recent_buy_bsp"
        params: {days: 3}
      - name: "multi_level_resonance"
        params: {days: 3}
"""
```

### 5.2.5 规则执行器

```python
# engine/rule_executor.py

def execute_rule(rule_ref: RuleRef, snapshot: ChanSnapshot) -> RuleResult:
    """执行单条规则"""
    func = get_rule(rule_ref.name)
    return func(snapshot, **rule_ref.params)

def execute_ruleset(ruleset: RuleSet, snapshot: ChanSnapshot) -> ScreeningResult:
    """执行规则集"""
    results = [execute_rule(r, snapshot) for r in ruleset.rules]
    hit_results = [r for r in results if r.hit]

    if ruleset.mode == "AND":
        passed = len(hit_results) == len(results)
    elif ruleset.mode == "OR":
        min_count = ruleset.min_hit_count or 1
        passed = len(hit_results) >= min_count
    else:
        passed = False

    return ScreeningResult(
        code=snapshot.code,
        name=snapshot.name,
        passed=passed,
        ruleset_name=ruleset.name,
        rule_results=results,
        hit_results=hit_results,
        snapshot=snapshot,
    )
```

### 5.2.6 候选池输出数据结构

```python
@dataclass
class ScreeningResult:
    """单只股票的筛选结果"""
    code: str
    name: str
    passed: bool                     # 是否通过
    ruleset_name: str                # 使用的规则集
    rule_results: List[RuleResult]   # 全部规则结果
    hit_results: List[RuleResult]    # 命中的规则
    snapshot: ChanSnapshot           # 原始结构快照
    scan_time: datetime = field(default_factory=datetime.now)

@dataclass
class ScanBatchResult:
    """一次完整扫描的批量结果"""
    scan_id: str                     # 扫描 ID（如 "2026-04-08_close"）
    scan_time: datetime
    total_stocks: int                # 扫描总数
    passed_stocks: int               # 通过数
    failed_stocks: int               # 计算失败数
    ruleset_name: str
    results: List[ScreeningResult]   # 通过的结果列表
    duration_seconds: float          # 耗时
```

## 5.3 扩展性保障

**加新规则**：在 `rules/` 目录新建 `.py` 文件，用 `@rule` 装饰器注册，然后在 YAML 的 `rule_sets` 中引用名字即可。

**不需要改的部分**：
- 规则引擎核心（`rule_executor.py`）
- 扫描调度
- 存储层
- 展示层

**第二阶段可选升级**：
- 支持 `NOT` 组合（排除规则）
- 支持嵌套规则集（RuleSet 内嵌 RuleSet）
- 支持权重评分模式（每条规则有分数，总分达标才通过）

---

# 6. 全 A 股扫描执行流程设计

## 6.1 每日收盘后扫描流程

```
触发（cron 15:30 或手动）
      │
      ▼
步骤 1：获取全 A 股列表
      │  调用 akshare stock_zh_a_spot_em()
      │  过滤 ST/停牌/科创板/北交所/B股
      │  输出：~4000 只股票的 (code, name, price, change%)
      │
      ▼
步骤 2：加载规则集配置
      │  从 config.yaml 读取当前激活的 rule_set
      │  判断需要哪些级别（日线？日线+60分钟？）
      │
      ▼
步骤 3：并行计算缠论结构
      │  ProcessPoolExecutor(max_workers=CPU_COUNT)
      │  每个 worker：
      │    3a. CChan(code, begin_time, data_src=AKSHARE, lv_list=lv_list, config=chan_config)
      │    3b. extract_snapshot(chan) → ChanSnapshot
      │    3c. 返回 (code, ChanSnapshot) 或 (code, Error)
      │
      ▼
步骤 4：规则引擎过滤
      │  对每个 ChanSnapshot 执行 execute_ruleset()
      │  收集 passed=True 的结果
      │
      ▼
步骤 5：结果落库
      │  写入 scan_results 表和 candidate_pool 表
      │  保存结构化的 ScreeningResult
      │
      ▼
步骤 6：LLM 解释（可选/异步）
      │  对 passed 的结果，生成自然语言解释
      │  写入 explanations 表
      │
      ▼
步骤 7：通知（可选）
      │  推送候选池数量/摘要
      │
完成
```

## 6.2 关键设计决策

### 先算结构还是先筛股票？

**先算结构，后筛规则。** 理由：
1. chan.py 的计算是最耗时的部分（每只股票 0.5~2 秒），规则判断几乎不耗时
2. 如果未来规则集变了，不需要重新计算结构——只需重新跑规则
3. 结构快照存下来后，可以事后用新规则重新筛选

### 全量扫描 vs 增量扫描

**第一阶段：全量扫描。** 理由：
1. 全 A 股约 4000 只，8 核并行每只 1 秒 → 约 8 分钟。可接受。
2. 增量扫描需要维护"上次扫描状态"，复杂度高，收益有限
3. 缠论结构可能因历史数据变化而整体重算（笔/段是全局计算的，不是增量追加）

**第二阶段：可选增量优化**：
- 对未变化的股票（今日停牌/无交易），跳过计算
- 缓存上次的 pickle 结果，只增量追加新 K 线（利用 `trigger_load()`）

### 缓存放在哪一层

```
第 1 层（数据）：缓存 K 线数据到本地 CSV/SQLite → 避免重复调 API
第 2 层（计算）：缓存 CChan 的 pickle → 避免重复算（第二阶段）
第 3 层（摘要）：ChanSnapshot 直接存数据库 → 规则重跑不需重新计算
```

**MVP 只做第 3 层**——摘要存库。K 线数据每次从 Akshare 拉（简单可靠）。

### 性能预估

| 环节 | 单股耗时 | 4000 股(8 核) | 优化空间 |
|------|---------|-------------|----------|
| Akshare 拉数据 | 0.3~0.8s | 3~7min | 本地缓存 |
| CChan 计算（日线 365 天） | 0.2~0.5s | 2~4min | pickle 增量 |
| 规则判断 | <1ms | <1s | 无需优化 |
| 落库 | <1ms | <1s | 批量写入 |
| **总计** | | **~10min** | |

### 盘中扫描升级路径

如果未来要从"每日收盘后"升级到"盘中每 N 分钟扫描"：

**需要改的**：
1. 数据源：从 Akshare 历史数据 → Akshare 实时 + 分钟数据
2. 计算模式：从 `CChan()` 一次性加载 → `trigger_load()` 增量推送
3. 调度：从 cron → APScheduler 周期任务
4. 缓存：必须做 CChan pickle 缓存，每次只追加新 K 线

**不需要改的**：
- ChanSnapshot 数据结构
- 规则引擎
- 存储层
- 解释层
- 展示层

---

# 7. 结果存储与数据模型设计

## 7.1 SQLite 表设计（MVP）

### 表 1：scan_batch — 扫描批次

```sql
CREATE TABLE scan_batch (
    id              TEXT PRIMARY KEY,    -- "2026-04-08_close"
    scan_time       DATETIME NOT NULL,
    ruleset_name    TEXT NOT NULL,
    total_stocks    INTEGER,
    passed_count    INTEGER,
    failed_count    INTEGER,
    duration_sec    REAL,
    chan_config_json TEXT,               -- CChanConfig 参数快照（JSON）
    status          TEXT DEFAULT 'completed'  -- running / completed / failed
);
```

### 表 2：candidate_pool — 候选池主表

```sql
CREATE TABLE candidate_pool (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id         TEXT NOT NULL REFERENCES scan_batch(id),
    code            TEXT NOT NULL,       -- 股票代码
    name            TEXT,                -- 股票名称
    last_price      REAL,               -- 最新价
    change_pct      REAL,               -- 涨跌幅

    -- 命中的规则（JSON 数组）
    hit_rules_json  TEXT NOT NULL,       -- [{"name":"recent_buy_bsp","detail":"买点类型:1类..."}]

    -- 关键结构摘要（不依赖 chan.py 对象）
    latest_fx_type  TEXT,               -- "TOP" / "BOTTOM"
    latest_fx_time  DATETIME,
    latest_bi_dir   TEXT,               -- "UP" / "DOWN"
    latest_bi_sure  BOOLEAN,
    latest_seg_dir  TEXT,
    latest_zs_low   REAL,
    latest_zs_high  REAL,
    latest_bsp_type TEXT,               -- "1,2" 买卖点类型
    latest_bsp_time DATETIME,
    latest_bsp_is_buy BOOLEAN,
    latest_macd     REAL,

    -- LLM 解释
    explanation     TEXT,               -- 自然语言解释（异步生成）

    -- 时间
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(scan_id, code)
);
```

### 表 3：scan_errors — 计算失败记录

```sql
CREATE TABLE scan_errors (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id     TEXT NOT NULL REFERENCES scan_batch(id),
    code        TEXT NOT NULL,
    error_type  TEXT,            -- "data_error" / "compute_error" / "timeout"
    error_msg   TEXT,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 表 4：rule_config — 规则配置（可选，第二阶段）

```sql
CREATE TABLE rule_config (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ruleset_name    TEXT NOT NULL,
    ruleset_json    TEXT NOT NULL,       -- 完整 RuleSet 序列化
    is_active       BOOLEAN DEFAULT 1,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

## 7.2 哪些数据适合数据库 vs 文件

| 数据 | 存储方式 | 理由 |
|------|---------|------|
| 候选池结果 | **SQLite** | 需要查询、排序、过滤 |
| 规则命中详情 | **SQLite**（JSON 字段） | 和候选池绑定 |
| LLM 解释文本 | **SQLite** | 和候选池绑定 |
| 完整 ChanSnapshot | **SQLite**（JSON）或 **不存** | MVP 不存（太大），第二阶段可选 |
| CChan pickle 缓存 | **文件**（`cache/{code}.pkl`） | 二进制，大文件，不适合数据库 |
| K 线原始数据缓存 | **文件**（CSV）或 **不缓存** | MVP 不缓存，每次拉新的 |
| 配置文件 | **YAML 文件** | 版本控制友好 |

---

# 8. 非技术用户解释层设计

## 8.1 每个候选项输出的解释字段

```
{
  "headline": "平安银行今日出现日线1类买点",
  "summary": "该股近期经历了一段下跌走势，日线级别在今日形成了底分型并出现1类买点信号，MACD出现背驰迹象，显示下跌动能衰减。",
  "hit_rules": [
    {
      "rule": "近3天出现买点",
      "detail": "买点类型: 1类, 时间: 2026-04-07, 价格: 12.35",
      "plain_text": "日线级别在4月7日12.35元附近出现了1类买点，这通常意味着一段下跌走势可能结束"
    },
    {
      "rule": "形成确认底分型",
      "detail": "底分型时间: 2026-04-06, 价格: 12.20",
      "plain_text": "4月6日在12.20元附近确认形成了底分型（价格的局部低点结构）"
    }
  ],
  "risk_note": "以上为技术结构分析结果，不构成投资建议",
  "structure_summary": "当前处于日线下跌线段末端，最近中枢区间 12.80~13.50"
}
```

## 8.2 缠论术语→人话的翻译映射

这部分**不需要 LLM**，用固定模板即可：

```python
TERM_TRANSLATIONS = {
    "BOTTOM_FX":    "底分型（价格形成了一个局部低点结构）",
    "TOP_FX":       "顶分型（价格形成了一个局部高点结构）",
    "BI_UP":        "向上笔（一段从低到高的走势）",
    "BI_DOWN":      "向下笔（一段从高到低的走势）",
    "SEG_UP":       "向上线段（一段较大级别的上涨趋势）",
    "SEG_DOWN":     "向下线段（一段较大级别的下跌趋势）",
    "ZS":           "中枢（价格反复震荡的核心区间）",
    "ZS_BREAKOUT":  "中枢突破（价格突破了震荡区间的上沿）",
    "BSP_T1":       "1类买点（一段下跌趋势结束，动能衰减的信号）",
    "BSP_T1P":      "1'类买点（类似1类买点，但没有明确的中枢结构）",
    "BSP_T2":       "2类买点（1类买点后的回踩确认，回踩幅度有限）",
    "BSP_T2S":      "2S类买点（在2类买点基础上的再次回踩）",
    "BSP_T3A":      "3类买点A（新趋势中出现中枢后的突破买点）",
    "BSP_T3B":      "3类买点B（旧趋势中最后一个中枢的突破买点）",
    "DIVERGENCE":   "背驰（价格创新低/新高，但动能减弱，趋势可能反转）",
    "MULTI_RESONANCE": "多级别共振（大级别和小级别同时发出买入信号）",
}
```

## 8.3 LLM 的正确使用方式

### LLM 适合做的事

| 任务 | 方式 |
|------|------|
| **润色解释文本** | 输入结构化 JSON → 输出自然语言段落 |
| **回答用户提问** | "为什么这只票入选？" → 从存储的结构化数据组装 context → LLM 回答 |
| **辅助规则配置** | 用户说"我想找底部反转的股票" → LLM 推荐规则组合 |

### LLM 不应该碰的事

| 任务 | 理由 |
|------|------|
| **执行规则判断** | 必须可复现、可审计，LLM 输出不确定 |
| **计算缠论结构** | 这是 chan.py 的活 |
| **直接推荐买入/卖出** | 合规风险 + 不可控 |
| **从 K 线图"看出"信号** | 幻觉风险高 |

### 防止 LLM 胡说八道的策略

1. **结构化输入，模板化输出**：LLM 的 prompt 包含完整的结构化数据，不给自由发挥空间
2. **输出约束**：prompt 明确要求"只基于以下数据描述，不要添加数据中没有的信息"
3. **风险声明强制注入**：LLM 生成的文本末尾硬编码追加"以上为技术分析结果，不构成投资建议"
4. **事实核查**：LLM 生成的文本可以程序化检查是否包含数据中不存在的数字/日期

### 推荐流程

```
规则引擎产出结构化结果（ScreeningResult）
      │
      ▼
模板层：用固定模板生成基础解释（无 LLM）
      │
      ▼
LLM 层（可选/异步）：对基础解释做润色改写
      │
      ▼
合并输出：模板结果 + LLM 润色 + 风险声明
```

**MVP 阶段可以只做模板层**，不接 LLM。模板层已经能产出可读的结果。

---

# 9. 大模型在系统中的正确使用方式

## 9.1 分阶段引入

| 阶段 | LLM 用途 | 优先级 |
|------|---------|--------|
| MVP | **不接 LLM**。模板化解释足够。 | — |
| 第二阶段 | 润色候选池解释文本 | 中 |
| 第二阶段 | 用户问答（"这只票为什么入选"） | 中 |
| 第三阶段 | 自然语言配置规则（"帮我找底部放量的票"） | 低 |

## 9.2 LLM 解释的 Prompt 模板

```python
EXPLANATION_PROMPT = """
你是一个股票技术分析助手。请根据以下结构化数据，用简洁的中文解释为什么该股票被选入候选池。

要求：
1. 只基于下面的数据描述，不要添加数据中没有的信息
2. 避免使用"建议买入"等投资建议性用语
3. 用通俗易懂的语言，必要时简单解释缠论术语
4. 控制在 100 字以内

股票信息：
- 代码：{code}
- 名称：{name}
- 当前价：{price}

命中规则：
{rules_text}

缠论结构摘要：
- 最新分型：{fx_info}
- 最新笔方向：{bi_info}
- 最新线段方向：{seg_info}
- 最近中枢区间：{zs_info}
- 最近买卖点：{bsp_info}

请生成解释：
"""
```

---

# 10. 技术选型建议（MVP 版 / 扩展版）

## 10.1 MVP 版（第一阶段）

| 组件 | 选型 | 理由 |
|------|------|------|
| **Python 版本** | 3.11+ | chan.py 要求 |
| **项目结构** | 单 repo 单包 | 避免过度工程 |
| **后端框架** | **无**（纯 CLI + Streamlit） | MVP 不需要 API 服务 |
| **调度** | **cron + shell 脚本** | 最简单的每日触发 |
| **存储** | **SQLite** | 零配置，单文件 |
| **缓存** | **不做** | 第一阶段不需要 |
| **前端** | **Streamlit** | 快速出页面 |
| **消息队列** | **不需要** | 单机同步够用 |
| **微服务** | **不需要** | 单进程 |
| **容器化** | **不需要** | 本地运行 |
| **异步任务** | **不需要** | ProcessPoolExecutor 够用 |
| **LLM** | **不接入** | 模板解释够用 |

## 10.2 扩展版（第二阶段）

| 组件 | 选型 | 触发条件 |
|------|------|----------|
| **后端框架** | FastAPI | 需要暴露 API 给前端或其他系统时 |
| **调度** | APScheduler | 需要盘中多次扫描时 |
| **存储** | PostgreSQL | 数据量增长 / 需要并发写入时 |
| **缓存** | Redis 或 pickle 文件 | 需要增量计算 / 盘中扫描时 |
| **前端** | React / Vue | Streamlit 无法满足交互需求时 |
| **LLM** | Claude API | 需要自然语言解释时 |
| **容器化** | Docker Compose | 需要部署到服务器时 |
| **异步任务** | Celery + Redis | 需要分布式计算时 |

## 10.3 推荐项目结构（MVP）

```
chan-assist/
├── chan.py/                    # chan.py 源码（git submodule 或直接复制）
├── src/
│   ├── __init__.py
│   ├── config.py              # 配置加载
│   ├── snapshot.py            # ChanSnapshot dataclass + extract_snapshot()
│   ├── engine/
│   │   ├── __init__.py
│   │   ├── rule_base.py       # 规则注册器 + RuleResult
│   │   ├── rule_combiner.py   # RuleSet + 组合逻辑
│   │   └── rule_executor.py   # 执行器
│   ├── rules/
│   │   ├── __init__.py        # 自动导入所有规则文件
│   │   ├── bsp_rules.py       # 买卖点相关规则
│   │   ├── fx_rules.py        # 分型相关规则
│   │   ├── bi_rules.py        # 笔相关规则
│   │   ├── zs_rules.py        # 中枢相关规则
│   │   └── multi_level_rules.py  # 多级别规则
│   ├── scanner/
│   │   ├── __init__.py
│   │   ├── stock_pool.py      # 全 A 股列表获取 + 过滤
│   │   ├── chan_worker.py      # 单只股票的 CChan 计算 + 快照提取
│   │   └── batch_scanner.py   # 批量扫描编排器
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── db.py              # SQLite 连接 + 建表
│   │   └── models.py          # 表操作封装
│   ├── explain/
│   │   ├── __init__.py
│   │   ├── template.py        # 模板化解释（无 LLM）
│   │   └── llm_explain.py     # LLM 润色（第二阶段）
│   └── app/
│       ├── __init__.py
│       └── streamlit_app.py   # Streamlit 页面
├── config/
│   ├── chan_config.yaml        # CChanConfig 参数
│   └── rules.yaml             # 规则集配置
├── scripts/
│   ├── run_scan.py            # 手动/cron 触发扫描
│   └── setup_db.py            # 初始化数据库
├── data/
│   └── chan_assist.db          # SQLite 数据库文件
├── requirements.txt
└── README.md
```

---

# 11. 备选架构方案对比

## 方案 A：单机脚本 + SQLite + Streamlit

```
cron → run_scan.py → chan.py 计算 → 规则引擎 → SQLite
                                                  ↑
                                    Streamlit ─────┘
```

| 维度 | 评分 | 说明 |
|------|------|------|
| 开发复杂度 | **低** | 纯 Python，无额外基础设施 |
| 可维护性 | 中 | 单人维护没问题 |
| 性能 | 中 | 8 核并行 ~10 分钟扫完全 A |
| 适合当前阶段 | **最高** | 两周内可出 MVP |
| 后续扩展 | 中 | SQLite→PostgreSQL 迁移成本低 |

## 方案 B：FastAPI + PostgreSQL + Redis + 前后端分离

```
APScheduler → Celery Workers → chan.py → PostgreSQL
                                              ↑
                  React 前端 ← FastAPI ────────┘
                                   ↓
                              Redis (缓存)
```

| 维度 | 评分 | 说明 |
|------|------|------|
| 开发复杂度 | **高** | 需要前后端、消息队列、ORM |
| 可维护性 | 高 | 标准化工程架构 |
| 性能 | 高 | 分布式可水平扩展 |
| 适合当前阶段 | **低** | 1~2 个月才能出 MVP |
| 后续扩展 | **最高** | 天花板高 |

## 方案 C：单机脚本 + SQLite + Streamlit + LLM 解释

```
cron → run_scan.py → chan.py → 规则引擎 → SQLite
                                            ↑
              Claude API ← 模板层 ──────────┤
                                            ↑
                            Streamlit ──────┘
```

| 维度 | 评分 | 说明 |
|------|------|------|
| 开发复杂度 | **中低** | 比方案 A 多一个 LLM 调用 |
| 可维护性 | 中 | LLM prompt 需要维护 |
| 性能 | 中 | LLM 调用增加延迟（可异步） |
| 适合当前阶段 | 中 | 3~4 周出 MVP |
| 后续扩展 | 中高 | LLM 层独立，可随时换模型 |

## 三方案对比总结

| | 方案 A | 方案 B | 方案 C |
|---|---|---|---|
| 出 MVP 时间 | **~2 周** | ~6 周 | ~3 周 |
| 技术风险 | 低 | 中 | 低 |
| 当前最需要 | **是** | 否 | 第二步 |
| 做完能用 | 能 | 能 | 能 |
| 过度工程 | 否 | **是** | 否 |

---

# 12. 最终推荐方案

**推荐方案 A 起步，第二阶段平滑过渡到方案 C。**

理由：
1. **你现在最需要的是验证"规则引擎 + 缠论计算"的组合是否好用**，而不是搭建基础设施
2. 方案 A 的每一层都可以独立替换——SQLite→PostgreSQL、Streamlit→Web、cron→APScheduler——不存在推倒重来的风险
3. LLM 解释是锦上添花，不是核心功能。先用模板把功能跑通，再接 LLM 润色
4. 方案 B 对一个人做的项目来说是过度工程。除非你确定会有多人协作或生产级部署

---

# 13. 第一阶段实施路线（按优先级排序）

```
优先级 1 ────────────────────────────────────── 周 1
│
├── P1.1：搭建项目骨架
│   ├── 创建项目结构（src/ rules/ config/ scripts/）
│   ├── 配置 chan.py 的 sys.path
│   ├── 写 requirements.txt
│   └── 写 config/chan_config.yaml
│
├── P1.2：实现 ChanSnapshot + extract_snapshot()
│   ├── 定义 ChanSnapshot dataclass
│   ├── 写 extract_snapshot(chan: CChan) → ChanSnapshot
│   └── 用 main.py 的单只股票验证输出
│
├── P1.3：实现规则引擎骨架
│   ├── rule_base.py（@rule 装饰器 + RuleResult）
│   ├── rule_combiner.py（RuleSet + AND/OR）
│   ├── rule_executor.py（执行器）
│   └── 写第一条规则：recent_buy_bsp
│
优先级 2 ────────────────────────────────────── 周 2
│
├── P2.1：实现批量扫描器
│   ├── stock_pool.py（获取全 A 股列表）
│   ├── chan_worker.py（单股计算 + 异常处理）
│   ├── batch_scanner.py（ProcessPoolExecutor 并行）
│   └── run_scan.py（CLI 入口）
│
├── P2.2：实现存储层
│   ├── db.py（SQLite 连接 + 建表）
│   ├── models.py（写入/查询封装）
│   └── 验证：跑一次扫描，结果落库
│
├── P2.3：写 3~5 条规则
│   ├── recent_bottom_fx
│   ├── new_bi_formed
│   ├── zs_breakout
│   └── multi_level_resonance（如果做多级别）
│
优先级 3 ────────────────────────────────────── 周 3
│
├── P3.1：Streamlit 展示页面
│   ├── 候选池列表（表格 + 排序）
│   ├── 单只股票详情（命中规则 + 结构摘要）
│   └── 规则集选择（下拉框切换）
│
├── P3.2：模板化解释层
│   ├── template.py（术语翻译 + 模板生成）
│   └── 在 Streamlit 页面中展示解释
│
├── P3.3：cron 定时任务
│   └── 每日 15:30 自动触发 run_scan.py
│
Done ─── MVP 完成 ──────────────────────────────
```

第一阶段完成后你将拥有：
- 一个每天自动扫描全 A 股的系统
- 可配置的规则引擎（YAML 配置 + Python 插件）
- 结果存 SQLite
- Streamlit 页面查看候选池
- 每个入池股票有模板化的人话解释

---

# 14. 明确不建议现在做的东西

| 不要做 | 理由 |
|--------|------|
| **不要做前后端分离** | Streamlit 能满足至少 3 个月的需求 |
| **不要接 LLM** | 先用模板验证流程，LLM 是第二阶段的事 |
| **不要做增量计算** | 全量扫描 10 分钟，不值得为此引入 pickle 缓存的复杂度 |
| **不要做盘中实时扫描** | 收盘后扫描已经足够开始。盘中是第三阶段 |
| **不要做多级别** | 先把日线单级别跑通，多级别增加数据量和计算时间 |
| **不要做回测** | 这不是回测系统。如果想回测，那是另一个项目 |
| **不要做微服务** | 单进程够用。除非有多人协作需求 |
| **不要做容器化** | 本地跑就行。部署到服务器时再 Docker 化 |
| **不要做 DSL** | Python 函数就是最好的"DSL"。JSON/YAML 规则表达能力不够 |
| **不要自己写数据源** | 先用 Akshare。Tushare/Wind 等以后再说 |
| **不要做权限/多用户** | 单用户系统。多用户是产品化阶段的事 |

---

# 附录 A：从 chan.py 现有代码到本系统的具体衔接点

## extract_snapshot() 的关键取值路径

基于对 chan.py 代码的实际阅读，以下是从 `CChan` 对象提取数据的具体路径：

```python
def extract_snapshot(chan: CChan, code: str, name: str) -> ChanSnapshot:
    kl_list = chan[0]  # CKLine_List，第一级别

    # 最新分型：遍历 kl_list.lst 从后往前找 fx != UNKNOWN 的
    # 最新笔：kl_list.bi_list[-1]（CBi 对象）
    #   → bi.get_begin_val(), bi.get_end_val(), bi.dir, bi.is_sure
    # 最新线段：kl_list.seg_list[-1]（CSeg 对象）
    #   → seg.start_bi, seg.end_bi, seg.dir, seg.zs_lst
    # 最新中枢：kl_list.zs_list[-1]（CZS 对象）
    #   → zs.low, zs.high, zs.begin, zs.end
    # 买卖点：chan.get_latest_bsp(number=0)
    #   → bsp.is_buy, bsp.type, bsp.klu.time, bsp.features
    # MACD：kl_list.lst[-1][-1].macd（CMACD_item 对象）
    #   → macd.macd (柱值), macd.DIF, macd.DEA
    # RSI：kl_list.lst[-1][-1].rsi（float 值，如果 cal_rsi=True）
    ...
```

这个函数是第 3 层（结构摘要层）的核心，需要了解 chan.py 内部数据结构。但上层所有模块（规则引擎、存储、展示）都不需要知道 chan.py 的任何细节。

## 与 ashare_bsp_scanner_gui.py 的关系

现有的 GUI 扫描器（`App/ashare_bsp_scanner_gui.py`）本质上是一个"简化版方案 A"：

```
ashare_bsp_scanner_gui.py:
  get_tradable_stocks()     → 复用为 stock_pool.py
  ScanThread.run()          → 复用扫描逻辑到 batch_scanner.py
  CChan(..., AKSHARE, ...)  → 直接复用
  bsp_list 过滤             → 升级为规则引擎
  GUI 展示                  → 替换为 Streamlit
```

它证明了 chan.py 完全可以支撑全 A 股扫描，但需要把"硬编码的 3 天买卖点过滤"替换为可配置的规则引擎。

---

# 附录 B：风险与不确定性

| 风险 | 应对 |
|------|------|
| Akshare API 不稳定/限速 | 加重试 + 降级到 BaoStock |
| 单只股票 chan.py 计算报错 | try-except 包住，记录到 scan_errors 表 |
| 全量扫描超过 15 分钟 | 减少历史数据天数（365→180）或加核 |
| chan.py 上游更新不兼容 | 锁定版本（git submodule 固定 commit） |
| 规则写错导致大面积误报 | 支持"dry run"模式（只输出不落库） |

---

> 本文档基于 chan.py 公开版代码实际阅读 + 系统架构经验撰写。
> 所有涉及 chan.py 内部 API 的描述均有代码依据，非推测。
> 涉及"第二阶段"/"第三阶段"的部分为建议，需根据实际迭代情况调整。
