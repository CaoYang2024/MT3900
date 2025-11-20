#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Camera Driver v3 — AAS AUTO-CONFIG
----------------------------------
✔ AAS_ID 从环境变量读取
✔ 自动从 AAS AssetInterface 读取:
    - StreamURL (HTTP)
    - FrameURL
    - Resolution
    - FPS
✔ 自动找到摄像头设备 devnode (通过 /dev/video*)
✔ 启动 FastAPI 视频服务：
    /frame → 单帧JPEG
    /video → MJPEG streaming
"""

import os
import sys
import cv2
import time
import base64
import requests
from fastapi import FastAPI, Response
from fastapi.responses import StreamingResponse
import uvicorn
import threading


AAS_SERVER = os.environ.get("AAS_SERVER", "http://192.168.137.1:8081")
AAS_ID = os.environ.get("AAS_ID", None)


# ============================================================
# Base64 URL Encode
# ============================================================
def b64url(s: str):
    return base64.urlsafe_b64encode(s.encode()).decode().rstrip("=")


# ============================================================
# 从 AAS 获取摄像头接口参数
# ============================================================
def resolve_camera_interface():
    if not AAS_ID:
        print("❌ ERROR: AAS_ID not provided.")
        sys.exit(1)

    print(f"🔧 Camera Driver launched with AAS_ID = {AAS_ID}")

    enc_shell = b64url(AAS_ID)
    shell_url = f"{AAS_SERVER}/shells/{enc_shell}"

    shell = requests.get(shell_url).json()
    if isinstance(shell, list):
        shell = shell[0]

    asset_sm_iri = None
    for sm in shell["submodels"]:
        iri = sm["keys"][0]["value"]
        if iri.endswith("/AssetInterface"):
            asset_sm_iri = iri

    if not asset_sm_iri:
        print("❌ ERROR: AssetInterface not found in AAS")
        sys.exit(1)

    enc_sm = b64url(asset_sm_iri)

    sm = requests.get(f"{AAS_SERVER}/submodels/{enc_sm}").json()
    elems = sm["submodelElements"]

    frame_url = None
    stream_url = None
    resolution = None
    fps = None

    for e in elems:
        if e["idShort"] == "FrameURL":
            frame_url = e["value"]
        elif e["idShort"] == "StreamURL":
            stream_url = e["value"]
        elif e["idShort"] == "Resolution":
            resolution = e["value"]
        elif e["idShort"] == "FPS":
            fps = int(e["value"])

    print(f"📸 FrameURL  = {frame_url}")
    print(f"📺 StreamURL = {stream_url}")
    print(f"📐 Resolution = {resolution}")
    print(f"🎞 FPS = {fps}")

    return frame_url, stream_url, resolution, fps


# ============================================================
# 自动选择摄像头 /dev/video*
# ============================================================
def find_video_device():
    for idx in range(10):
        dev = f"/dev/video{idx}"
        if os.path.exists(dev):
            print(f"🎥 Camera device found: {dev}")
            return dev
    print("❌ No camera device found (/dev/video*)")
    sys.exit(1)


# ============================================================
# FastAPI 视频服务器
# ============================================================
def create_app(devnode, fps):
    app = FastAPI()

    cap = cv2.VideoCapture(devnode)
    if not cap.isOpened():
        print("❌ ERROR: Cannot open camera")
        sys.exit(1)

    # 设置 FPS
    cap.set(cv2.CAP_PROP_FPS, fps)

    def generate_mjpeg():
        while True:
            ret, frame = cap.read()
            if not ret:
                continue

            _, jpeg = cv2.imencode(".jpg", frame)
            frame_bytes = jpeg.tobytes()

            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" +
                frame_bytes +
                b"\r\n"
            )
            time.sleep(1 / fps)

    @app.get("/frame")
    def get_frame():
        ret, frame = cap.read()
        if not ret:
            return Response(status_code=500)

        _, jpeg = cv2.imencode(".jpg", frame)
        return Response(content=jpeg.tobytes(), media_type="image/jpeg")

    @app.get("/video")
    def video_stream():
        return StreamingResponse(
            generate_mjpeg(),
            media_type="multipart/x-mixed-replace; boundary=frame"
        )

    return app


# ============================================================
# MAIN
# ============================================================
def main():
    frame_url, stream_url, resolution, fps = resolve_camera_interface()

    devnode = find_video_device()
    app = create_app(devnode, fps)

    # 解析端口号
    # FrameURL = http://IP:PORT/frame
    port = int(frame_url.split(":")[2].split("/")[0])
    print(f"\n🚀 Starting camera API on port {port} ...\n")

    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
