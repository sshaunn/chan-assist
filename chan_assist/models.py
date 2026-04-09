"""
数据模型定义。

定义 scan_run / scan_result / scan_signal 的轻量数据结构。
用于应用层数据传递，不做 ORM 映射。
"""
from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime

# scan_result.status 合法值
RESULT_STATUS_HIT = "hit"
RESULT_STATUS_NO_HIT = "no_hit"
RESULT_STATUS_ERROR = "error"
VALID_RESULT_STATUSES = {RESULT_STATUS_HIT, RESULT_STATUS_NO_HIT, RESULT_STATUS_ERROR}

# scan_run.status 合法值
RUN_STATUS_RUNNING = "running"
RUN_STATUS_SUCCESS = "success"
RUN_STATUS_PARTIAL_SUCCESS = "partial_success"
RUN_STATUS_FAILED = "failed"
VALID_RUN_STATUSES = {RUN_STATUS_RUNNING, RUN_STATUS_SUCCESS, RUN_STATUS_PARTIAL_SUCCESS, RUN_STATUS_FAILED}


@dataclass
class ScanRun:
    """一次批量扫描任务"""
    started_at: str
    market: str
    strategy_name: str
    status: str = RUN_STATUS_RUNNING
    finished_at: Optional[str] = None
    params_json: Optional[str] = None
    total_symbols: int = 0
    hit_count: int = 0
    error_count: int = 0
    processed_count: int = 0
    notes: Optional[str] = None
    id: Optional[int] = None

    def __post_init__(self):
        if self.status not in VALID_RUN_STATUSES:
            raise ValueError(
                f"ScanRun.status 必须是 {VALID_RUN_STATUSES} 之一，收到: '{self.status}'"
            )


@dataclass
class ScanResult:
    """单股扫描结果"""
    symbol: str
    name: str
    status: str  # hit / no_hit / error
    scan_time: str = ""
    signal_code: Optional[str] = None
    signal_desc: Optional[str] = None
    score: Optional[float] = None
    error_msg: Optional[str] = None
    raw_snapshot_json: Optional[str] = None
    signals: List[dict] = field(default_factory=list)
    run_id: Optional[int] = None
    id: Optional[int] = None

    def __post_init__(self):
        if self.status not in VALID_RESULT_STATUSES:
            raise ValueError(
                f"ScanResult.status 必须是 {VALID_RESULT_STATUSES} 之一，收到: '{self.status}'"
            )
        if not self.scan_time:
            self.scan_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class ScanSignal:
    """命中信号明细"""
    signal_type: str
    signal_level: Optional[str] = None
    signal_value: Optional[str] = None
    extra_json: Optional[str] = None
    result_id: Optional[int] = None
    id: Optional[int] = None
