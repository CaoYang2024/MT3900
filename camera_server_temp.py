
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
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" +
            frame_bytes +
            b"\r\n"
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
