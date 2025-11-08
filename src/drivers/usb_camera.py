# src/drivers/usb_camera_driver.py
from fastapi import FastAPI
from starlette.responses import StreamingResponse
import subprocess
import threading
import cv2
import uvicorn


class USBCameraDriver:
    def __init__(self, port: int = 8000):
        self.port = port
        self.ip = "0.0.0.0"   # or detect local IP
        self.running = False

    def _camera_loop(self):
        self.cap = cv2.VideoCapture(0)
        self.running = True
        while self.running:
            ok, frame = self.cap.read()
            if not ok:
                continue
            _, jpeg = cv2.imencode(".jpg", frame)
            self.frame_bytes = jpeg.tobytes()
        self.cap.release()

    def get_app(self):
        app = FastAPI()

        @app.get("/stream")
        def stream():
            return StreamingResponse(
                self._frame_gen(),
                media_type="multipart/x-mixed-replace; boundary=frame"
            )

        @app.on_event("startup")
        def startup():
            threading.Thread(target=self._camera_loop, daemon=True).start()

        @app.on_event("shutdown")
        def shutdown():
            self.running = False

        return app

    def _frame_gen(self):
        while self.running:
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" +
                self.frame_bytes +
                b"\r\n"
            )

    def start(self):
        """启动 FastAPI Camera server"""
        print("🎥 [USBCameraDriver] Starting FastAPI server...")
        app = self.get_app()
        self.server = subprocess.Popen(
            ["python3", "-m", "uvicorn", "src.drivers.usb_camera_driver:driver_app", "--host", "0.0.0.0", f"--port={self.port}"],
        )

    def stop(self):
        """停止 Camera server"""
        print("🛑 [USBCameraDriver] Stopping Camera server...")
        self.running = False
        if self.cap:
            self.cap.release()
