# chan-assist

基于 [chan.py](https://github.com/Vespa314/chan.py) 缠论引擎的 A 股扫描辅助系统。对全 A 或指定股票池进行买卖点扫描，产出可审计、可复盘、可落库的候选结果。

## 环境要求

- Python >= 3.11
- TuShare API token（从 https://tushare.pro 注册获取）

## 安装

```bash
cd chan-assist
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
pip install -e .
pip install -e ".[dev]"
```

## 运行扫描

### 小样本模式（推荐首次验证）

```bash
python scripts/run_scan.py \
  --tushare-token YOUR_TOKEN \
  --symbols 000001 600036 000002 \
  --commit-every 10
```

### 限制数量模式

```bash
python scripts/run_scan.py \
  --tushare-token YOUR_TOKEN \
  --limit 10 \
  --commit-every 10
```

### 全量扫描

```bash
python scripts/run_scan.py \
  --tushare-token YOUR_TOKEN \
  --commit-every 50
```

### 只筛特定买点类型

```bash
# 只要 2 买和 3 买
python scripts/run_scan.py \
  --tushare-token YOUR_TOKEN \
  --limit 100 \
  --target-types 2 2s 3a 3b
```

### 使用过滤配置文件

```bash
# 创建过滤配置
cat > filters.json << 'EOF'
{
    "exclude_industries": {"industries": ["银行", "保险"]},
    "market_cap": {"min": 50, "max": 800},
    "target_bsp_types": ["3a", "3b"]
}
EOF

python scripts/run_scan.py \
  --tushare-token YOUR_TOKEN \
  --filter-config filters.json \
  --limit 100
```

### CLI 参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--market` | `A` | 市场标识 |
| `--db-path` | `data/chan_assist.db` | SQLite 数据库路径 |
| `--limit` | 无 | 限制扫描股票数 |
| `--symbols` | 无 | 指定股票列表（空格分隔） |
| `--commit-every` | `50` | 每 N 只股票提交一次事务 |
| `--strategy` | `chan_default` | 策略名称 |
| `--tushare-token` | 空 | TuShare API token |
| `--target-types` | 无 | 目标买点类型（如 2 2s 3a 3b），不指定则全类型 |
| `--filter-config` | 无 | 过滤配置 JSON 文件路径 |

### 可用过滤条件

| 配置 key | 参数 | 说明 |
|----------|------|------|
| `market_cap` | `{"min": 50, "max": 800}` | 总市值区间过滤（亿元） |
| `exclude_industries` | `{"industries": ["银行"]}` | 排除行业 |
| `inquiry_days` | `{"days": 30}` | 排除近 N 天有问询函/监管函的股票 |
| `target_bsp_types` | `["2", "3a", "3b"]` | 目标买点类型 |

## 查看结果

```bash
sqlite3 data/chan_assist.db
```

```sql
-- 查看命中结果
SELECT symbol, name, signal_code, signal_desc
FROM scan_result WHERE run_id = 1 AND status = 'hit';

-- 查看命中信号明细
SELECT r.symbol, s.signal_type, s.signal_value
FROM scan_signal s
JOIN scan_result r ON s.result_id = r.id
WHERE r.run_id = 1;

-- 验证统计闭合
SELECT
  (SELECT COUNT(*) FROM scan_result WHERE run_id = 1) AS result_count,
  (SELECT total_symbols FROM scan_run WHERE id = 1) AS total_symbols,
  (SELECT COUNT(*) FROM scan_result WHERE run_id = 1 AND status = 'hit') AS hits,
  (SELECT COUNT(*) FROM scan_result WHERE run_id = 1 AND status = 'no_hit') AS no_hits,
  (SELECT COUNT(*) FROM scan_result WHERE run_id = 1 AND status = 'error') AS errors;
```

## 生成缠论图表

```bash
# 生成 30 只样本图表
python scripts/run_sample_charts.py --tushare-token YOUR_TOKEN

# 只生成前 10 只
python scripts/run_sample_charts.py --tushare-token YOUR_TOKEN --count 10
```

图表包含：K 线、笔、线段、中枢、买卖点标记、MACD 副图。输出到 `data/charts/`。

## 策略过滤规则

内置三条买卖点过滤规则，自动过滤假买点：

| 规则 | 作用 | 触发条件 |
|------|------|----------|
| `b2_retrace_check` | 回踩比过滤 | b2/b2s 回踩比超过 60% |
| `b2_in_new_zs` | 震荡中枢过滤 | b2 落在 b1 参与构成的中枢内 |
| `b2_must_enter_zs` | 回踩位置过滤 | b2 低点未进入中枢有效区间 |

补充中枢检测（`_zs_patch.py`）会自动检测 chan.py 遗漏的短线段三笔中枢。

## 运行测试

```bash
python -m pytest tests/ -v

# 按类型
python -m pytest tests/unit/ -v
python -m pytest tests/integration/ -v
python -m pytest tests/regression/ -v
```

## 项目结构

```
scripts/           CLI 入口（run_scan.py, run_sample_charts.py）
chan_assist/        应用层（配置、DB、模型、持久化、股票池、扫描编排）
strategy/          策略层（薄入口 chan_strategy.py + 内部过滤模块）
chan.py/            缠论引擎（上游 fork，尽量不改）
tests/             测试（unit / integration / regression）
```
