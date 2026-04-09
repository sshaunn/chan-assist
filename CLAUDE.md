# chan-assist — 基于缠论的 A 股扫描辅助系统

## 项目概述

chan-assist 是基于 [chan.py](https://github.com/Vespa314/chan.py) 缠论引擎构建的 A 股扫描辅助系统。对全 A 或指定股票池进行买卖点扫描，产出可审计、可复盘、可落库的候选结果。

- **Python 版本要求**: >= 3.11
- **数据源**: TuShare（需要 API token）
- **持久化**: SQLite
- **上游缠论引擎**: `chan.py/` 子目录（fork 自 Vespa314/chan.py，尽量少改）

## 项目结构

```
chan-assist/
├── scripts/
│   ├── run_scan.py              # CLI 扫描入口
│   └── run_sample_charts.py     # 缠论图表生成
│
├── chan_assist/                  # 应用层（独立顶层包）
│   ├── config.py                # ScanConfig 配置
│   ├── db.py                    # SQLite 连接与建表
│   ├── models.py                # ScanRun/ScanResult/ScanSignal 数据模型
│   ├── persistence.py           # 落库写入逻辑
│   ├── stock_pool.py            # 股票池获取与过滤
│   └── scan_service.py          # 扫描编排 + run_one_symbol 单股边界
│
├── strategy/                    # 策略层（薄入口 + 内部模块）
│   ├── chan_strategy.py          # 唯一对外入口 evaluate_signal()
│   ├── _accessor.py             # chan.py 数据读取隔离层
│   ├── _zs_patch.py             # 补充中枢检测（chan.py 遗漏的三笔中枢）
│   ├── _bsp_filters.py          # 买卖点过滤规则（b2回踩/震荡中枢/位置有效性）
│   └── _bsp_modify.py           # BSP 内存修改器（仅画图场景使用）
│
├── chan.py/                     # 上游缠论引擎（尽量不改）
│   ├── Chan.py                  # CChan 核心入口
│   ├── ChanConfig.py            # CChanConfig 配置
│   ├── DataAPI/TushareAPI.py    # TuShare 数据接口
│   ├── Plot/PlotDriver.py       # matplotlib 画图驱动
│   ├── Bi/                      # 笔
│   ├── Seg/                     # 线段
│   ├── ZS/                      # 中枢
│   ├── BuySellPoint/            # 买卖点
│   └── ...
│
├── tests/
│   ├── unit/                    # 单元测试
│   ├── integration/             # 集成测试
│   └── regression/              # 回归测试
│
├── _legacy/                     # 旧实现存档（不在运行路径中）
├── data/                        # 运行数据（SQLite、图表、扫描结果）
└── doc/chanpy/                  # 架构文档、任务计划、进度日志
```

## 四层架构

| 层 | 目录 | 职责 | 禁止 |
|----|------|------|------|
| CLI | `scripts/` | 命令行入口，参数解析 | 业务逻辑、策略、DB 操作 |
| 应用层 | `chan_assist/` | 扫描编排、配置、股票池、持久化 | 策略判定、直接改 chan.py |
| 策略层 | `strategy/` | 薄策略入口、信号判定 | 配置管理、DB、股票池、批量调度 |
| 引擎层 | `chan.py/` | 缠论计算（笔段中枢买卖点） | 尽量不改，外层包裹解决 |

## 核心概念（缠论术语）

- **K线(KLine)**: 原始/合并后的 K 线单元
- **笔(Bi)**: 由顶底分型确定的最小趋势单元
- **线段(Seg)**: 由笔构成的更大级别趋势
- **中枢(ZhongShu/ZS)**: 至少三笔重叠区间，核心分析结构
- **买卖点(BSP)**: 1类/2类/3类买卖点（b1/b2/b3a/b1p/b2s/b3b）

## 策略过滤规则

`strategy/` 内置三条买卖点过滤规则，过滤 chan.py 原始输出中的假买点：

| 规则 | 函数 | 作用 |
|------|------|------|
| 回踩比过滤 | `b2_retrace_check` | b2 回踩比超过 60% 判定为假 b2 |
| 震荡中枢过滤 | `b2_in_new_zs` | b2 落在 b1 参与构成的中枢内，属于震荡 |
| 回踩位置过滤 | `b2_must_enter_zs` | b2 低点未进入中枢有效区间 [中轴, 上沿] |

`_zs_patch.py` 补充检测 chan.py 遗漏的短线段三笔中枢。

调用顺序固定写死在 `chan_strategy.py` 中，不可动态编排。

## 数据库 Schema

三表结构，SQLite 存储：

- **scan_run** — 一次批量扫描任务（status: running/success/partial_success/failed）
- **scan_result** — 每只股票一条（status: hit/no_hit/error，全量落库）
- **scan_signal** — 命中信号明细（仅 hit 时写入）

## 冻结参数

- `divergence_rate = 0.8`（已冻结，不可擅自修改）
- `min_zs_cnt`：由 ChanConfig 内部默认值控制，不在应用层硬编码

## 常用命令

```bash
# 安装
pip install -e .
pip install -e ".[dev]"

# 小样本扫描（指定股票）
python scripts/run_scan.py --tushare-token TOKEN --symbols 000001 600036 000002

# 限制数量扫描
python scripts/run_scan.py --tushare-token TOKEN --limit 20 --commit-every 10

# 全量扫描
python scripts/run_scan.py --tushare-token TOKEN --commit-every 50

# 生成缠论图表（30只样本）
python scripts/run_sample_charts.py --tushare-token TOKEN

# 运行测试
python -m pytest tests/ -v

# 查看扫描结果
sqlite3 data/chan_assist.db "SELECT symbol, name, signal_code FROM scan_result WHERE status='hit' ORDER BY id DESC LIMIT 20;"
```

## 代码风格

- chan.py 内部类名使用 `C` 前缀（`CChan`, `CKLine_List`）
- chan_assist 使用标准 Python dataclass
- strategy 内部模块使用 `_` 前缀（`_accessor.py`, `_zs_patch.py`）
- 测试分三类：unit / integration / regression

## 关键约束

- `chan_assist/` 必须保持独立顶层包，不回塞 chan.py
- `stock_pool.py` 必须独立文件
- `scan_service.py` 中 `run_one_symbol()` 是单股执行稳定边界
- `strategy/chan_strategy.py` 是唯一对外策略入口，保持薄层
- `strategy/` 下不允许 `engine/`、`bsp/`、`zs/` 子包
- `scan_result` 全量落库（hit + no_hit + error）
- `scan_signal` 只记录 hit 明细
- error 状态必须带 `error_msg`
