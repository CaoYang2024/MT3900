from __future__ import annotations
import cv2
import time
import threading
from typing import Optional, Tuple, Generator, Dict
import numpy as np

from .base import DriverBase
from ..models.measurement import Measurement


def _probe_device_index(max_index: int = 10) -> Optional[int]:
    """
    自动探测可用的摄像头索引（0..max_index-1）。
    在 Windows/笔记本上通常是 0。
    """
    for i in range(max_index):
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)  # CAP_DSHOW 在 Windows 更稳定
        if cap.isOpened():
            ret, _ = cap.read()
            cap.release()
            if ret:
                return i
    return None


class USBCameraDriver(DriverBase):
    """
    简单的 USB 摄像头驱动（基于 OpenCV）。
    - 返回 JPEG 编码后的帧（bytes）
    - meta 里给出 width/height/format
    - 提供 iter_frames() 连续采集
    """

    def __init__(
        self,
        device_index: Optional[int] = None,
        width: int = 640,
        height: int = 480,
        fps: int = 30,
        jpeg_quality: int = 85,
        backend: int = cv2.CAP_DSHOW,  # Windows 建议 DSHOW；Linux 可尝试 CAP_V4L2
    ) -> None:
        self.device_index = device_index
        self.width = width
        self.height = height
        self.fps = fps
        self.jpeg_quality = jpeg_quality
        self.backend = backend

        self._cap: Optional[cv2.VideoCapture] = None
        self._last_frame_ts = 0.0
        self._frame_interval = 1.0 / max(1, fps)

    def open(self) -> None:
        if self.device_index is None:
            idx = _probe_device_index()
            if idx is None:
                raise RuntimeError("未找到可用的摄像头设备（尝试索引 0..9）")
            self.device_index = idx

        cap = cv2.VideoCapture(self.device_index, self.backend)
        if not cap.isOpened():
            raise RuntimeError(f"无法打开摄像头：index={self.device_index}")

        # 设置分辨率/帧率（部分设备可能不完全尊重）
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, float(self.width))
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, float(self.height))
        cap.set(cv2.CAP_PROP_FPS, float(self.fps))

        # 读取一次，确认可用
        ok, _ = cap.read()
        if not ok:
            cap.release()
            raise RuntimeError("摄像头打开但无法读取帧")

        self._cap = cap
        self._last_frame_ts = 0.0

    def _grab_encoded(self) -> Optional[Tuple[bytes, Dict[str, str]]]:
        assert self._cap is not None
        ok, frame = self._cap.read()
        if not ok or frame is None:
            return None

        # 统一为 BGR（OpenCV 默认），可按需做颜色空间转换
        h, w = frame.shape[:2]

        # JPEG 编码
        encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), int(self.jpeg_quality)]
        ok, buf = cv2.imencode(".jpg", frame, encode_params)
        if not ok:
            return None

        meta = {
            "width": str(w),
            "height": str(h),
            "format": "jpeg",
        }
        return (buf.tobytes(), meta)

    def read(self) -> Optional[Measurement]:
        """
        同步读取一帧；若要固定 FPS，可以 sleep。
        """
        if self._cap is None:
            raise RuntimeError("请先调用 open()")

        # 控制采样间隔（简单限速）
        now = time.perf_counter()
        dt = now - self._last_frame_ts
        if dt < self._frame_interval:
            time.sleep(self._frame_interval - dt)
        self._last_frame_ts = time.perf_counter()

        out = self._grab_encoded()
        if out is None:
            return None
        data, meta = out
        return Measurement(
            timestamp=Measurement.now_iso(),
            data=data,
            meta=meta,
            semantic_id=None,  # 以后接 VSS/IEC 61360 时再填
        )

    def iter_frames(self) -> Generator[Measurement, None, None]:
        """
        连续读取帧（阻塞式）。
        """
        while True:
            m = self.read()
            if m is None:
                break
            yield m

    def close(self) -> None:
        if self._cap is not None:
            try:
                self._cap.release()
            finally:
                self._cap = None
