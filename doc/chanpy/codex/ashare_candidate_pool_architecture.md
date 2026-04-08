# 1. 项目目标重新定义

你的真实目标，不是“研究 chan.py 本身”，而是做一个基于缠论结构计算能力的 **全 A 股周期性候选池筛选系统**。

一句更准确的定义：

> 这是一个以 `chan.py` 为缠论结构计算内核、以可插拔规则引擎为核心、以批量扫描和可解释输出为交付物的 A 股候选池筛选系统。

它要解决的不是“自动交易”，而是下面这组更务实的问题：

1. 定期扫描全 A 股，找出符合一组缠论条件的股票。
2. 允许“入池条件”不断演化，而不是写死成一个脚本。
3. 让结果可追溯、可复跑、可解释，而不是只给一个模糊结论。
4. 给非技术用户可读的原因说明，但不把核心判断交给大模型。

建议把系统首期目标收敛为：

1. 支持日终扫描。
2. 支持 5 到 10 个原子条件。
3. 支持规则组合。
4. 支持候选结果留痕与解释。
5. 支持后续升级到分钟级共振扫描。

这是建议，不是从 `chan.py` 代码中直接确认的事实。

# 2. chan.py 在该系统中的正确定位

## 2.1 它适合做什么

基于源码，`chan.py` 适合承担下面这些职责：

1. K 线数据进入后的缠论结构计算内核。
2. 分型、笔、线段、中枢、理论买卖点的对象化表达。
3. 多级别递归计算与父子级别对齐。
4. 批量计算场景中的统一结构输出入口。
5. 增量模式下的结构更新实验基础。

源码可确认的直接依据：

1. `CChan` 负责整体编排，入口在 [Chan.py](/Users/shenpeng/Git/chan-assist/chan.py/Chan.py)。
2. `CKLine_List` 已把 K 线合并、分型、笔、段、中枢、买卖点串成流水线，在 [KLine_List.py](/Users/shenpeng/Git/chan-assist/chan.py/KLine/KLine_List.py)。
3. `get_latest_bsp()`、`step_load()`、`trigger_load()` 已提供静态结果和增量入口，在 [Chan.py](/Users/shenpeng/Git/chan-assist/chan.py/Chan.py)。

## 2.2 它不适合做什么

基于公开代码，它不适合直接承担以下职责：

1. 全市场候选池规则管理。
2. 候选池落库、版本化、追踪历史命中。
3. 面向业务的规则组合引擎。
4. 非技术用户解释层。
5. 完整回测平台。
6. 交易执行与风控。
7. 大模型编排与问答服务。

源码可确认的依据：

1. 公开版存在 `BuySellPoint`，但没有可直接复用的“候选池规则层”。
2. `ChanModel/Features.py` 只有很薄的特征容器骨架，不是成熟特征平台，在 [Features.py](/Users/shenpeng/Git/chan-assist/chan.py/ChanModel/Features.py)。
3. README 提到的 `CustomBuySellPoint/`、`cbsp`、模型策略层，在当前公开仓库中并不存在对应源码，这一点与你已有 `info.md` 结论一致。

## 2.3 应该把它放在系统的哪一层

最合适的定位：

> `chan.py` 应放在“缠论结构计算层”，作为领域计算引擎，而不是系统总平台。

也就是：

1. 它负责把原始 K 线变成结构化对象。
2. 上层规则引擎只消费它的结果。
3. 调度、存储、解释、展示都不应塞进 `chan.py` 本体。

## 2.4 哪些能力可以直接复用

可以直接复用的能力：

1. `CChan` 的多级别计算编排。
2. `Bi/`、`Seg/`、`ZS/`、`BuySellPoint/` 的结构对象和算法。
3. `trigger_load()` / `step_load()` 的增量接口。
4. `DataAPI/` 的适配器接口抽象。
5. `Plot/` 的图形输出能力，适合作为诊断工具，不适合作为主业务前端。

尤其值得直接复用的对象访问路径：

1. `chan[lv].bi_list`
2. `chan[lv].seg_list`
3. `chan[lv].zs_list`
4. `chan[lv].bs_point_lst`
5. `chan.get_latest_bsp()`

## 2.5 哪些能力必须自己补

必须自建的能力：

1. 股票池与交易标的过滤。
2. 候选池规则引擎。
3. 扫描任务编排与调度。
4. 结果存储与历史查询。
5. 结构摘要与规则证据抽取。
6. 面向业务的解释层。
7. 大模型辅助层。
8. 配置管理与规则版本管理。

## 2.6 一个关键源码约束

这是一个对系统设计影响很大的事实：

1. 当前 [AkshareAPI.py](/Users/shenpeng/Git/chan-assist/chan.py/DataAPI/AkshareAPI.py) 只实现了 `K_DAY`、`K_WEEK`、`K_MON`。
2. 当前 [BaoStockAPI.py](/Users/shenpeng/Git/chan-assist/chan.py/DataAPI/BaoStockAPI.py) 才实现了 `K_5M`、`K_15M`、`K_30M`、`K_60M`。

因此：

> 如果你的规则未来要做“日线 + 30 分钟 / 60 分钟共振”，不能直接依赖当前 `AKSHARE` 适配器，必须补分钟级数据适配层或切换数据源。

这条是源码确认的事实。

# 3. 系统边界与一句话定义

一句话定义：

> 这是一个面向全 A 股的、基于缠论结构计算和可插拔规则引擎的周期性候选池筛选与解释系统。

边界定义：

它是：

1. 批量扫描系统。
2. 候选池生成系统。
3. 规则管理系统。
4. 结构化解释系统。
5. 人机协同分析系统。

它不是：

1. 自动交易系统。
2. 自动下单系统。
3. 完整回测平台。
4. 高实时低延迟撮合系统。
5. 用大模型直接替代规则判断的黑盒系统。

建议你在产品定义里明确写死一个原则：

> 核心筛选结果只能由“数据 + 结构计算 + 规则引擎”产生；大模型只参与解释、辅助配置和问答，不参与最终命中裁决。

这是建议，不是从 `chan.py` 代码中直接确认的事实。

# 4. 推荐的系统分层架构

建议采用“模块化单体”架构，而不是一上来做微服务。

建议的新项目结构：

```text
candidate_pool/
├── data_access/
├── chan_engine/
├── feature_snapshot/
├── rules/
├── scanner/
├── storage/
├── explain/
├── llm/
├── api/
├── ui/
└── config/
```

## 4.1 数据接入层

### 作用

1. 获取全 A 股股票列表。
2. 过滤不可交易标的。
3. 拉取不同周期 K 线。
4. 统一输出给结构计算层。

### 是否复用 chan.py

部分复用。

可复用：

1. `DataAPI/CommonStockAPI.py` 的适配器抽象。
2. `BaoStockAPI.py`、`AkshareAPI.py`、`csvAPI.py` 的基本范式。

不可直接复用的部分：

1. 全市场股票池管理。
2. 数据缓存。
3. 统一的分钟级和日级数据仓接口。

### 是否需要新写

需要。

建议新写：

1. `UniverseProvider`
2. `MarketDataProvider`
3. `BarRepository`

建议接口：

```python
class UniverseProvider(Protocol):
    def list_symbols(self, trade_date: date) -> list[SymbolMeta]: ...

class MarketDataProvider(Protocol):
    def get_bars(self, symbol: str, level: str, start: datetime, end: datetime) -> list[Bar]: ...
```

### 和上下游如何交互

1. 向上给扫描调度层提供股票列表和 K 线。
2. 向下不直接依赖 `chan.py`，而是给 `chan_engine` 层喂标准化 `Bar`。

### 最小可行实现

1. 股票池列表先用单一数据源。
2. 日线先用 `Akshare` 或 `BaoStock`。
3. 分钟级若需要，优先单独封装成新 provider，不要把业务逻辑写进 `chan.py/DataAPI`。
4. 原始 K 线缓存到本地 Parquet 或按日期分目录的文件。

## 4.2 缠论结构计算层

### 作用

1. 把标准化 K 线转成 `CChan` 可消费对象。
2. 执行结构计算。
3. 产出上层可稳定消费的结构快照。

### 是否复用 chan.py

强复用。

核心复用：

1. `CChan`
2. `CChanConfig`
3. `CKLine_List`
4. `Bi` / `Seg` / `ZS` / `BSPoint`

### 是否需要新写

需要写一层包装，不建议上层直接散落访问 `chan[lv].xxx`。

建议新写：

1. `ChanEngineAdapter`
2. `ChanSnapshotExtractor`
3. `LevelSnapshot`

建议接口：

```python
@dataclass
class LevelSnapshot:
    level: str
    last_bar_time: str
    last_fx: str | None
    last_bi_dir: str | None
    last_bi_idx: int | None
    last_seg_dir: str | None
    last_seg_idx: int | None
    latest_bsp: list[dict]
    zs_summary: list[dict]
    raw_refs: dict

class ChanEngineAdapter:
    def build(self, symbol: str, levels: list[str], bars_by_level: dict[str, list[Bar]], chan_config: dict) -> "ChanRunResult": ...
```

### 和上下游如何交互

1. 从数据接入层拿标准化 K 线。
2. 对规则引擎暴露“结构快照 + 原始引用”。

### 最小可行实现

1. 用 `CChan` 计算。
2. 抽取“最后分型、最后笔、最后段、最近买卖点、最近中枢”这些摘要。
3. 不要在首期把整个 `CChan` 对象存数据库。

## 4.3 候选池规则引擎层

### 作用

1. 定义规则。
2. 组合规则。
3. 评估规则。
4. 产出命中证据。

### 是否复用 chan.py

不直接复用。

`chan.py` 提供的是结构对象，不是规则系统。

### 是否需要新写

必须新写。

建议模块：

1. `RuleRegistry`
2. `ConditionPlugin`
3. `RuleEvaluator`
4. `RuleDefinitionRepository`

### 和上下游如何交互

1. 输入是结构快照和上下文。
2. 输出是 `RuleMatchResult`。
3. 结果交给扫描层聚合并落库。

### 最小可行实现

1. 原子条件用 Python 插件实现。
2. 规则组合用 YAML 或 JSON 文件配置。
3. 支持 `all` / `any` / `not`。

这一层详见第 5 节。

## 4.4 扫描调度层

### 作用

1. 定义一次扫描任务。
2. 拿股票池。
3. 拉数据。
4. 计算结构。
5. 执行规则。
6. 保存结果。

### 是否复用 chan.py

不复用。

### 是否需要新写

必须新写。

建议模块：

1. `ScanJobRunner`
2. `SymbolScanWorker`
3. `ScanPlanBuilder`
4. `RankingService`

### 和上下游如何交互

1. 从数据接入层取标的和 K 线。
2. 调用结构计算层。
3. 调用规则引擎层。
4. 把结果交给存储层。

### 最小可行实现

1. 单机多进程并发按股票扫描。
2. 每日收盘后固定时间跑。
3. 每次扫描生成一个 `scan_job` 记录。

## 4.5 结果存储层

### 作用

1. 存规则版本。
2. 存扫描任务。
3. 存候选池结果。
4. 存证据和解释。

### 是否复用 chan.py

不复用。

### 是否需要新写

必须新写。

建议模块：

1. `ScanJobRepository`
2. `CandidateRepository`
3. `RuleRepository`
4. `ExplanationRepository`

### 和上下游如何交互

1. 接收扫描层输出。
2. 给解释层和展示层提供查询。

### 最小可行实现

1. 关系库存元数据和结果。
2. 文件缓存存原始 K 线和图。

这一层详见第 7 节。

## 4.6 解释与展示层

### 作用

1. 把结构化命中结果翻译成业务可读文本。
2. 提供候选池浏览、筛选、详情查看。
3. 展示命中原因和结构摘要。

### 是否复用 chan.py

部分复用。

可复用：

1. `Plot/` 作为图形辅助。

不建议复用：

1. 现有 `ashare_bsp_scanner_gui.py` 作为正式业务前端。

源码确认事实：

1. 当前 [ashare_bsp_scanner_gui.py](/Users/shenpeng/Git/chan-assist/chan.py/App/ashare_bsp_scanner_gui.py) 是 PyQt GUI 示例。
2. 其中 `ScanThread` 是一个后台线程顺序扫描股票，不是成熟的规则平台。

### 是否需要新写

需要。

建议模块：

1. `ExplanationRenderer`
2. `CandidateDetailAssembler`
3. `ReportExporter`

### 和上下游如何交互

1. 从存储层取结构化结果。
2. 可调用大模型层做自然语言改写。

### 最小可行实现

1. Streamlit 页面或简单 Web 页面。
2. 每只股票展示：命中规则、关键证据、最近结构摘要、图形链接。

## 4.7 大模型辅助层

### 作用

1. 结构化结果改写成人话。
2. 自然语言生成规则草案。
3. 用户问答。

### 是否复用 chan.py

不复用。

### 是否需要新写

需要。

建议模块：

1. `LLMExplanationService`
2. `RuleDraftAssistant`
3. `CandidateQnAService`

### 和上下游如何交互

1. 只消费结构化结果，不直接读原始 `CChan` 对象。
2. 输出说明文字或规则草案。

### 最小可行实现

1. 先只做解释改写，不做自动规则发布。

## 4.8 管理配置层

### 作用

1. 管理规则集版本。
2. 管理扫描计划。
3. 管理数据源配置。
4. 管理解释模板和提示词。

### 是否复用 chan.py

不复用。

### 是否需要新写

需要。

建议模块：

1. `RuleSetConfig`
2. `ScanProfileConfig`
3. `PromptTemplateConfig`
4. `ChanParamConfig`

### 和上下游如何交互

1. 扫描层读取扫描配置。
2. 规则层读取规则版本。
3. 解释层读取模板。

### 最小可行实现

1. 配置文件先落在 Git 管理的 YAML 中。
2. 后续再做后台可视化管理。

# 5. 候选池规则引擎设计

这是整个系统最关键的一层。

核心原则：

> 不要把规则直接写成“遍历股票 -> if 最近 3 天买点”的一次性脚本，而要把规则拆成“原子条件插件 + 组合表达式 + 规则版本”。

## 5.1 规则应该如何表达

我建议采用：

> 第一阶段用“Python 原子条件插件 + YAML/JSON 规则组合配置”的混合方案。

不建议第一阶段直接做纯 DSL，原因：

1. 缠论条件本身对象关系复杂。
2. 很多判断需要访问 `Bi`、`Seg`、`ZS`、`BSP` 之间的上下文。
3. 纯 DSL 一开始很难把“底分型刚确认”“中枢突破后第一个回抽”“多级别共振”表达好。
4. 如果为了 DSL 去做大量解释器工作，会拖慢 MVP。

也不建议第一阶段直接把规则存在数据库里并做后台编辑器，原因：

1. 规则定义还处在快速演化期。
2. 先用 Git 管理更适合版本比较、回滚和代码评审。

## 5.2 第一阶段最务实的方案

### 方案

1. 原子条件写成 Python 插件。
2. 规则组合写成 YAML。
3. 规则版本按文件管理。
4. 每次扫描绑定一个 `ruleset_version`。

### 原子条件接口建议

```python
class ConditionPlugin(Protocol):
    key: str

    def evaluate(self, ctx: "RuleContext", params: dict) -> "ConditionResult":
        ...

@dataclass
class ConditionResult:
    passed: bool
    score: float | None
    evidence: list[dict]
    tags: list[str]
```

### 规则上下文建议

```python
@dataclass
class RuleContext:
    symbol: str
    trade_date: str
    chan_run_id: str
    level_snapshots: dict[str, LevelSnapshot]
    chan_objects: dict[str, object] | None
    market_meta: dict
```

说明：

1. `level_snapshots` 供大多数规则使用。
2. `chan_objects` 只给复杂规则兜底访问，避免规则层全面耦合到底层对象。

## 5.3 规则组合怎么支持

### 组合表达式

建议只实现三种布尔节点：

1. `all`
2. `any`
3. `not`

再加一种叶子节点：

1. `cond`

示例：

```yaml
rule_id: daily_2buy_60m_bottom_v1
name: 日线二买 + 60分钟底分型
version: 1
enabled: true
root:
  all:
    - cond: bsp_recent
      level: K_DAY
      params:
        is_buy: true
        types: ["2"]
        within_bars: 3
    - cond: fx_recent
      level: K_60M
      params:
        fx: BOTTOM
        confirmed: true
        within_bars: 2
```

### 时间窗口条件

建议统一成几类参数，不要每个条件自己发明口径：

1. `within_bars`
2. `within_days`
3. `since_trade_date`
4. `offset`

例如：

1. “近 3 天出现买卖点” 用 `within_days: 3`
2. “近 2 根 K 线形成有效底分型” 用 `within_bars: 2`

### 多级别联动

规则节点自身带 `level`。

例如：

1. `K_DAY` 上判断中枢突破。
2. `K_60M` 上判断最近底分型。
3. 上层表达式做 `all`。

### 缠论结构条件 + 指标条件

不要把技术指标逻辑塞进一个“大而全的规则类”。

建议拆成独立原子条件：

1. `bsp_recent`
2. `fx_recent`
3. `new_bi_formed`
4. `new_seg_formed`
5. `zs_breakout`
6. `divergence_exists`
7. `macd_strength`
8. `rsi_range`

这样结构条件和指标条件天然可以组合。

## 5.4 如何支持未来扩展而不重写系统

关键做法有四个：

1. 规则组合配置和原子条件实现解耦。
2. 规则判断结果必须返回结构化证据。
3. 结构快照层要保持相对稳定。
4. 每新增一个复杂条件，只新增插件，不改引擎主流程。

举例：

以后想扩展：

1. 底分型条件
2. 新笔条件
3. 新段条件
4. 中枢突破
5. 背驰
6. 二买
7. 三买
8. 多周期共振

你应该做的是：

1. 新增对应 `ConditionPlugin`
2. 在 `RuleRegistry` 注册
3. 在 YAML 规则里引用

而不是：

1. 改扫描器主流程
2. 改数据库核心表结构
3. 改 UI 主逻辑

## 5.5 推荐的规则建模方案

我认为当前阶段最合适的方案是：

> “代码实现原子条件，配置实现规则组合，结果输出统一结构化证据”。

这是当前阶段最平衡的点：

1. 比纯 Python 硬编码更可维护。
2. 比一上来做 DSL 更务实。
3. 比直接数据库可视化编排更容易落地。

## 5.6 候选池输出的数据结构应该长什么样

建议定义一个统一输出对象：

```python
@dataclass
class CandidateHit:
    scan_id: str
    trade_date: str
    symbol: str
    name: str
    matched: bool
    matched_rules: list[dict]
    primary_rule_id: str | None
    score: float | None
    levels: list[str]
    signal_time: str | None
    price_snapshot: dict
    structure_snapshot: dict
    evidence: list[dict]
    explanation_structured: dict
    explanation_text: str | None
```

其中 `matched_rules` 建议长这样：

```json
[
  {
    "rule_id": "daily_2buy_60m_bottom_v1",
    "rule_version": 1,
    "passed": true,
    "score": 0.86,
    "evidence": [
      {
        "type": "bsp_recent",
        "level": "K_DAY",
        "event_time": "2026-04-08",
        "value": "2",
        "ref": {"bi_idx": 128}
      },
      {
        "type": "fx_recent",
        "level": "K_60M",
        "event_time": "2026-04-08 14:30",
        "value": "BOTTOM",
        "ref": {"klc_idx": 542}
      }
    ]
  }
]
```

这一层最重要的不是“算出一个 True/False”，而是“保留下来为什么是 True”。

# 6. 全A股扫描执行流程设计

## 6.1 每日如何跑

建议首期做日终扫描。

标准流程：

1. 收盘后等待数据源稳定。
2. 生成 `scan_job`。
3. 获取交易日股票池。
4. 拉取所需级别 K 线。
5. 对每只股票计算结构。
6. 对所有启用规则做一次评估。
7. 写入候选池结果。
8. 生成解释文本和日报。

建议扫描时间：

1. A 股收盘后延迟 15 到 45 分钟。

这是建议，不是从 `chan.py` 代码中直接确认的事实。

## 6.2 每次扫描时的执行顺序

建议顺序：

1. 先做股票池级别的轻过滤。
2. 再拉取 K 线。
3. 再做结构计算。
4. 再做规则评估。
5. 再做排序和去重。
6. 再做解释生成。

具体执行链：

```text
Universe -> Prefilter -> Bars -> CChan -> Snapshot -> RuleEval -> CandidateHit -> DB -> Explanation -> UI
```

## 6.3 先算结构还是先筛股票

答案是：

1. 先做“轻量股票池过滤”。
2. 然后先算结构，再跑规则。

理由：

1. 规则本身依赖结构结果。
2. 但有一些轻过滤不需要结构计算，应该前置。

建议前置过滤：

1. ST 过滤。
2. 上市天数过滤。
3. 停牌过滤。
4. 流动性过滤。
5. 不关注板块过滤。

## 6.4 全量扫描还是增量扫描

### 第一阶段建议

建议做：

> 全市场范围内的“滚动窗口重算 + 结果增量落库”。

解释：

1. 全市场每天都可能有新 K 线，所以股票范围上仍然是全量。
2. 每只股票只重算最近一个足够长的窗口，而不是从上市首日算到今天。
3. 扫描结果按 `scan_id` 增量入库。

为什么首期不建议强依赖 `trigger_load()` 做持久化增量：

1. 增量模式在分钟级尤其涉及“未完成 K 线回滚/修正”。
2. 首期先追求正确性和可复现，比追求极致性能更重要。

### 第二阶段建议

当需要盘中周期性扫描时，再升级为：

1. 交易日内持久化结构快照。
2. 用 `trigger_load()` 或“快照 + 重放”做增量更新。

这是建议，不是从 `chan.py` 代码中直接确认的事实。

## 6.5 缓存要放在哪一层

建议放三层缓存：

1. 数据接入层缓存原始 K 线。
2. 结构计算层缓存结构快照。
3. 展示层缓存图形和解释文本。

不建议把缓存和规则结果混在一起。

## 6.6 如何避免重复计算

建议做法：

1. 同一只股票在同一次扫描中只计算一次 `CChan`。
2. 所有规则共用同一份 `LevelSnapshot`。
3. 解释层只读取已经保存的证据和摘要，不重新跑结构计算。

也就是说，计算复用的单位应该是：

> `symbol + trade_date + levels + chan_config_version`

## 6.7 如何兼顾性能与正确性

建议策略：

1. 用固定回看窗口保证结构稳定。
2. 用进程池按股票并行。
3. 每个扫描任务固定数据源、时间截面、配置版本。
4. 所有规则共享一次结构结果。

推荐经验做法：

1. 日线回看 250 到 500 个交易日。
2. 30 分钟和 60 分钟回看最近 20 到 60 个交易日。

这属于架构建议，不是从 `chan.py` 代码中直接确认的事实。

## 6.8 未来升级到盘中周期性扫描，需要改哪里

主要改四层：

1. 数据接入层：需要稳定分钟数据源和“未完成 K 线”处理策略。
2. 结构计算层：需要快照增量更新或快照重放机制。
3. 扫描调度层：从日终批处理变成定时循环任务。
4. 结果层：要区分“盘中候选”和“收盘确认候选”。

规则引擎本身不应该大改。

这正是为什么规则层要和调度层解耦。

# 7. 结果存储与数据模型设计

## 7.1 候选池表需要存什么字段

建议至少有以下核心表。

## 7.2 `scan_job`

记录一次扫描任务。

建议字段：

| 字段 | 说明 |
|---|---|
| `scan_id` | 扫描任务 ID |
| `trade_date` | 交易日 |
| `scan_type` | `eod` / `intraday` |
| `started_at` | 开始时间 |
| `finished_at` | 结束时间 |
| `status` | 成功/失败/部分成功 |
| `universe_size` | 股票池大小 |
| `success_count` | 成功计算数 |
| `fail_count` | 失败数 |
| `ruleset_version` | 规则集版本 |
| `chan_config_version` | 缠论参数版本 |
| `data_cutoff_time` | 数据截面时间 |

## 7.3 `rule_definition`

记录规则定义和版本。

建议字段：

| 字段 | 说明 |
|---|---|
| `rule_id` | 规则 ID |
| `version` | 版本号 |
| `name` | 规则名称 |
| `enabled` | 是否启用 |
| `rule_json` | 规则表达式 |
| `description` | 规则说明 |
| `created_at` | 创建时间 |

## 7.4 `candidate_hit`

这是最核心的结果表。

建议字段：

| 字段 | 说明 |
|---|---|
| `id` | 主键 |
| `scan_id` | 对应扫描任务 |
| `trade_date` | 交易日 |
| `symbol` | 股票代码 |
| `name` | 股票名称 |
| `primary_rule_id` | 主命中规则 |
| `primary_rule_version` | 主命中规则版本 |
| `matched_rule_ids` | 命中规则列表 |
| `score` | 综合分数 |
| `signal_time` | 关键信号时间 |
| `last_price` | 最近价格 |
| `change_pct` | 涨跌幅 |
| `levels` | 命中的级别集合 |
| `direction` | 候选方向，通常是 long/short 或 buy/sell |
| `status` | active / archived / removed |
| `explanation_text` | 自然语言解释 |
| `explanation_structured_json` | 结构化解释 |
| `structure_snapshot_json` | 结构摘要 |
| `evidence_json` | 命中证据 |
| `created_at` | 写入时间 |

## 7.5 `candidate_hit_rule`

如果要更规范，建议拆一个子表存“每只股票命中了哪些规则”。

建议字段：

| 字段 | 说明 |
|---|---|
| `candidate_hit_id` | 主表外键 |
| `rule_id` | 规则 ID |
| `rule_version` | 规则版本 |
| `passed` | 是否命中 |
| `score` | 该规则分数 |
| `evidence_json` | 该规则证据 |

## 7.6 `symbol_snapshot`

用来保存每次扫描时对股票结构的摘要，而不是整个 `CChan` 对象。

建议字段：

| 字段 | 说明 |
|---|---|
| `scan_id` | 扫描任务 |
| `symbol` | 股票代码 |
| `level` | 级别 |
| `snapshot_json` | 结构摘要 |
| `last_bar_time` | 最后一根 K 线时间 |

## 7.7 每次扫描结果如何落库

建议落库顺序：

1. 创建 `scan_job`
2. 每只股票结构计算完成后保存 `symbol_snapshot`
3. 命中规则后写 `candidate_hit`
4. 写 `candidate_hit_rule`
5. 解释完成后回填 `explanation_text`

## 7.8 是否要保存解释文本

要。

但建议同时保存两份：

1. `explanation_structured_json`
2. `explanation_text`

因为：

1. 结构化结果用于可追溯和可复现。
2. 自然语言用于给非技术用户阅读。

## 7.9 是否要保存原始结构特征

要保存“摘要化后的结构特征”，不建议第一阶段把完整内部对象入库。

建议保存：

1. 最近分型类型和时间。
2. 最近笔方向、索引、是否确认。
3. 最近线段方向、是否确认。
4. 最近中枢区间和突破状态。
5. 最近买卖点类型和时间。

## 7.10 是否要保存最近一次命中的规则

必须保存。

至少保存：

1. 主命中规则。
2. 所有命中规则。
3. 对应规则版本。

否则以后你无法回答：

1. 这只股票为什么进池。
2. 是哪版规则把它选进来的。

## 7.11 是否要保存 K线/笔/段/中枢摘要

建议保存摘要，不建议存全量对象。

推荐摘要结构：

```json
{
  "K_DAY": {
    "last_fx": {"type": "BOTTOM", "time": "2026-04-08"},
    "last_bi": {"idx": 128, "dir": "UP", "is_sure": true},
    "last_seg": {"idx": 33, "dir": "DOWN", "is_sure": true},
    "last_zs": {"low": 12.31, "high": 12.88, "begin_bi_idx": 120, "end_bi_idx": 126},
    "latest_bsp": [{"type": "2", "time": "2026-04-08"}]
  }
}
```

## 7.12 哪些适合数据库，哪些适合文件缓存

适合数据库：

1. 扫描任务元数据。
2. 规则定义。
3. 候选池结果。
4. 结构摘要。
5. 解释文本。

适合文件缓存：

1. 原始 K 线明细。
2. 大体积图像。
3. 临时结构快照。
4. 可选的 `CChan` pickle 调试快照。

如果以后确实要落 `CChan` 快照，建议只在调试模式保存，不要每次正式扫描都存。

# 8. 非技术用户解释层设计

## 8.1 每个候选项需要输出哪些解释字段

每个候选项建议至少输出以下字段：

1. 股票代码和名称。
2. 入池日期和时间。
3. 命中规则名称。
4. 简短一句话结论。
5. 关键证据列表。
6. 涉及的级别。
7. 最近结构状态。
8. 风险提示。
9. 技术说明入口。

建议结构：

```json
{
  "summary_title": "日线二买 + 60分钟底分型共振",
  "summary_plain": "该股票在日线层面出现二买，同时60分钟级别刚出现止跌结构，属于短中期共振候选。",
  "evidence_bullets": [
    "日线最近3个交易日出现二买",
    "60分钟最近2根K线确认底分型",
    "当前价格仍在最近中枢上沿附近"
  ],
  "risk_notes": [
    "60分钟结构仍可能变化",
    "若回落跌回中枢内，共振有效性下降"
  ]
}
```

## 8.2 如何把技术术语翻译成人话

建议做一个固定术语翻译表。

例如：

1. 底分型：短期止跌形态确认。
2. 二买：第一次转强后回调不破关键结构，再次转强的机会。
3. 三买：突破整理区后回踩不破，再次上攻的机会。
4. 中枢突破：价格走出了前一段震荡重叠区。
5. 背驰：价格创新低或新高，但趋势力度没有同步增强。
6. 多级别共振：大级别方向和小级别触发信号同时支持同一结论。

建议把解释拆成两层：

1. 专业层。
2. 白话层。

## 8.3 大模型适合放在哪一步

最合适的位置：

> 放在“结构化证据已经生成之后”的自然语言改写步骤。

流程应该是：

1. 规则引擎先产出结构化证据。
2. 模板层先产出基础说明。
3. 大模型再把它改写成更自然的语言。

## 8.4 大模型不应该碰哪一步

不应该碰：

1. K 线计算。
2. 分型/笔/段/中枢识别。
3. 规则命中判断。
4. 候选池最终裁决。

## 8.5 如何避免大模型胡说八道

建议做法：

1. 输入只给结构化证据，不给它自由猜图。
2. 输出限制在固定 JSON schema 或固定模板。
3. 提示词要求“只能基于输入字段生成，不得补充未提供事实”。
4. 保存模型输入与输出，便于审计。
5. 用低温度。

## 8.6 是否应该采用“先结构化，再改写”的方式

结论是：

> 应该，而且几乎是必须。

正确链路：

```text
规则命中 -> 结构化证据 -> 模板化说明 -> LLM 改写 -> 用户展示
```

错误链路：

```text
K线图/对象 -> 直接让 LLM 判断为什么入池
```

# 9. 大模型在系统中的正确使用方式

## 9.1 适合做的事

1. 候选项原因说明。
2. 自然语言问答。
3. 自然语言转规则草案。
4. 结果摘要日报。

## 9.2 不适合做的事

1. 替代 `chan.py` 做缠论结构识别。
2. 替代规则引擎做最终命中判断。
3. 直接从图片“看图选股”作为正式业务结果。
4. 在没有结构化证据时直接生成原因。

## 9.3 推荐接入方式

建议设计两个独立服务：

1. `LLMExplanationService`
2. `RuleDraftAssistant`

### `LLMExplanationService`

输入：

1. 股票基础信息。
2. 命中规则。
3. 结构化证据。
4. 风险提示模板。

输出：

1. 标题。
2. 一句话说明。
3. 详细解释。
4. 风险提示。

### `RuleDraftAssistant`

输入：

1. 用户自然语言需求。
2. 当前支持的条件插件列表。

输出：

1. 规则草案 JSON/YAML。
2. 无法表达的部分提示。
3. 需要确认的歧义点。

## 9.4 如何保证可控

建议加三条约束：

1. LLM 只能生成“规则草案”，不能直接上线。
2. 新规则必须经过人工确认和回测验证。
3. 解释文本永远以结构化证据为依据。

# 10. 技术选型建议（MVP版 / 扩展版）

## 10.1 MVP 版

目标：

1. 快速做出来。
2. 能稳定日终跑全 A 股。
3. 支持规则扩展。
4. 支持结果查询和解释。

建议选型：

| 维度 | 建议 |
|---|---|
| Python 项目结构 | 单仓模块化单体 |
| 后端服务框架 | 首期可不做重后端，`Typer` CLI + 轻量 `FastAPI` 查询接口 |
| 调度器 | `cron` 或 `APScheduler` |
| 存储 | `PostgreSQL` 优先；若纯个人本地验证可短期用 `SQLite` |
| 缓存 | 本地文件缓存，推荐 `Parquet` |
| 前端/展示 | `Streamlit` |
| 消息队列 | 不需要 |
| 微服务 | 不需要 |
| 容器化 | 可选，部署时再上 `docker-compose` |
| 异步任务框架 | 不需要，先用进程池批量扫描 |

这里我给的建议比“脚本 + SQLite”稍重一点，原因是：

1. 你要做的是“持续迭代的候选池系统”，不是一次性研究脚本。
2. 全 A 股扫描、规则版本、历史结果、解释文本，这些用 `PostgreSQL` 会舒服很多。

## 10.2 扩展版

当系统进入第二阶段，再考虑升级为：

| 维度 | 建议 |
|---|---|
| 后端 | `FastAPI` 正式化 API 服务 |
| 扫描执行 | 独立 worker 进程 |
| 存储 | `PostgreSQL` |
| 缓存 | `Redis` + 文件缓存 |
| 前端 | 前后端分离或保留 Streamlit 内部版 |
| 任务队列 | `Celery` 或 `RQ`，仅当盘中频繁扫描再引入 |
| 容器化 | `docker-compose` 起步 |

## 10.3 为什么不建议一开始就上微服务

因为你现在的复杂度核心不在部署，而在：

1. 规则建模。
2. 结构抽象。
3. 数据一致性。
4. 结果解释。

微服务不会帮你解决这些核心问题，反而会增加：

1. 调试成本。
2. 事务复杂度。
3. 发布成本。

# 11. 备选架构方案对比

## 11.1 方案 A：单机脚本 + SQLite + Streamlit

形态：

1. 扫描脚本直接跑。
2. `SQLite` 存结果。
3. `Streamlit` 看候选池。

优点：

1. 开发最快。
2. 成本最低。
3. 很适合快速验证规则。

缺点：

1. 规则和调度容易越写越乱。
2. 扫描历史和多版本管理会很快变笨重。
3. 后续盘中升级成本较高。

## 11.2 方案 B：模块化单体 + PostgreSQL + 文件缓存 + Streamlit/FastAPI

形态：

1. 一个 Python 仓库。
2. 一个扫描 worker。
3. 一个轻量查询/API 层。
4. `PostgreSQL` 存结果。
5. 文件缓存存 K 线和图。

优点：

1. 复杂度适中。
2. 规则引擎和存储边界清楚。
3. 便于后续加盘中扫描和 LLM。
4. 不需要微服务。

缺点：

1. 初期搭建成本高于方案 A。
2. 需要稍微认真做数据模型。

## 11.3 方案 C：研究引擎 + API 服务 + Redis/Celery + 前后端分离

形态：

1. 扫描任务队列化。
2. API 正式服务化。
3. 前后端分离。
4. LLM 模块独立。

优点：

1. 扩展性最好。
2. 适合多人协作和更高频任务。

缺点：

1. 前期明显过重。
2. 你会把大量时间花在工程基础设施上，而不是规则效果上。

## 11.4 对比结论

| 方案 | 开发复杂度 | 可维护性 | 性能 | 当前适配度 | 扩展性 |
|---|---|---|---|---|---|
| A | 低 | 中低 | 中 | 高 | 中低 |
| B | 中 | 高 | 高 | 最高 | 高 |
| C | 高 | 高 | 高 | 低 | 最高 |

对你当前目标最合适的是：

> 方案 B，模块化单体。

# 12. 最终推荐方案

## 12.1 我现在最推荐你采用哪套架构

推荐：

> 模块化单体架构：`chan.py` 作为结构计算内核，外面加“规则引擎 + 扫描调度 + 结果存储 + 解释层”，存储用 `PostgreSQL`，展示先用 `Streamlit` 或轻量 Web。

## 12.2 为什么

因为它在三个维度上最平衡：

1. 足够快能落地。
2. 足够稳能承载规则演进。
3. 足够清晰能支持后续升级到盘中扫描和 LLM 辅助。

## 12.3 第一阶段做到什么程度就够了

我建议第一阶段只做到：

1. 日终全 A 股扫描。
2. 日线规则为主，可预留分钟级接口。
3. 5 到 10 个原子条件。
4. YAML 规则组合。
5. 候选池结果落库。
6. 每只候选项输出结构化原因和简短说明。

这就已经是一个真实可用的 MVP。

## 12.4 哪些功能绝对不要一开始就做

1. 自动交易。
2. 自动下单。
3. 完整回测平台。
4. 自研复杂 DSL。
5. 微服务拆分。
6. 分布式任务队列。
7. 盘中全频扫描。
8. 让 LLM 直接负责命中判断。

## 12.5 下一步工程实现顺序应该是什么

顺序建议：

1. 先统一数据接入和股票池过滤。
2. 再封装 `chan.py` 结构输出接口。
3. 再实现规则引擎。
4. 再实现扫描任务。
5. 再做结果存储。
6. 再做展示。
7. 最后再加 LLM 解释。

# 13. 第一阶段实施路线（按优先级排序）

## P0：先把基础骨架立起来

1. 新建 `candidate_pool/` 模块化目录。
2. 实现 `UniverseProvider` 和 `MarketDataProvider`。
3. 实现 `ChanEngineAdapter` 与 `ChanSnapshotExtractor`。
4. 确定统一 `LevelSnapshot` 结构。

## P1：把规则引擎做对

1. 实现 `ConditionPlugin` 接口。
2. 先落地 5 个原子条件：
   `bsp_recent`
   `fx_recent`
   `new_bi_formed`
   `new_seg_formed`
   `zs_breakout`
3. 实现 `all` / `any` / `not` 组合器。
4. 实现 YAML 规则加载。

## P2：把扫描跑通

1. 做 `ScanJobRunner`。
2. 做按股票并行扫描。
3. 输出 `CandidateHit`。
4. 保存 `scan_job`、`candidate_hit`、`symbol_snapshot`。

## P3：把结果做成可用产品

1. 做候选池列表页。
2. 做股票详情页。
3. 展示命中规则、证据、结构摘要。
4. 接入图形查看入口。

## P4：加大模型辅助，但只做辅助

1. 对结构化结果做自然语言改写。
2. 增加自然语言规则草案生成。
3. 增加问答能力。

## P5：再考虑分钟级与盘中

1. 补分钟级数据源。
2. 处理未完成 K 线。
3. 做盘中扫描任务。
4. 增加快照增量更新。

# 14. 明确不建议现在做的东西

1. 不建议现在把 `chan.py` 改造成“大一统平台”。
2. 不建议现在围绕 README 里的 `cbsp`/模型层做架构设计，因为公开源码并不完整。
3. 不建议现在一开始就做数据库可视化规则编辑器。
4. 不建议现在设计过度通用的 DSL。
5. 不建议现在上微服务、消息队列、Kubernetes。
6. 不建议现在做自动交易闭环。
7. 不建议现在把大模型接到核心筛选判断链路里。
8. 不建议现在为了性能过早把全链路改造成复杂增量计算系统。

最后给一个最直接的结论：

> `chan.py` 很适合做你的“结构计算内核”，但不适合直接充当“候选池系统平台”；你真正该做的是在它上面搭一个模块化单体的候选池框架，而这个框架的核心不是 GUI，也不是 LLM，而是“规则引擎 + 扫描编排 + 结果留痕 + 结构化解释”。
