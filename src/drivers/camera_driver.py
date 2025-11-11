# src/camera_api.py
from fastapi import FastAPI, Response, HTTPException
from starlette.responses import StreamingResponse
import os, time, cv2, glob

from src.drivers.usb_camera import USBCameraDriver


def get_local_ip():
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "localhost"
    finally:
        s.close()
    return ip
app = FastAPI(title="USB Camera REST API")

CAM_DEV = os.getenv("CAM_DEV")  # 由 orchestrator 动态指定
FPS = int(os.getenv("FPS", "15"))

camera = USBCameraDriver()


@app.on_event("startup")
def startup():
    dev = CAM_DEV or first_camera()
    if dev and camera.open(dev):
        ip = get_local_ip()
        print(f"\n✅ Camera opened: {dev}")
        print(f"📌 MJPEG stream URL:   http://{ip}:8000/stream")
        print(f"📌 Single frame URL:   http://{ip}:8000/frame")
        print(f"📌 Health check:       http://{ip}:8000/health\n")
    else:
        print(f"⚠️ Camera not ready (CAM_DEV={CAM_DEV})")


@app.get("/frame")
def frame():
    img = camera.get_frame()
    if img is None:
        raise HTTPException(503, "Camera not ready")

    ok, buf = cv2.imencode(".jpg", img)
    return Response(buf.tobytes(), media_type="image/jpeg")


@app.get("/stream")
def stream():
    def gen():
        while True:
            img = camera.get_frame()
            if img is not None:
                ok, buf = cv2.imencode(".jpg", img)
                yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n")
            time.sleep(1.0 / FPS)

    return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=frame")


def first_camera():
    devs = sorted(glob.glob("/dev/video*"))
    return devs[0] if devs else None
