# camera_server.py
from fastapi import FastAPI, Response
from fastapi.responses import StreamingResponse, JSONResponse
from src.drivers.UsbCamera import CameraDriver
import socket

def get_pi_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    finally:
        s.close()
    return ip


app = FastAPI()

# 默认 /dev/video0，但可改
driver = CameraDriver("/dev/video0")


# ============================================================
# 服务器启动时启动 driver
# ============================================================

@app.on_event("startup")
def startup_event():
    driver.open()
    print("📸 Camera started.")
    print(f"🌐 Server accessible at: http://{get_pi_ip()}:8000")


# ============================================================
# 服务器关闭时释放 camera
# ============================================================
@app.on_event("shutdown")
def stop_camera():
    driver.close()
    print("🛑 Camera stopped.")


# ============================================================
# 返回单帧 JPEG
# ============================================================
@app.get("/frame")
def get_frame():
    jpg = driver.get_jpeg_frame()
    if jpg is None:
        return JSONResponse({"error": "Camera not ready"}, status_code=503)
    return Response(jpg, media_type="image/jpeg")


# ============================================================
# MJPEG video 流
# ============================================================
@app.get("/video")
def video_stream():
    return StreamingResponse(
        driver.mjpeg_stream(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )
