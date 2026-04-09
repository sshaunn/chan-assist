"""
股票池获取与过滤。

负责获取可扫描的股票列表，支持：
- 全 A 股票列表获取（通过 TuShare）
- 基础过滤（ST / 北交所 / B股 / CDR）
- 可配置过滤链（市值 / 行业 / 问询函等）
- 测试模式小样本截取
- 指定股票列表覆盖默认池

职责边界：
- 只负责"给出可扫描的股票列表"
- 不负责策略判定、持久化、批量调度
"""
from typing import Optional, List


def normalize_symbols(symbols: List[str]) -> List[str]:
    """
    标准化 symbol 列表：去空值、去空格、去重、保序。
    """
    seen = set()
    result = []
    for s in symbols:
        if not s or not isinstance(s, str):
            continue
        s = s.strip()
        if not s:
            continue
        if s not in seen:
            seen.add(s)
            result.append(s)
    return result


def apply_basic_filters(stocks: List[dict]) -> List[dict]:
    """
    基础过滤：去除 ST、北交所、B股、CDR。

    输入: [{"symbol": "000001", "name": "平安银行"}, ...]
    输出: 过滤后的列表
    """
    filtered = []
    for stock in stocks:
        name = stock.get("name", "")
        symbol = stock.get("symbol", "")

        # 去 ST
        if "ST" in name.upper():
            continue

        # 去北交所 (8x, 43x)
        if symbol.startswith("8") or symbol.startswith("43"):
            continue

        # 去 B 股 (200x, 900x)
        if symbol.startswith("200") or symbol.startswith("900"):
            continue

        # 去 CDR (920x)
        if symbol.startswith("920"):
            continue

        filtered.append(stock)
    return filtered


# ============================================================
# 可配置过滤函数
# 每个函数签名: (pool: List[dict], **params) -> List[dict]
# ============================================================

def filter_market_cap(pool: List[dict], min: float = 0, max: float = float("inf"),
                      tushare_token: str = "") -> List[dict]:
    """
    按总市值过滤（单位：亿元）。
    需要 TuShare daily_basic 的 total_mv 字段（单位：万元）。
    """
    if not tushare_token:
        return pool

    import tushare as ts
    ts.set_token(tushare_token)
    pro = ts.pro_api()

    symbols = [s["symbol"] for s in pool]
    # 批量查最新市值
    try:
        df = pro.daily_basic(ts_code="", fields="ts_code,total_mv")
        if df is None or df.empty:
            return pool
        # total_mv 单位是万元，转亿元
        mv_map = {}
        for _, row in df.iterrows():
            code = row["ts_code"].split(".")[0]
            mv_map[code] = row["total_mv"] / 10000  # 万 → 亿
    except Exception:
        return pool  # 查询失败不过滤

    min_val = min
    max_val = max
    result = []
    for stock in pool:
        mv = mv_map.get(stock["symbol"])
        if mv is None:
            result.append(stock)  # 查不到市值的保留
            continue
        if min_val <= mv <= max_val:
            result.append(stock)
    return result


def filter_exclude_industries(pool: List[dict], industries: List[str] = None) -> List[dict]:
    """
    按行业排除。stock 需要有 "industry" 字段。
    """
    if not industries:
        return pool
    exclude_set = set(industries)
    return [s for s in pool if s.get("industry", "") not in exclude_set]


def filter_inquiry(pool: List[dict], days: int = 30) -> List[dict]:
    """
    排除近 N 天内收到问询函/监管函/关注函/警示函的股票。
    数据源：AkShare stock_notice_report（仅此处使用）。
    """
    if days <= 0:
        return pool

    from datetime import datetime, timedelta
    try:
        import akshare as ak
    except ImportError:
        return pool  # akshare 未安装则跳过

    # 收集近 N 天有问询/监管函的股票代码（只查工作日，跳过周末）
    flagged_codes = set()
    end = datetime.now()
    start = end - timedelta(days=days)

    try:
        d = start
        while d <= end:
            if d.weekday() < 5:  # 跳过周末
                date_str = d.strftime("%Y%m%d")
                df = ak.stock_notice_report(symbol="全部", date=date_str)
                if df is not None and len(df) > 0:
                    inquiry = df[df["公告标题"].str.contains("问询|关注函|监管函|警示函", na=False)]
                    for code in inquiry["代码"].tolist():
                        flagged_codes.add(str(code))
            d += timedelta(days=1)
    except Exception:
        return pool  # 查询失败不过滤

    return [s for s in pool if s["symbol"] not in flagged_codes]


# ============================================================
# 过滤注册表：config key → 函数
# 写死在代码中，不做动态发现
# ============================================================

FILTER_REGISTRY = {
    "market_cap": filter_market_cap,
    "exclude_industries": filter_exclude_industries,
    "inquiry_days": filter_inquiry,
}


def apply_filters(pool: List[dict], filters_config: dict, tushare_token: str = "") -> List[dict]:
    """
    按配置依次执行可选过滤函数。

    filters_config 示例:
        {
            "market_cap": {"min": 50, "max": 800},
            "exclude_industries": {"industries": ["银行", "保险"]},
            "inquiry_days": {"days": 30},
        }
    """
    for name, params in filters_config.items():
        fn = FILTER_REGISTRY.get(name)
        if fn is None:
            continue  # 未知过滤项跳过

        if params is True:
            kwargs = {}
        elif isinstance(params, dict):
            kwargs = dict(params)
        else:
            kwargs = {"days": params} if name == "inquiry_days" else {}

        # 自动注入 tushare_token（需要的函数会用，不需要的会忽略）
        if "tushare_token" not in kwargs and name == "market_cap":
            kwargs["tushare_token"] = tushare_token

        pool = fn(pool, **kwargs)

    return pool


# ============================================================
# 主入口
# ============================================================

def _fetch_a_share_list(tushare_token: str) -> List[dict]:
    """
    通过 TuShare 获取全 A 股票列表（含行业字段）。

    返回: [{"symbol": "000001", "name": "平安银行", "industry": "银行"}, ...]
    """
    import tushare as ts

    ts.set_token(tushare_token)
    pro = ts.pro_api()
    df = pro.stock_basic(
        exchange="", list_status="L",
        fields="ts_code,symbol,name,industry",
    )
    stocks = []
    for _, row in df.iterrows():
        stocks.append({
            "symbol": row["symbol"],
            "name": row["name"],
            "industry": row.get("industry", ""),
        })
    return stocks


def get_stock_pool(
    market: str = "A",
    limit: Optional[int] = None,
    symbols: Optional[List[str]] = None,
    tushare_token: Optional[str] = None,
    filters_config: Optional[dict] = None,
) -> List[dict]:
    """
    获取股票池。

    返回: [{"symbol": "000001", "name": "平安银行", "industry": "银行"}, ...]

    参数:
        market: 市场标识（当前仅支持 "A"）
        limit: 限制返回数量（小样本模式）
        symbols: 指定股票列表（覆盖默认池）
        tushare_token: TuShare API token（默认模式必须提供）
        filters_config: 可选过滤配置 dict
    """
    if symbols:
        # 白名单模式：用指定 symbol 列表
        clean = normalize_symbols(symbols)
        if not clean:
            return []
        pool = [{"symbol": s, "name": ""} for s in clean]
    else:
        # 默认模式：获取全 A 并过滤
        if market != "A":
            raise ValueError(f"当前仅支持 market='A'，收到: '{market}'")
        if not tushare_token:
            raise ValueError("默认模式需要提供 tushare_token")
        raw = _fetch_a_share_list(tushare_token)
        pool = apply_basic_filters(raw)

        # 应用可配置过滤链
        if filters_config:
            pool = apply_filters(pool, filters_config, tushare_token=tushare_token)

    # 小样本截取
    if limit is not None and limit > 0:
        pool = pool[:limit]

    return pool
