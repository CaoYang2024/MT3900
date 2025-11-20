# src/drivers/camera_api.py
import os
import cv2
import time
import threading
from fastapi import FastAPI, Response, HTTPException
from starlette.responses import StreamingResponse

driver = {
    "cap": None,
    "dev": None,
    "frame": None,
    "running": False,
    "thread": None,
}


def camera_reader():
    """Capture frames in background"""
    while driver["running"] and driver["cap"]:
        ok, frame = driver["cap"].read()
        if ok:
            driver["frame"] = frame
        else:
            time.sleep(0.02)


def open_camera(dev: str):
    print(f"🔧 Opening camera: {dev}")

    cap = cv2.VideoCapture(dev)
    if not cap.isOpened():
        print(f"❌ Cannot open camera: {dev}")
        return False

    driver["cap"] = cap
    driver["dev"] = dev
    driver["running"] = True
    driver["thread"] = threading.Thread(target=camera_reader, daemon=True)
    driver["thread"].start()
    return True


def close_camera():
    print("🛑 Closing camera")
    driver["running"] = False
    if driver["thread"]:
        driver["thread"].join()
    if driver["cap"]:
        driver["cap"].release()


app = FastAPI()


@app.on_event("startup")
def startup_event():
    """
    When FastAPI starts, read CAM_DEV from environment.
    But DO NOT crash if camera is not open (hotplug scenario).
    """
    dev = os.getenv("CAM_DEV")
    driver["dev"] = dev

    if not dev:
        print("⚠️ No CAM_DEV set, not opening camera.")
        return

    if not open_camera(dev):
        print(f"⚠️ Camera not ready yet: {dev} (continue without camera)")
        return  # ✅ 不再 raise RuntimeError


@app.on_event("shutdown")
def shutdown_event():
    close_camera()


@app.get("/frame")
def frame():
    if driver["frame"] is None:
        raise HTTPException(503, "Camera not ready")

    ok, buf = cv2.imencode(".jpg", driver["frame"])
    return Response(buf.tobytes(), media_type="image/jpeg")


@app.get("/stream")
def stream():
    def gen():
        while True:
            if driver["frame"] is None:
                time.sleep(0.01)
                continue
            ok, buf = cv2.imencode(".jpg", driver["frame"])
            yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" +
                   buf.tobytes() + b"\r\n")
    return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=frame")
