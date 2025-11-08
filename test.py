from fastapi import FastAPI, Response
from fastapi.responses import StreamingResponse
from src.drivers.csi_camera import camera

app = FastAPI()

@app.get("/capture")  # ✅ 抓取当前最新 JPEG
def capture():
    frame = camera.get_frame()
    return Response(content=frame, media_type="image/jpeg")


@app.get("/stream")   # ✅ 生成 MJPEG streaming
def stream():
    def mjpeg_generator():
        while True:
            frame = camera.get_frame()
            if frame:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
                )

    return StreamingResponse(
        mjpeg_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )
