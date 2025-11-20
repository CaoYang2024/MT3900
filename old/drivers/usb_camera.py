# src/drivers/usb_camera.py

import cv2
import time
import threading
from typing import Optional
import numpy as np


class USBCameraDriver:
    """Low-level USB camera driver: open/close/read frames"""
    def __init__(self):
        self._cap: Optional[cv2.VideoCapture] = None
        self._dev = None
        self._thread = None
        self._last: Optional[np.ndarray] = None
        self._running = False

    def open(self, dev: str, width: int = 0, height: int = 0) -> bool:
        dev = dev if dev.startswith("/dev/") else f"/dev/{dev}"
        if self._cap and self._dev == dev:
            return True

        self.close()
        cap = cv2.VideoCapture(dev)
        if not cap.isOpened():
            return False

        if width > 0: cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        if height > 0: cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

        self._cap, self._dev, self._running = cap, dev, True
        self._thread = threading.Thread(target=self._reader, daemon=True)
        self._thread.start()
        return True

    def _reader(self):
        while self._running and self._cap:
            ok, frame = self._cap.read()
            if ok: self._last = frame
            else: time.sleep(0.02)

        if self._cap:
            self._cap.release()
            self._cap = None

    def get_frame(self): return None if self._last is None else self._last.copy()

    def close(self):
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1)
        if self._cap: self._cap.release()
        self._cap, self._thread = None, None
