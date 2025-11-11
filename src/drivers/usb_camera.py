# src/drivers/usb_camera.py
import time
import threading
from typing import Optional
import cv2
import numpy as np


class USBCameraDriver:
    def __init__(self):
        self._cap: Optional[cv2.VideoCapture] = None
        self._dev = None
        self._last: Optional[np.ndarray] = None
        self._thread = None
        self._running = False
        self._lock = threading.Lock()

    def open(self, dev: str, width: int = 0, height: int = 0) -> bool:
        dev = dev if dev.startswith("/dev/") else f"/dev/{dev}"
        with self._lock:
            if self._cap and self._dev == dev:
                return True

            self._close_locked()
            cap = cv2.VideoCapture(dev)
            if not cap.isOpened():
                return False

            if width > 0: cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            if height > 0: cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

            self._cap = cap
            self._dev = dev
            self._running = True
            self._thread = threading.Thread(target=self._reader, daemon=True)
            self._thread.start()
            return True

    def _reader(self):
        while self._running and self._cap:
            ok, frame = self._cap.read()
            if ok:
                with self._lock:
                    self._last = frame
            else:
                time.sleep(0.02)

        if self._cap:
            self._cap.release()
            self._cap = None

    def get_frame(self) -> Optional[np.ndarray]:
        with self._lock:
            return None if self._last is None else self._last.copy()

    def close(self):
        with self._lock:
            self._close_locked()

    def _close_locked(self):
        self._running = False
        th, cap = self._thread, self._cap
        self._thread = None
        self._cap = None
        self._last = None
        self._dev = None

        if th and th.is_alive():
            th.join(timeout=1.0)
        if cap:
            cap.release()
