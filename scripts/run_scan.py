#!/usr/bin/env python3
"""
CLI 入口：驱动 chan_assist 执行扫描任务。

职责：
- 接收命令行参数
- 构造 ScanConfig
- 调用 scan_service.run_scan()

禁止在此写业务逻辑、策略判定或直接操作数据库。
"""
import argparse
import sys


def parse_args(argv=None):
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="chan-assist 扫描入口")
    parser.add_argument("--market", default="A", help="市场标识 (default: A)")
    parser.add_argument("--db-path", default="data/chan_assist.db", help="数据库路径")
    parser.add_argument("--limit", type=int, default=None, help="小样本模式：限制股票数")
    parser.add_argument("--symbols", nargs="*", default=None, help="指定股票列表")
    parser.add_argument("--commit-every", type=int, default=50, help="批量提交频率")
    parser.add_argument("--strategy", default="chan_default", help="策略名称")
    parser.add_argument("--tushare-token", default="", help="TuShare API token")
    parser.add_argument("--target-types", nargs="*", default=None,
                        help="目标买点类型 (如: 2 2s 3a 3b)，不指定则全类型")
    parser.add_argument("--filter-config", default=None,
                        help="过滤配置 JSON 文件路径")
    return parser.parse_args(argv)


def main(argv=None):
    """主入口"""
    args = parse_args(argv)

    from chan_assist.config import load_config
    from chan_assist.scan_service import run_scan

    # 加载过滤配置
    filters = {}
    file_target_types = []
    if args.filter_config:
        import json
        with open(args.filter_config, "r", encoding="utf-8") as f:
            file_data = json.load(f)
        # target_bsp_types 从配置文件提取，不混入 filters dict
        file_target_types = file_data.pop("target_bsp_types", [])
        filters = file_data

    # CLI --target-types 优先，否则用配置文件中的
    target_types = args.target_types or file_target_types or []

    config = load_config(
        db_path=args.db_path,
        market=args.market,
        limit=args.limit,
        symbols=args.symbols,
        commit_every=args.commit_every,
        strategy_name=args.strategy,
        tushare_token=args.tushare_token,
        target_bsp_types=target_types,
        filters=filters,
    )

    result = run_scan(config)
    print(f"扫描完成: {result}")


if __name__ == "__main__":
    main()
