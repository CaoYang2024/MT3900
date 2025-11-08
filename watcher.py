#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
USB Camera Hotplug + 自动启动 FastAPI MJPEG Streaming Server
单文件版本，不需要脚本、udev 或 systemd。

依赖：
    pip install pyudev fastapi uvicorn opencv-python

运行：
    python3 auto_usb_camera_server.py
"""

import pyudev
import subprocess
import textwrap
import os


# =======================================================================
# FastAPI 摄像头服务器代码（会在插入摄像头时动态创建）
# =======================================================================

CAMERA_SERVER_CODE = textwrap.dedent("""
    from fastapi import FastAPI
    from starlette.responses import StreamingResponse
    import cv2, threading, uvicorn

    app = FastAPI()
    cap = None
    running = False


    def camera_loop():
        global cap, running
        cap = cv2.VideoCapture(0)
        running = True


    def gen_frames():
        global cap, running
        while running:
            ok, frame = cap.read()
            if not ok:
                continue

            _, jpeg = cv2.imencode(".jpg", frame)
            frame_bytes = jpeg.tobytes()

            yield (
                b"--frame\\r\\n"
                b"Content-Type: image/jpeg\\r\\n\\r\\n" +
                frame_bytes +
                b"\\r\\n"
            )


    @app.on_event("startup")
    def start():
        thread = threading.Thread(target=camera_loop, daemon=True)
        thread.start()


    @app.on_event("shutdown")
    def stop():
        global running
        running = False
        if cap:
            cap.release()


    @app.get("/stream")
    def stream():
        return StreamingResponse(gen_frames(),
            media_type="multipart/x-mixed-replace; boundary=frame"
        )


    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8000)
""")


# =======================================================================
# 热插拔监听，可启动/关闭 FastAPI server
# =======================================================================

class USBCameraAutoService:
    def __init__(self):
        self.process = None
        self.context = pyudev.Context()

    def start_server(self):
        """插入摄像头 → 启动 FastAPI"""
        if self.process is not None:
            return  # 已经启动，无需重复启动

        print("✅ USB Camera detected — Starting FastAPI server...")

        # 动态写入一个摄像头服务脚本
        with open("camera_server_temp.py", "w") as f:
            f.write(CAMERA_SERVER_CODE)

        self.process = subprocess.Popen(
            ["python3", "camera_server_temp.py"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

    def stop_server(self):
        """拔出摄像头 → 停止 FastAPI"""
        if self.process:
            print("❌ USB Camera removed — Stopping server...")
            self.process.terminate()
            self.process.wait()
            self.process = None

            # 清理临时文件
            if os.path.exists("camera_server_temp.py"):
                os.remove("camera_server_temp.py")

    def monitor(self):
        """监听 USB 摄像头热插拔"""
        monitor = pyudev.Monitor.from_netlink(self.context)
        monitor.filter_by("video4linux")

        print("👀 Monitoring USB Camera. Plug/unplug to test.")
        print("➡ 打开浏览器访问: http://<树莓派IP>:8000/stream\n")

        for action, device in monitor:
            print(f"[DEBUG] event={action}, device={device.device_node}")

            if action in ("add", "bind"):      # 物理插入 + 驱动绑定
                self.start_server()

            elif action in ("unbind", "remove"):  # 驱动解绑 + 物理拔出
                self.stop_server()



# =======================================================================
# Entry point
# =======================================================================

if __name__ == "__main__":
    try:
        service = USBCameraAutoService()
        service.monitor()
    except KeyboardInterrupt:
        print("🛑 Exit")
