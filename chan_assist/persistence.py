"""
持久化写入逻辑。

负责 scan_run / scan_result / scan_signal 的落库操作。

职责边界：
- db.py 负责连接与 schema
- models.py 负责数据结构
- persistence.py 负责写入与更新
"""
import sqlite3
from chan_assist.models import ScanResult, ScanSignal, RESULT_STATUS_HIT, RESULT_STATUS_ERROR


def create_scan_run(
    conn: sqlite3.Connection,
    started_at: str,
    market: str,
    strategy_name: str,
    params_json: str | None = None,
    total_symbols: int = 0,
) -> int:
    """创建一条 scan_run 记录，返回 run_id。"""
    cursor = conn.execute(
        "INSERT INTO scan_run (started_at, market, strategy_name, params_json, total_symbols) "
        "VALUES (?, ?, ?, ?, ?)",
        (started_at, market, strategy_name, params_json, total_symbols),
    )
    conn.commit()
    return cursor.lastrowid


def insert_scan_result(conn: sqlite3.Connection, run_id: int, result: ScanResult) -> int:
    """
    写入一条 scan_result，返回 result_id。

    每只被扫描的股票都必须调用此函数，无论 hit / no_hit / error。
    error 状态必须携带非空 error_msg。
    """
    if result.status == RESULT_STATUS_ERROR and not result.error_msg:
        raise ValueError(
            f"status='error' 时 error_msg 不可为空，symbol='{result.symbol}'"
        )
    cursor = conn.execute(
        "INSERT INTO scan_result "
        "(run_id, symbol, name, scan_time, status, signal_code, signal_desc, score, error_msg, raw_snapshot_json) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            run_id,
            result.symbol,
            result.name,
            result.scan_time,
            result.status,
            result.signal_code,
            result.signal_desc,
            result.score,
            result.error_msg,
            result.raw_snapshot_json,
        ),
    )
    return cursor.lastrowid


def insert_scan_signal(conn: sqlite3.Connection, result_id: int, signal: ScanSignal) -> int:
    """写入一条 scan_signal，返回 signal_id。只有 hit 时才允许调用。"""
    row = conn.execute(
        "SELECT status FROM scan_result WHERE id = ?", (result_id,)
    ).fetchone()
    if row is None:
        raise ValueError(f"result_id={result_id} 不存在")
    if row["status"] != RESULT_STATUS_HIT:
        raise ValueError(
            f"scan_signal 只能写给 hit 结果，result_id={result_id} 的 status='{row['status']}'"
        )
    cursor = conn.execute(
        "INSERT INTO scan_signal (result_id, signal_type, signal_level, signal_value, extra_json) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            result_id,
            signal.signal_type,
            signal.signal_level,
            signal.signal_value,
            signal.extra_json,
        ),
    )
    return cursor.lastrowid


def persist_one_result(conn: sqlite3.Connection, run_id: int, result: ScanResult) -> int:
    """
    写入单股完整结果：scan_result + 若 hit 则追加 scan_signal。

    返回 result_id。
    """
    result_id = insert_scan_result(conn, run_id, result)

    if result.status == RESULT_STATUS_HIT:
        for sig_dict in result.signals:
            signal = ScanSignal(**sig_dict) if isinstance(sig_dict, dict) else sig_dict
            insert_scan_signal(conn, result_id, signal)

    return result_id


def update_scan_run_summary(
    conn: sqlite3.Connection,
    run_id: int,
    status: str | None = None,
    finished_at: str | None = None,
    total_symbols: int | None = None,
    hit_count: int | None = None,
    error_count: int | None = None,
    processed_count: int | None = None,
) -> None:
    """更新 scan_run 的汇总统计。只更新传入的非 None 字段。"""
    updates = []
    values = []

    if status is not None:
        updates.append("status = ?")
        values.append(status)
    if finished_at is not None:
        updates.append("finished_at = ?")
        values.append(finished_at)
    if total_symbols is not None:
        updates.append("total_symbols = ?")
        values.append(total_symbols)
    if hit_count is not None:
        updates.append("hit_count = ?")
        values.append(hit_count)
    if error_count is not None:
        updates.append("error_count = ?")
        values.append(error_count)
    if processed_count is not None:
        updates.append("processed_count = ?")
        values.append(processed_count)

    if not updates:
        return

    values.append(run_id)
    sql = f"UPDATE scan_run SET {', '.join(updates)} WHERE id = ?"
    conn.execute(sql, values)
    conn.commit()
