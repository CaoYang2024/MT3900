from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict
from datetime import datetime, timezone


@dataclass
class Measurement:
    """
    通用测量数据结构（这里用于视频帧）。
    """
    timestamp: str                # ISO8601，例如 "2025-10-23T12:34:56.789Z"
    data: bytes                   # 原始数据（这里存JPEG编码后的图像字节）
    meta: Dict[str, str]          # 元数据：width/height/format 等
    semantic_id: Optional[str] = None  # 语义ID（预留给 VSS/IEC61360）

    @staticmethod
    def now_iso() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
