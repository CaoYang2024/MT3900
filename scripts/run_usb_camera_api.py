from __future__ import annotations
import os
import time
import threading
from typing import Optional, Dict, Generator
from pathlib import Path
from fastapi import FastAPI, Response, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse, PlainTextResponse

# 你的 USB 相机驱动（按你当前项目结构）
from src.drivers.usb_camera import USBCameraDriver

# -------------------------------
# 配置
# -------------------------------
CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", "1"))   # 你说外置 USB 是 1
DEFAULT_ENABLED = os.getenv("CAMERA_ENABLED", "1") in ("1", "true", "True")
WIDTH = int(os.getenv("CAMERA_WIDTH", "640"))
HEIGHT = int(os.getenv("CAMERA_HEIGHT", "480"))
FPS = int(os.getenv("CAMERA_FPS", "10"))
JPEG_QUALITY = int(os.getenv("CAMERA_JPEG_QUALITY", "85"))

# -------------------------------
# 后台抓帧器
# -------------------------------
class FrameGrabber:
    """
    根据 enabled 开关管理相机资源。开启则后台线程循环读取最新帧。
    """
    def __init__(self):
        self.enabled: bool = DEFAULT_ENABLED
        self.device_index: int = CAMERA_INDEX
        self.driver: Optional[USBCameraDriver] = None
        self.thread: Optional[threading.Thread] = None
        self.stop_evt = threading.Event()
        self.lock = threading.Lock()
        self.latest_frame: Optional[bytes] = None
        self.latest_meta: Dict[str, str] = {}
        self.running: bool = False

    def _loop(self):
        assert self.driver is not None
        self.running = True
        try:
            while not self.stop_evt.is_set():
                m = self.driver.read()
                if m is None:
                    # 小憩再试，避免空转
                    time.sleep(0.05)
                    continue
                with self.lock:
                    self.latest_frame = m.data
                    self.latest_meta = m.meta
        finally:
            self.running = False

    def _open_driver(self):
        self.driver = USBCameraDriver(
            device_index=self.device_index,
            width=WIDTH, height=HEIGHT, fps=FPS, jpeg_quality=JPEG_QUALITY
        )
        self.driver.open()

    def _close_driver(self):
        try:
            if self.driver is not None:
                self.driver.close()
        finally:
            self.driver = None

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.stop_evt.clear()
        # 打开相机
        self._open_driver()
        # 起线程
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_evt.set()
        if self.thread:
            self.thread.join(timeout=2.0)
        self.thread = None
        self._close_driver()
        with self.lock:
            self.latest_frame = None
            self.latest_meta = {}

    def set_enabled(self, flag: bool):
        if flag == self.enabled:
            return
        self.enabled = flag
        if self.enabled:
            self.start()
        else:
            self.stop()

    def get_latest_jpeg(self) -> Optional[bytes]:
        with self.lock:
            return self.latest_frame

    def get_meta(self) -> Dict[str, str]:
        with self.lock:
            return dict(self.latest_meta)

grabber = FrameGrabber()

# 按开关初始化
if grabber.enabled:
    try:
        grabber.start()
    except Exception as e:
        # 启动失败也不崩溃，可通过 API 再试
        print(f"[WARN] Camera start failed on boot: {e}")

# -------------------------------
# FastAPI 应用
# -------------------------------
app = FastAPI(title="USB Camera Service", version="0.1.0")

@app.get("/health")
def health():
    return {"ok": True, "enabled": grabber.enabled, "running": grabber.running}

@app.get("/camera/status")
def camera_status():
    return {
        "enabled": grabber.enabled,
        "running": grabber.running,
        "device_index": grabber.device_index,
        "meta": grabber.get_meta(),
        "width": WIDTH,
        "height": HEIGHT,
        "fps": FPS,
    }

@app.put("/camera/enable")
def camera_enable(payload: Dict[str, bool]):
    """
    传 {"enabled": true/false} 切换开关。
    """
    enabled = payload.get("enabled")
    if enabled is None:
        raise HTTPException(status_code=400, detail="Missing 'enabled' boolean")
    try:
        grabber.set_enabled(bool(enabled))
        return {"enabled": grabber.enabled}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/camera/frame")
def camera_frame():
    """
    返回最新一帧 JPEG（如果未启用或还没抓到帧 -> 404）。
    """
    if not grabber.enabled:
        raise HTTPException(status_code=409, detail="Camera disabled")
    data = grabber.get_latest_jpeg()
    if not data:
        raise HTTPException(status_code=404, detail="No frame available yet")
    return Response(content=data, media_type="image/jpeg")

@app.get("/camera/stream")
def camera_stream():
    """
    简易 MJPEG 流。浏览器可直接打开；注意是 multipart/x-mixed-replace。
    """
    if not grabber.enabled:
        raise HTTPException(status_code=409, detail="Camera disabled")

    boundary = "frame"
    headers = {
        "Age": "0",
        "Cache-Control": "no-cache, private",
        "Pragma": "no-cache",
        "Content-Type": f"multipart/x-mixed-replace; boundary=--{boundary}",
    }

    def gen() -> Generator[bytes, None, None]:
        while True:
            if not grabber.enabled:
                break
            frame = grabber.get_latest_jpeg()
            if frame:
                yield (
                    f"--{boundary}\r\n"
                    "Content-Type: image/jpeg\r\n"
                    f"Content-Length: {len(frame)}\r\n\r\n"
                ).encode("utf-8") + frame + b"\r\n"
            else:
                time.sleep(0.05)

    return StreamingResponse(gen(), headers=headers)

@app.post("/camera/reopen")
def camera_reopen():
    """
    如果驱动异常，可手动重启（在 enabled=True 下）。
    """
    if not grabber.enabled:
        raise HTTPException(status_code=409, detail="Camera disabled")
    try:
        grabber.stop()
        time.sleep(0.2)
        grabber.start()
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def root():
    return PlainTextResponse("USB Camera Service. See /health /camera/status /camera/frame /camera/stream /camera/enable")
