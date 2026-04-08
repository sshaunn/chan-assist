# chan.py 项目深度解读报告

> 基于完整代码阅读的分析报告，非 README 复述。
> 公开版总代码量：约 7562 行 Python（含 GUI 732 行、绘图 887 行）。
> 完整版据 README 约 22000 行，公开版约 5300 行核心计算代码。

---

# 1. 项目一句话定义

chan.py 是一个**将缠论从主观画图变成可编程计算的 Python 引擎**——它把分型、笔、线段、中枢、买卖点这套缠论体系，实现为一个配置驱动、多级别递归、支持增量计算的结构化分析框架。

它**不是**一个完整的量化交易平台，而是一个**缠论计算引擎 + 可视化工具**，公开版不含策略回测、交易执行、模型训练等上层模块。

---

# 2. 项目核心用途

## 2.1 它能做什么（基于代码实际能力）

| 能力 | 成熟度 | 代码位置 |
|------|--------|----------|
| K 线数据接入（A 股/加密/CSV） | 成熟 | `DataAPI/` |
| K 线合并（包含关系处理） | 成熟 | `Combiner/KLine_Combiner.py` |
| 分型识别（顶底分型） | 成熟 | `Combiner/KLine_Combiner.py:update_fx()` |
| 笔的识别（多算法） | 成熟 | `Bi/BiList.py` |
| 线段的识别（3 种算法） | 成熟 | `Seg/SegListChan.py`, `SegListDYH.py`, `SegListDef.py` |
| 中枢的识别与合并 | 成熟 | `ZS/ZSList.py`, `ZS/ZS.py` |
| 理论买卖点识别（1/2/3 类） | 成熟 | `BuySellPoint/BSPointList.py` |
| MACD 背驰判定 | 成熟 | `Bi/Bi.py:cal_macd_metric()`, `ZS/ZS.py:is_divergence()` |
| 多级别 K 线递归分析 | 成熟 | `Chan.py:load_iterator()` |
| 增量/实时计算模式 | 成熟 | `Chan.py:trigger_load()`, `step_load()` |
| Plotly/Matplotlib 可视化 | 成熟 | `Plot/PlotDriver.py`（887 行） |
| A 股批量扫描 GUI | 可用 | `App/ashare_bsp_scanner_gui.py`（732 行） |
| 技术指标（MACD/BOLL/RSI/KDJ/Demark） | 成熟 | `Math/` |
| 特征提取接口（CFeatures） | 骨架 | `ChanModel/Features.py`（18 行） |
| 策略回测 Demo | 示例级 | `Debug/strategy_demo.py` |

## 2.2 它不能做什么（公开版缺失）

以下模块在 README 中提及，但**代码中不存在**：

| 缺失模块 | README 描述 |
|----------|-------------|
| `CustomBuySellPoint/` | 自定义策略买卖点（cbsp） |
| `ModelStrategy/` | 模型策略框架 |
| `Trade/` | 交易引擎/执行层 |
| `OfflineData/` | 离线数据管理 |
| `Config/` | 配置管理（独立模块） |
| AutoML 框架 | 自动化特征+模型搜索 |
| 交易后端数据库 | 信号存储/监控 |

**结论：公开版是"缠论计算引擎"，不是"缠论量化平台"。**

---

# 3. 这个项目解决了缠论里的哪些问题

## 3.1 程序化了哪些缠论概念

| 缠论概念 | 是否实现 | 实现方式 | 关键代码 |
|----------|---------|----------|----------|
| **K 线包含关系** | 完整 | 方向感知的合并算法，UP 取高高、DOWN 取低低 | `KLine_Combiner.py:try_add()` |
| **顶底分型** | 完整 | 3 根合并 K 线的高低比较，支持 4 种严格度 | `KLine_Combiner.py:update_fx()` |
| **笔** | 完整 | 顶底分型连接 + 间距验证 + 峰值约束 | `BiList.py:can_make_bi()` |
| **线段** | 完整 | 3 种可选算法（chan 特征序列 / DYH 1+1 / break 定义法） | `Seg/SegListChan.py` 等 |
| **特征序列** | 完整 | CEigen + CEigenFX 三元素分型序列验证器 | `Seg/Eigen.py`, `EigenFX.py` |
| **中枢** | 完整 | 笔的重叠区间计算 + 可选合并 | `ZS/ZSList.py:try_construct_zs()` |
| **背驰** | 完整 | MACD 指标多算法对比（面积/峰值/斜率等 12 种） | `ZS/ZS.py:is_divergence()` |
| **买卖点 1 类** | 完整 | 中枢出段 + MACD 背驰 | `BSPointList.py:treat_bsp1()` |
| **买卖点 1' 类** | 完整 | 无中枢时的价格形态背驰 | `BSPointList.py:treat_pz_bsp1()` |
| **买卖点 2 类** | 完整 | BSP1 后回抽幅度判定 | `BSPointList.py:treat_bsp2()` |
| **买卖点 2S 类** | 完整 | 二次回抽延续 | `BSPointList.py:treat_bsp2s()` |
| **买卖点 3A 类** | 完整 | BSP1 后新中枢出段 | `BSPointList.py:treat_bsp3_after()` |
| **买卖点 3B 类** | 完整 | BSP1 前最后中枢区间突破 | `BSPointList.py:treat_bsp3_before()` |
| **多级别联立** | 完整 | 递归 `load_iterator()` + 父子 K 线关联 | `Chan.py:load_iterator()` |
| **区间套** | 仅 README | 公开版代码中无 cbsp 实现 | 缺失 |
| **走势类型分类** | 不完整 | 段有方向，但无"盘整/趋势"显式分类 | — |

## 3.2 解决的实际难点

### 难点 1：缠论结构定义太主观
- **解决方式**：参数化 + 多算法。笔有 `bi_algo`（normal/advance）、`bi_fx_check`（4 种严格度）、`bi_strict`（间距标准）；线段有 3 种算法（chan/1+1/break）。
- **效果**：同一段 K 线可以用不同参数组合得到不同结果，把"主观判断"变成"参数选择"。

### 难点 2：多级别分析难以自动化
- **解决方式**：`Chan.py:load_iterator()` 用递归深度优先遍历，自动处理日线→60 分钟→15 分钟的父子对齐。
- **效果**：只需指定 `lv_list=[K_DAY, K_60M]`，引擎自动完成多级别嵌套计算。

### 难点 3：背驰判定没有标准
- **解决方式**：`MACD_ALGO` 枚举提供 12 种量化方式（AREA/PEAK/FULL_AREA/DIFF/SLOPE/AMP/VOLUME 等），通过 `divergence_rate` 阈值控制。
- **效果**：背驰从"看一眼 MACD 柱线"变成"指标比值是否低于阈值"。

### 难点 4：无法批量扫描
- **解决方式**：`App/ashare_bsp_scanner_gui.py` 实现了多线程全 A 股扫描 + PyQt6 GUI。
- **效果**：一键扫描全市场，筛选最近 3 天有买卖点信号的股票。

### 难点 5：实时增量计算
- **解决方式**：`trigger_load()` 和 `step_load()` 两种增量模式，支持逐根 K 线推送。
- **效果**：可以对接实时数据源，每来一根 K 线就更新全部结构。

## 3.3 它要把缠论从什么变成什么

**从**：一个人盯着 K 线图凭经验画笔、画段、标中枢、判断背驰的手工分析方法

**变成**：一个"输入 K 线序列 → 输出结构化的笔/段/中枢/买卖点对象"的计算引擎，可以批量运行、参数调优、接入可视化和（私有版的）机器学习。

---

# 4. 项目整体架构

## 4.1 分层结构

```
┌─────────────────────────────────────────────────────────┐
│  应用层                                                  │
│  App/ashare_bsp_scanner_gui.py  Debug/strategy_demo*.py │
├─────────────────────────────────────────────────────────┤
│  可视化层                                                │
│  Plot/PlotDriver.py   Plot/PlotMeta.py                  │
├─────────────────────────────────────────────────────────┤
│  信号层                                                  │
│  BuySellPoint/BSPointList.py  (bsp 理论买卖点)           │
│  [缺失] CustomBuySellPoint/   (cbsp 策略买卖点)          │
├─────────────────────────────────────────────────────────┤
│  结构分析层                                              │
│  ZS/ZSList.py          (中枢识别与合并)                   │
│  Seg/SegList*.py       (线段识别，3 种算法)               │
│  Bi/BiList.py          (笔识别)                          │
│  Combiner/             (K 线合并 + 分型识别)              │
├─────────────────────────────────────────────────────────┤
│  数据层                                                  │
│  KLine/KLine_List.py   (K 线管理 + 全流程串联)            │
│  KLine/KLine_Unit.py   (原始 K 线单元)                   │
│  DataAPI/*.py          (数据源适配器)                     │
├─────────────────────────────────────────────────────────┤
│  技术指标层                                              │
│  Math/MACD.py  BOLL.py  RSI.py  KDJ.py  Demark.py      │
├─────────────────────────────────────────────────────────┤
│  基础设施层                                              │
│  Common/CEnum.py  CTime.py  ChanException.py            │
│  Common/func_util.py  cache.py                           │
├─────────────────────────────────────────────────────────┤
│  编排层                                                  │
│  Chan.py (CChan)       — 总调度器                        │
│  ChanConfig.py         — 全局配置容器                    │
└─────────────────────────────────────────────────────────┘
```

## 4.2 数据流总览

```
外部数据源 (BaoStock/Akshare/CCXT/CSV)
     │
     ▼
 CCommonStockApi.get_kl_data()  →  Iterable[CKLine_Unit]
     │
     ▼
 CChan.load_iterator()  递归处理多级别
     │
     ├── KLine_List.add_single_klu(klu)
     │       │
     │       ├── 1. 设置技术指标 (MACD/RSI/KDJ/BOLL)
     │       ├── 2. K 线合并 (包含关系处理)
     │       ├── 3. 分型识别 (顶/底)
     │       ├── 4. 更新笔 (BiList.update_bi)
     │       └── 5. [增量模式] 计算线段+中枢+买卖点
     │
     ├── 设置父子 K 线关联 (set_klu_parent_relation)
     │
     └── 递归进入下一级别 (load_iterator(lv_idx+1))
     │
     ▼
 CChan.cal_seg_and_zs()  [批量模式最终调用]
     │
     ├── 计算线段 (cal_seg)
     ├── 计算中枢 (zs_list.cal_bi_zs)
     ├── 中枢关联到线段 (update_zs_in_seg)
     ├── 递归: 线段的线段 (segseg)
     ├── 线段级买卖点 (seg_bs_point_lst.cal)
     └── 笔级买卖点 (bs_point_lst.cal)
     │
     ▼
 结果访问：chan[0].bi_list / seg_list / zs_list / bs_point_lst
     │
     ▼
 可视化：CPlotDriver(chan) 或 信号提取：chan.get_latest_bsp()
```

---

# 5. 核心模块逐个解析

## 5.1 KLine 模块 — K 线数据结构层

**职责**：管理原始 K 线和合并 K 线，是整个分析链的起点。

| 文件 | 行数 | 核心类 | 职责 |
|------|------|--------|------|
| `KLine_Unit.py` | 154 | `CKLine_Unit` | 单根原始 K 线（OHLCV + 技术指标 + 父子关系） |
| `KLine.py` | 97 | `CKLine` | 合并后的 K 线（继承 `CKLine_Combiner[CKLine_Unit]`），带分型标记 |
| `KLine_List.py` | 204 | `CKLine_List` | K 线列表管理器，串联合并→分型→笔→段→中枢→买卖点全流程 |
| `TradeInfo.py` | 13 | `CTradeInfo` | 成交量/成交额等交易指标容器 |

**关键数据结构关系**：
```
CKLine_Unit (原始 K 线，一根蜡烛)
  ├── time: CTime
  ├── open, high, low, close: float
  ├── trade_info: CTradeInfo (量价信息)
  ├── sub_kl_list: List[CKLine_Unit]  (下级 K 线，如日线包含的 60 分钟线)
  ├── sup_kl: CKLine_Unit  (上级 K 线)
  ├── macd/boll/rsi/kdj/demark  (技术指标值)
  └── pre/next: 链表指针

CKLine (合并 K 线，可能包含多根原始 K 线)
  ├── lst: List[CKLine_Unit]  (被合并的原始 K 线)
  ├── dir: KLINE_DIR  (合并方向: UP/DOWN)
  ├── fx: FX_TYPE  (分型: TOP/BOTTOM/UNKNOWN)
  ├── high, low  (合并后的极值)
  └── pre/next: 链表指针
```

**核心算法 — K 线合并**（`Combiner/KLine_Combiner.py:try_add()`）：

```
当前 K 线 vs 新 K 线:
  - 当前包含新的 (cur.high >= new.high && cur.low <= new.low) → COMBINE，吞入
  - 新的包含当前 (反过来) → COMBINE 或 INCLUDED
  - 新高新低 → UP
  - 新低新低 → DOWN

合并时按方向调整:
  - UP 方向: high = max(两者), low = max(两者)  ← 两端同时抬升
  - DOWN 方向: high = min(两者), low = min(两者)  ← 两端同时下移
```

**核心算法 — 分型识别**（`KLine_Combiner.py:update_fx()`）：

```
顶分型: prev.high < self.high > next.high 且 prev.low < self.low > next.low
底分型: prev.high > self.high < next.high 且 prev.low > self.low < next.low
```

支持 4 种验证严格度（`FX_CHECK_METHOD`）：STRICT / HALF / LOSS / TOTALLY。

**CKLine_List 是流程枢纽**（`KLine_List.py:add_single_klu()` 和 `cal_seg_and_zs()`）：

每添加一根 K 线，依次触发：设置指标 → 合并 → 分型 → 更新笔 → （增量模式下）计算线段/中枢/买卖点。整个分析 pipeline 藏在这一个类里。

---

## 5.2 Combiner 模块 — 通用合并器

**职责**：提供泛型合并逻辑，被 K 线、笔、线段复用。

| 文件 | 行数 | 核心类 | 职责 |
|------|------|--------|------|
| `KLine_Combiner.py` | 171 | `CKLine_Combiner[T]` | 泛型合并器，处理包含关系和分型检测 |
| `Combine_Item.py` | 25 | `CCombine_Item` | 适配器，把不同类型（KLine_Unit/Bi/Seg）统一成 high/low 接口 |

**设计亮点**：用泛型实现了"一套合并逻辑，三处复用"——K 线合并用 `CKLine_Combiner[CKLine_Unit]`，特征序列用 `CKLine_Combiner[CBi]`。

---

## 5.3 Bi 模块 — 笔识别

**职责**：从分型序列中识别笔（连接相邻顶底分型的最小趋势单元）。

| 文件 | 行数 | 核心类 | 职责 |
|------|------|--------|------|
| `Bi.py` | 326 | `CBi` | 单根笔（方向/起止/是否确认/MACD 指标） |
| `BiList.py` | 235 | `CBiList` | 笔列表管理（创建/验证/虚拟笔/峰值更新） |
| `BiConfig.py` | 30 | `CBiConfig` | 笔算法配置 |

**笔的验证规则**（`BiList.py:can_make_bi()`）：
1. **间距验证**：`satisfy_bi_span()` — 严格模式要 4 根合并 K 线，非严格模式 3 根 + 3 根原始 K 线
2. **分型验证**：`check_fx_valid()` — 顶分型的高点必须高于底分型的高点
3. **峰值约束**：`end_is_peak()` — 笔的终点必须是区间极值（可关闭）
4. **方向约束**：UP 笔从底到顶，DOWN 笔从顶到底

**虚拟笔机制**（关键设计）：
- 最后一笔可能是"虚拟的"（`is_sure=False`），表示还未确认
- 新 K 线进来可能更新虚拟笔的终点（`update_virtual_end()`）
- 也可能完全删除虚拟笔回退到前一笔（`delete_virtual_bi()`）
- 这是支持实时增量计算的基础

**MACD 指标算法**（`Bi.py:cal_macd_metric()`，12 种）：
- AREA：起点到峰值的 MACD 面积
- FULL_AREA：整根笔的 MACD 面积
- PEAK：MACD 最大值
- DIFF：MACD 最大-最小差值
- SLOPE：价格变化斜率
- AMP：振幅比
- VOLUME/AMOUNT/TURNRATE：量价指标
- RSI：相对强弱指标

---

## 5.4 Seg 模块 — 线段识别

**职责**：从笔序列中识别线段（多根笔组成的更大级别趋势）。提供 3 种可选算法。

| 文件 | 行数 | 核心类 | 职责 |
|------|------|--------|------|
| `Seg.py` | 156 | `CSeg` | 单条线段（起止笔/方向/中枢列表/趋势线） |
| `SegListComm.py` | 174 | `CSegListComm` | 线段列表基类（公共逻辑：左段处理、峰值查找） |
| `SegListChan.py` | 76 | `CSegListChan` | **Chan 算法**（标准缠论特征序列法） |
| `SegListDYH.py` | 96 | `CSegListDYH` | **DYH 算法**（1+1 模式匹配法） |
| `SegListDef.py` | 60 | `CSegListDef` | **Break 算法**（定义法/高低比较法） |
| `Eigen.py` | 28 | `CEigen` | 特征序列元素（继承 `CKLine_Combiner[CBi]`） |
| `EigenFX.py` | 150 | `CEigenFX` | 特征序列分型验证器（3 元素状态机） |
| `SegConfig.py` | 13 | `CSegConfig` | 线段算法配置 |

**三种算法对比**：

| 特性 | Chan（特征序列法） | DYH（1+1法） | Break（定义法） |
|------|-------------------|-------------|----------------|
| 理论严谨度 | 最高 | 中等 | 最低 |
| 实时响应性 | 中等 | 较高 | 最高 |
| 核心逻辑 | 3 元素分型序列完成 | 特定价格模式匹配 | 简单高低比较 |
| 是否可更新端点 | 否 | 是 | 是 |
| 适用场景 | 严格分析 | 实盘交易 | 快速粗筛 |

**Chan 算法核心**（`SegListChan.py` + `EigenFX.py`）：
- 维护两个 `CEigenFX` 对象：一个找向上线段（用向下笔构建），一个找向下线段（用向上笔构建）
- `CEigenFX` 是一个 3 元素状态机：第一元素→第二元素→第三元素
- 当第三元素完成且中间元素形成分型，线段确认
- 处理了"缺口"（gap）的特殊验证逻辑

**"左段"处理**（`SegListComm.py:collect_left_seg()`）：
- 最后一段可能未确认（笔还不够形成完整线段）
- `left_method="peak"`：递归查找峰值作为左段端点
- `left_method="all"`：把所有剩余笔归入最后一段

---

## 5.5 ZS 模块 — 中枢识别

**职责**：从笔/线段中识别中枢（重叠区间），支持合并。

| 文件 | 行数 | 核心类 | 职责 |
|------|------|--------|------|
| `ZS.py` | 234 | `CZS[LINE_TYPE]` | 单个中枢（边界/进出段/峰值/背驰判定） |
| `ZSList.py` | 161 | `CZSList` | 中枢列表管理（构造/合并/增量更新） |
| `ZSConfig.py` | 6 | `CZSConfig` | 中枢配置 |

**中枢构造算法**（`ZSList.py:try_construct_zs()`）：

```python
# "normal" 模式：取最后 2 根笔
min_high = min(bi._high() for bi in lst[-2:])
max_low = max(bi._low() for bi in lst[-2:])
valid = (min_high > max_low)  # 有重叠才是中枢

# 中枢区间 = [max_low, min_high]，即所有笔重叠的部分
```

**中枢合并**（`ZS.py:combine()`）：
- `zs` 模式：两个中枢的 [low, high] 区间有重叠就合并
- `peak` 模式：两个中枢的 [peak_low, peak_high] 有重叠就合并
- 合并后的中枢维护 `sub_zs_lst` 子中枢列表

**背驰判定**（`ZS.py:is_divergence()`）：
```python
in_metric = 进入笔的 MACD 指标
out_metric = 离开笔的 MACD 指标
is_divergence = (out_metric <= divergence_rate * in_metric)
```
当 `divergence_rate > 100` 时直接返回 True（"保送"模式）。

---

## 5.6 BuySellPoint 模块 — 买卖点识别

**职责**：基于中枢和背驰识别 6 种理论买卖点。

| 文件 | 行数 | 核心类 | 职责 |
|------|------|--------|------|
| `BSPointList.py` | 413 | `CBSPointList` | 买卖点计算引擎（全部 6 种类型） |
| `BS_Point.py` | 38 | `CBS_Point` | 单个买卖点对象 |
| `BSPointConfig.py` | 81 | `CBSPointConfig` + `CPointConfig` | 买卖点检测参数 |

**6 种买卖点类型详解**：

| 类型 | 含义 | 触发条件 | 代码方法 |
|------|------|----------|----------|
| **T1** | 1 类买卖点 | 线段末端 + 最后中枢出段 + MACD 背驰 | `treat_bsp1()` |
| **T1P** | 1' 类买卖点 | 无中枢，两根同向笔价格形态背驰 | `treat_pz_bsp1()` |
| **T2** | 2 类买卖点 | BSP1 后回抽幅度 ≤ max_bs2_rate | `treat_bsp2()` |
| **T2S** | 2S 类买卖点 | BSP2 后的二次/多次回抽延续 | `treat_bsp2s()` |
| **T3A** | 3A 类买卖点 | BSP1 后新中枢出段突破 | `treat_bsp3_after()` |
| **T3B** | 3B 类买卖点 | BSP1 前最后中枢的区间突破 | `treat_bsp3_before()` |

**计算流程**：
```
cal() →
  1. cal_seg_bs1point()  → 遍历线段，找 T1 和 T1P
  2. cal_seg_bs2point()  → 基于已找到的 T1，找 T2 和 T2S
  3. cal_seg_bs3point()  → 基于已找到的 T1，找 T3A 和 T3B
```

每个买卖点都双向计算（买/卖），配置也分买卖两套（`b_conf` / `s_conf`）。

---

## 5.7 DataAPI 模块 — 数据源接入

**职责**：统一不同数据源的接口。

| 文件 | 行数 | 核心类 | 支持周期 | 特点 |
|------|------|--------|----------|------|
| `CommonStockAPI.py` | 34 | `CCommonStockApi` | — | 抽象基类，定义接口 |
| `BaoStockAPI.py` | 114 | `CBaoStock` | 1M~月线 | A 股全周期，需要 login/logout |
| `AkshareAPI.py` | 141 | `CAkshare` | 日~月线 | A 股日线级别，无登录 |
| `ccxt.py` | 97 | `CCXT` | 5M~月线 | 加密货币，binance 为例 |
| `csvAPI.py` | 87 | `CSV_API` | 全部 | 本地 CSV，最灵活 |

**统一接口模式**：
```python
class CCommonStockApi:
    def get_kl_data() -> Iterable[CKLine_Unit]  # 每次迭代返回一根 K 线
    def SetBasciInfo()  # 设置股票基本信息
    def do_init()       # 初始化（连接/登录）
    def do_close()      # 关闭（断开/登出）
```

**自定义数据源**：
通过 `data_src="custom:package.ClassName"` 可动态导入任意实现了 `CCommonStockApi` 的类。

---

## 5.8 Plot 模块 — 可视化

**职责**：将分析结果渲染为交互式/静态图表。

| 文件 | 行数 | 核心类 | 职责 |
|------|------|--------|------|
| `PlotDriver.py` | 887 | `CPlotDriver` | 主绘图引擎（matplotlib） |
| `PlotMeta.py` | 170 | `CChanPlotMeta` + 多个 Meta 类 | 数据→绘图元数据转换 |
| `AnimatePlotDriver.py` | 19 | `CAnimateDriver` | Jupyter 逐帧动画 |

**可绘制的元素**（`plot_config` 控制）：

| 配置项 | 内容 |
|--------|------|
| `plot_kline` | K 线蜡烛图 |
| `plot_kline_combine` | 合并 K 线矩形 |
| `plot_bi` | 笔（线段连接） |
| `plot_seg` | 线段 |
| `plot_eigen` | 特征序列 |
| `plot_zs` | 中枢（矩形区域） |
| `plot_macd` | MACD 指标副图 |
| `plot_bsp` | 买卖点（箭头标注） |
| `plot_mean` | 均线 |
| `plot_channel` | 通道线 |
| `plot_boll` | 布林带 |
| `plot_rsi` | RSI |
| `plot_kdj` | KDJ |
| `plot_demark` | TD 序列 |
| `plot_marker` | 自定义标记 |

**PlotDriver.py 是整个项目最大的单文件（887 行）**，包含完整的 matplotlib 渲染逻辑。

---

## 5.9 Math 模块 — 技术指标

**职责**：提供各种技术指标的流式计算。

| 文件 | 行数 | 核心类 | 算法 |
|------|------|--------|------|
| `MACD.py` | 29 | `CMACD` | EMA 差值 + 信号线 + 柱线 |
| `BOLL.py` | 28 | `BollModel` | N 周期均值 ± 2 倍标准差 |
| `RSI.py` | 38 | `RSI` | 平滑上涨/下跌均值比 |
| `KDJ.py` | 34 | `KDJ` | 随机指标 (K/D/J) |
| `Demark.py` | 207 | `CDemarkEngine` | TD 序列（Setup + Countdown） |
| `TrendLine.py` | 75 | `CTrendLine` | 最小距离拟合趋势线 |
| `TrendModel.py` | 22 | `CTrendModel` | 滚动窗口 (MEAN/MAX/MIN) |

所有指标都是**流式的**（`add(value)` 逐点计算），不依赖 numpy/pandas。

---

## 5.10 Common 模块 — 基础设施

| 文件 | 行数 | 内容 |
|------|------|------|
| `CEnum.py` | 130 | 全部枚举定义（14 个 Enum 类） |
| `CTime.py` | 44 | 时间封装（支持日线自动设为 23:59:59） |
| `ChanException.py` | 88 | 分域异常体系（CHAN_ERR/TRADE_ERR/KL_ERR） |
| `func_util.py` | 54 | 工具函数（级别判断/方向反转/区间重叠） |
| `cache.py` | 34 | 方法结果缓存装饰器 |

---

## 5.11 ChanModel 模块 — 特征工程（骨架）

| 文件 | 行数 | 核心类 | 状态 |
|------|------|--------|------|
| `Features.py` | 18 | `CFeatures` | 仅 key-value 容器，无特征计算逻辑 |

公开版只有一个空壳 `CFeatures` 类，提供 `add_feat()` 和 `items()` 方法。
实际特征计算逻辑在完整版中。

---

## 5.12 App 模块 — 应用

| 文件 | 行数 | 功能 |
|------|------|------|
| `ashare_bsp_scanner_gui.py` | 732 | PyQt6 全 A 股扫描 GUI |

**功能**：多线程扫描全 A 股，过滤 ST/停牌/科创板/北交所，检测近 3 天买卖点信号，支持点击查看个股分析图。

---

## 5.13 Debug 模块 — 策略示例

| 文件 | 行数 | 演示内容 |
|------|------|----------|
| `strategy_demo.py` | 51 | 基础回测：在 BSP1 买入，在反向分型卖出 |
| `strategy_demo2.py` | 58 | 外部数据推送模式（`trigger_load`） |
| `strategy_demo3.py` | 77 | 多周期合成（15 分钟→60 分钟） |
| `strategy_demo4.py` | 53 | 多级别对齐（日线 + 30 分钟线） |

---

## 5.14 用户提到但公开版不存在的模块

| 模块 | 状态 | 说明 |
|------|------|------|
| `CustomBuySellPoint/` | **不存在** | README 提及的 cbsp（策略买卖点），公开版未包含 |
| `ModelStrategy/` | **不存在** | 模型策略框架，完整版功能 |
| `Trade/` | **不存在** | 交易引擎/执行层，完整版功能 |
| `OfflineData/` | **不存在** | 离线数据管理，完整版功能 |
| `Config/` | **不存在** | 配置管理模块，公开版直接用 ChanConfig.py |

---

# 6. 核心类解析

## 6.1 CChan — 总调度器

**文件**：`Chan.py`（379 行）

**职责**：整个系统的入口和编排者。负责数据加载、多级别递归处理、结果访问。

**构造参数**：
```python
CChan(
    code="sz.000001",          # 股票代码
    begin_time="2018-01-01",   # 起始日期
    end_time=None,             # 结束日期（None=至今）
    data_src=DATA_SRC.BAO_STOCK,  # 数据源
    lv_list=[KL_TYPE.K_DAY],   # 级别列表（从高到低）
    config=CChanConfig({...}), # 配置对象
    autype=AUTYPE.QFQ,         # 复权类型
)
```

**关键方法**：

| 方法 | 职责 | 调用时机 |
|------|------|----------|
| `do_init()` | 为每个级别创建 CKLine_List | 构造时 |
| `load()` | 完整数据加载 + 分析 pipeline | 构造时（非 trigger 模式） |
| `load_iterator(lv_idx, parent_klu, step)` | **核心递归**：逐级处理 K 线 | load() 内部 |
| `step_load()` | 增量加载，每根 K 线 yield 一次 | 回测/动画 |
| `trigger_load(inp)` | 外部推送 K 线数据 | 实时交易 |
| `GetStockAPI()` | 动态加载数据源类 | load() 内部 |
| `get_latest_bsp(idx, number)` | 获取最新买卖点 | 策略调用 |
| `__getitem__(n)` | 按级别或索引访问 KLine_List | 结果访问 |
| `chan_dump_pickle()` / `chan_load_pickle()` | 序列化/反序列化 | 缓存 |

**内部依赖**：直接依赖 CKLine_List（通过 `kl_datas` 字典）、所有 DataAPI、ChanConfig。

**三种执行模式**：
1. **批量模式**（`trigger_step=False`）：构造时自动加载全部数据，一次性计算
2. **步进模式**（`trigger_step=True` + `step_load()`）：Generator，每根 K 线 yield 一次快照
3. **推送模式**（`trigger_load()`）：外部手动传入 K 线数据

---

## 6.2 CChanConfig — 全局配置

**文件**：`ChanConfig.py`（183 行）

**职责**：用 dict 驱动所有子模块的配置，支持 ConfigWithCheck 防止拼写错误。

**配置层次**：
```python
CChanConfig
├── bi_conf: CBiConfig       # 笔配置
│   ├── bi_algo              # "normal" / "advance"
│   ├── is_strict            # 严格笔定义
│   ├── bi_fx_check          # 分型验证方式
│   ├── gap_as_kl            # 缺口算 K 线
│   ├── bi_end_is_peak       # 终点必须是峰
│   └── bi_allow_sub_peak    # 允许次高低点
├── seg_conf: CSegConfig     # 线段配置
│   ├── seg_algo             # "chan" / "1+1" / "break"
│   └── left_method          # "peak" / "all"
├── zs_conf: CZSConfig       # 中枢配置
│   ├── need_combine         # 是否合并
│   ├── zs_combine_mode      # "zs" / "peak"
│   ├── one_bi_zs            # 单笔中枢
│   └── zs_algo              # "normal" / "over_seg" / "auto"
├── bs_point_conf: CBSPointConfig    # 笔级买卖点配置
├── seg_bs_point_conf: CBSPointConfig  # 段级买卖点配置
├── 处理参数: trigger_step, skip_step, kl_data_check, ...
└── 技术指标参数: macd_config, rsi_cycle, kdj_cycle, ...
```

**ConfigWithCheck 机制**：每个 key 只能 get 一次，最后 `check()` 检查是否有未被使用的 key → 拼写错误立刻报错。

---

## 6.3 CKLine_List — 流程枢纽

**文件**：`KLine/KLine_List.py`（204 行）

**职责**：这是最关键的"胶水类"，串联了从 K 线合并到买卖点输出的全部流程。

**核心属性**：
```python
self.lst: List[CKLine]              # 合并 K 线列表
self.bi_list: CBiList               # 笔管理器
self.seg_list: CSegListComm         # 线段管理器（笔级）
self.segseg_list: CSegListComm      # 线段管理器（段级）
self.zs_list: CZSList               # 中枢列表（笔级）
self.segzs_list: CZSList            # 中枢列表（段级）
self.bs_point_lst: CBSPointList     # 买卖点（笔级）
self.seg_bs_point_lst: CBSPointList # 买卖点（段级）
self.metric_model_lst: List         # 技术指标模型
```

**核心方法 `add_single_klu(klu)`**：
```
1. klu.set_metric(metric_model_lst)  → 计算 MACD/RSI/KDJ 等
2. 如果是第一根 → 创建 CKLine(klu)
3. 否则 → 尝试与最后一根合并
   - COMBINE → 合并进最后一根
   - UP/DOWN → 新建 CKLine，更新分型，更新笔
4. 如果笔有更新 + 增量模式 → cal_seg_and_zs()
```

**核心方法 `cal_seg_and_zs()`**：
```
1. bi_list.try_add_virtual_bi()    → 尝试添加虚拟笔
2. cal_seg(bi_list, seg_list)       → 计算线段
3. zs_list.cal_bi_zs()             → 计算笔级中枢
4. update_zs_in_seg()              → 中枢关联到线段
5. 递归: cal_seg(seg_list, segseg_list)  → 计算"线段的线段"
6. segzs_list.cal_bi_zs()         → 段级中枢
7. seg_bs_point_lst.cal()          → 段级买卖点
8. bs_point_lst.cal()              → 笔级买卖点
```

---

## 6.4 策略/模型/交易接口（公开版状态）

| 接口 | 公开版情况 |
|------|-----------|
| 自定义策略买卖点（cbsp） | **不存在**。README 描述了接口，但代码中无 `CustomBuySellPoint/` 目录 |
| 模型接入 | **仅骨架**。`CFeatures` 是空容器（18 行），无特征计算代码 |
| 交易引擎 | **不存在**。无 `Trade/` 目录 |
| 信号监控 | **不存在**。仅 GUI 扫描器提供基本扫描 |

**从代码中能确认的策略接入方式**：
- 使用 `step_load()` 逐帧迭代
- 每帧调用 `chan.get_latest_bsp()` 获取信号
- 自行实现交易逻辑（参考 `Debug/strategy_demo.py`）

---

# 7. 一次完整执行流程

以 `main.py` 中的标准用例为例：

**步骤 1：构造 CChan**
```python
chan = CChan(code="sz.000001", begin_time="2018-01-01",
            data_src=DATA_SRC.BAO_STOCK, lv_list=[KL_TYPE.K_DAY], config=config)
```
- 验证 lv_list 顺序
- 创建 CChanConfig（包含笔/段/中枢/买卖点配置）
- 调用 `do_init()` → 为 K_DAY 创建 CKLine_List

**步骤 2：加载数据**
- `load()` 调用 `GetStockAPI()` → 获得 `CBaoStock` 类
- `CBaoStock.do_init()` → `baostock.login()`
- `init_lv_klu_iter()` → 创建数据迭代器

**步骤 3：逐根处理 K 线**（`load_iterator()`）
对每根原始 K 线 `klu`：
```
3a. 设置技术指标: klu.set_metric() → MACD, RSI, KDJ, BOLL, Demark
3b. K 线合并: KLine_List.add_single_klu(klu)
    → 处理包含关系 (方向感知合并)
    → 如果方向变化: 创建新的合并 K 线
3c. 分型识别: update_fx(prev, curr, next)
    → 标记 TOP / BOTTOM
3d. 更新笔: BiList.update_bi(klc)
    → 检查是否可以形成新笔
    → 管理虚拟笔
```

**步骤 4：最终分析**（`cal_seg_and_zs()`）
```
4a. 线段计算: SegListChan.update(bi_list)
    → 特征序列法识别线段
4b. 中枢计算: ZSList.cal_bi_zs(bi_list, seg_list)
    → 笔的重叠区间 → 中枢
    → 可选合并相邻中枢
4c. 中枢关联: update_zs_in_seg()
    → 中枢挂到对应线段
4d. 递归: 线段→线段的线段→段级中枢
4e. 买卖点: BSPointList.cal(bi_list, seg_list)
    → T1: 线段末端 + 最后中枢背驰
    → T1P: 无中枢，价格形态背驰
    → T2: BSP1 后回抽
    → T2S: 多次回抽延续
    → T3A: BSP1 后新中枢出段
    → T3B: BSP1 前中枢突破
```

**步骤 5：结果访问**
```python
chan[0]                    # CKLine_List (日线级别)
chan[0].bi_list            # 所有笔
chan[0].seg_list           # 所有线段
chan[0].zs_list            # 所有中枢
chan[0].bs_point_lst       # 所有买卖点
chan.get_latest_bsp(number=5)  # 最新 5 个买卖点
```

**步骤 6：可视化**
```python
plot_driver = CPlotDriver(chan, plot_config=plot_config, plot_para=plot_para)
plot_driver.figure.show()
```
PlotMeta 把分析对象转换为绘图元数据 → PlotDriver 用 matplotlib 渲染。

---

# 8. bsp/cbsp/模型/交易之间关系

## 8.1 bsp vs cbsp

| | bsp（理论买卖点） | cbsp（策略买卖点） |
|---|---|---|
| **定义** | 纯缠论结构推导的买卖点 | 结合策略逻辑的实际交易信号 |
| **代码** | `BuySellPoint/BSPointList.py` | **公开版不存在** |
| **输入** | 笔/线段/中枢/MACD | bsp + 自定义过滤条件 |
| **灵活度** | 固定的 6 种类型 | 可自定义策略逻辑 |
| **公开版状态** | 完整 | 缺失 |

从代码看，bsp 是"形态学层面"的信号——只要结构满足条件就产生；cbsp 按 README 描述是在 bsp 基础上叠加"策略层"的过滤/增强。但公开版中 cbsp 相关代码（CustomBuySellPoint/）完全不存在。

## 8.2 理论买卖点 vs 策略买卖点

- **理论买卖点**（bsp）：由缠论结构自动推导，不需要人为干预。配置通过 `CChanConfig` 的 `bs_type`、`divergence_rate`、`min_zs_cnt` 等参数控制。
- **策略买卖点**（cbsp）：需要用户自定义逻辑，例如"只在日线 BSP1 + 60 分钟线 BSP2 同时出现时才产生信号"。公开版需自行在 `step_load()` 循环中实现。

## 8.3 形态学计算 vs 动力学策略

- **形态学计算**（公开版核心）：K 线→合并→分型→笔→线段→中枢。纯几何/拓扑分析。
- **动力学策略**（部分公开）：背驰判定（MACD 比较）、买卖点类型识别。这是形态学和指标的交叉。
- **策略层**（未公开）：模型预测、组合信号、仓位管理、风控。

## 8.4 离线回测 vs 实时交易

| | 离线回测 | 实时交易 |
|---|---|---|
| **数据加载** | `load()` 一次加载全部 | `trigger_load()` 逐根推送 |
| **计算模式** | `step_load()` + 快照 | `trigger_step=True` |
| **交易执行** | 自行记录（Demo 级） | 需自建交易引擎（公开版无） |
| **代码示例** | `Debug/strategy_demo.py` | `Debug/strategy_demo2.py` |

## 8.5 缠论结构计算层 vs 交易执行层

```
结构计算层 (公开版完整):
  K 线 → 合并 → 分型 → 笔 → 线段 → 中枢 → bsp
  ↕
交易执行层 (公开版缺失):
  信号过滤 → 仓位管理 → 下单 → 持仓跟踪 → 风控
```

两层之间的"接口"是 `chan.get_latest_bsp()` 返回的 `CBS_Point` 对象。

---

# 9. 工程质量与局限性分析

## 9.1 架构评价

**清晰度：7/10**
- 模块边界基本合理：数据/结构分析/信号/可视化分层清楚
- 但 `CKLine_List` 承担了太多职责（K 线管理 + 全流程串联），是一个"上帝对象"
- `CChan` 同时是数据加载器、多级别协调器和结果访问器，职责边界模糊

**可扩展性：6/10**
- 数据源扩展很好：实现 `CCommonStockApi` 接口即可，支持 `custom:` 动态加载
- 线段算法扩展较好：3 种实现共用 `CSegListComm` 基类
- 但买卖点类型是 hardcode 的 6 种（`BSP_TYPE` 枚举固定），扩展需改核心代码
- 技术指标是硬编码到 `ChanConfig.GetMetricModel()` 里的

**Hardcode 情况**：
- `ashare_bsp_scanner_gui.py` 中 BaoStock 是硬编码的数据源
- `BaoStockAPI.py` 中 K 线类型映射是 if-else 链
- `BSPointList.py` 中 6 种买卖点的计算逻辑是直接串联调用，无插件机制
- `PlotDriver.py` 中颜色、大小等绑图参数大量硬编码

## 9.2 代码风格

**优点**：
- 类型注解较完整（使用 Generic、TypeVar）
- 异常体系清晰（分 CHAN_ERR/TRADE_ERR/KL_ERR 三域）
- ConfigWithCheck 防止配置拼写错误，设计精巧
- 泛型合并器 `CKLine_Combiner[T]` 复用度高
- 序列化（pickle）处理了链表指针的特殊需求

**不足**：
- 所有类名都用 `C` 前缀（`CChan`, `CKLine`, `CBi`），略显冗余
- 很多方法缺少 docstring
- `PlotDriver.py` 887 行，应拆分
- 部分方法较长（`BSPointList.py` 中的 `treat_bsp2s` 约 50 行连续逻辑）

## 9.3 项目定位判断

**更偏"研究型个人项目"还是"可工程化部署框架"？**

**答：研究型个人项目，带有工程化的骨架。**

理由：
1. 核心计算层质量很高，泛型设计、多算法支持、增量计算等体现了工程思维
2. 但无测试代码（零单元测试、零集成测试）
3. 无 requirements.txt / pyproject.toml，依赖管理缺失
4. 无 CI/CD、无 Docker、无日志框架
5. 完整版（22000 行）才包含策略/交易/模型，但未公开——说明核心竞争力在私有部分
6. GUI 应用是可用的，但属于"能跑"而非"可部署"的水平

## 9.4 哪些写得最好 vs 最脆弱

**最好**：
1. **Combiner/KLine_Combiner.py**：泛型合并器，逻辑清晰，复用度高
2. **Seg/EigenFX.py**：特征序列状态机，150 行实现了最复杂的缠论算法
3. **BuySellPoint/BSPointList.py**：413 行覆盖 6 种买卖点，逻辑完整
4. **Chan.py:load_iterator()**：递归多级别处理，优雅地解决了父子 K 线对齐

**最脆弱**：
1. **Plot/PlotDriver.py**：887 行单文件，改一处可能影响全局
2. **App/ashare_bsp_scanner_gui.py**：UI 和业务逻辑混在一起，依赖 PyQt6 版本
3. **DataAPI/BaoStockAPI.py**：BaoStock 库不稳定时整个流程崩溃，无重试/降级
4. **CKLine_List**：串联过多职责，难以独立测试

## 9.5 README 说的能力 vs 代码实际

| README 提到 | 代码实际 |
|-------------|----------|
| 缠论基本元素计算 | **成熟** |
| 策略买卖点（cbsp） | **不存在** |
| 机器学习特征 | **仅空壳容器** |
| 模型开发/AutoML | **不存在** |
| 线上交易 | **不存在** |
| 交易后端数据库 | **不存在** |
| Notion/COS 集成 | **不存在** |
| Gotify 推送 | **不存在** |

**公开版实现了 README 描述的大约 30% 的功能，集中在"缠论计算"部分。**

---

# 10. 适合什么人，不适合什么人

## 适合

| 人群 | 原因 |
|------|------|
| 想学习缠论程序化实现的开发者 | 代码是目前最完整的开源缠论实现之一 |
| 想做缠论回测研究的量化研究员 | step_load() 提供了基本的回测能力 |
| 想批量扫描 A 股缠论信号的个人投资者 | GUI 扫描器可直接使用 |
| 想把缠论计算接入自有系统的量化团队 | 核心引擎可作为计算后端 |

## 不适合

| 人群 | 原因 |
|------|------|
| 想开箱即用做实盘交易的人 | 无交易引擎，无风控，无仓位管理 |
| 不懂缠论的纯量化工程师 | 需要先理解缠论概念才能用好配置 |
| 需要生产级部署的团队 | 无测试、无 CI、无容器化 |
| 想直接用 ML 建模的数据科学家 | 特征工程部分是空壳 |

---

# 11. 如果我要继续深入，建议优先看哪些文件

## 第一梯队：必读（理解核心引擎）

| 优先级 | 文件 | 行数 | 理由 |
|--------|------|------|------|
| 1 | `Chan.py` | 379 | 总入口，理解整个 pipeline |
| 2 | `KLine/KLine_List.py` | 204 | 流程枢纽，串联全部分析 |
| 3 | `Combiner/KLine_Combiner.py` | 171 | K 线合并+分型识别的核心算法 |
| 4 | `Bi/BiList.py` | 235 | 笔的识别逻辑 |
| 5 | `BuySellPoint/BSPointList.py` | 413 | 买卖点检测的完整实现 |

## 第二梯队：按需深入

| 方向 | 文件 | 理由 |
|------|------|------|
| 理解线段算法 | `Seg/EigenFX.py` + `SegListChan.py` | 最复杂的缠论算法 |
| 理解中枢 | `ZS/ZS.py` + `ZSList.py` | 中枢构造和背驰判定 |
| 接入自有数据 | `DataAPI/CommonStockAPI.py` + `csvAPI.py` | 数据源接口 |
| 做可视化 | `Plot/PlotMeta.py`（非 PlotDriver） | 数据转绘图元数据 |
| 做回测 | `Debug/strategy_demo.py` | 最简策略模板 |
| 做实时推送 | `Debug/strategy_demo2.py` | trigger_load 用法 |

## 第三梯队：配置调参

| 文件 | 理由 |
|------|------|
| `ChanConfig.py` | 理解所有可调参数 |
| `Bi/BiConfig.py` | 笔的严格度控制 |
| `BuySellPoint/BSPointConfig.py` | 买卖点检测阈值 |

---

# 附录：如果我要二次开发/改造

## 最值得学的

1. **泛型合并器设计**（`CKLine_Combiner[T]`）：一套逻辑三处复用，值得在其他系统借鉴
2. **多级别递归处理**（`load_iterator`）：优雅地处理了时间序列的层级嵌套
3. **配置安全检查**（`ConfigWithCheck`）：用"get 一次删一次"防止拼写错误，小但实用
4. **增量计算设计**（虚拟笔 + step_load）：支持从批量分析无缝切换到实时分析

## 应该借鉴哪几层

1. **数据抽象层**：`CCommonStockApi` 接口 + 适配器模式
2. **结构分析层**：K 线合并 → 分型 → 笔 → 线段 → 中枢 的 pipeline
3. **信号层**：`CBSPointList` 的 6 种买卖点计算逻辑

## 最适合从哪里下手二次开发

1. **实现 CSV 数据源**：`DataAPI/csvAPI.py` 最简单，用你自己的数据跑通全流程
2. **写一个简单回测**：基于 `Debug/strategy_demo.py` 扩展，添加持仓/PnL 跟踪
3. **添加新的数据源**：继承 `CCommonStockApi`，对接 Tushare/Wind/自有数据库

## 接入自有系统最可能卡在哪里

1. **依赖管理**：无 requirements.txt，需要手动装 baostock/akshare/ccxt/matplotlib/PyQt6
2. **路径导入**：项目用的是相对导入（`from Chan import CChan`），需要把 `chan.py/` 加入 `sys.path` 或改为包结构
3. **无包发布**：不是 pip 可安装的包，需要 git submodule 或复制代码
4. **特征接口空壳**：如果想接 ML，需要自己实现特征提取逻辑

## 改造成 A 股选股/信号系统最先应该改什么

1. **添加 requirements.txt**（或 pyproject.toml），固化依赖版本
2. **改为包结构**：添加 `setup.py`，支持 `pip install`
3. **实现 cbsp 层**：在 bsp 之上添加自定义策略过滤器（如多级别联动、均线过滤）
4. **添加信号持久化**：把扫描结果写入 SQLite/PostgreSQL，支持历史查询
5. **添加调度器**：用 APScheduler 或 cron 定时扫描，替代手动点 GUI

---

> **报告生成时间**：2026-04-08
> **分析方式**：逐文件完整阅读代码后总结，非 README 复述
> **代码版本**：公开版，约 7562 行 Python
