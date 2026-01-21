#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Camera Driver (Clean Version)
=============================
Features:
1. Connects to AAS Server to fetch configuration (Resolution, FPS).
2. Auto-detects local Container IP.
3. Updates AAS (PUT) with the real stream URLs.
4. Serves raw MJPEG stream via FastAPI (No HUD/Overlay).
"""

import os
import sys
import cv2
import time
import base64
import requests
import socket
import threading
import logging
from urllib.parse import urlparse
from contextlib import asynccontextmanager
from fastapi import FastAPI, Response
from fastapi.responses import StreamingResponse
import uvicorn
from zeroconf import Zeroconf, ServiceInfo

# ---------------------------------------------------------
# Logging Setup
# ---------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("camera_driver")

# ---------------------------------------------------------
# Configuration (Env Variables)
# ---------------------------------------------------------
AAS_SERVER = os.environ.get("AAS_SERVER")
AAS_ID = os.environ.get("AAS_ID")
CAMERA_DEV = os.environ.get("CAMERA_DEV")

if not AAS_ID or not AAS_SERVER:
    logger.critical("❌ Critical Error: AAS_ID or AAS_SERVER not set.")
    sys.exit(1)

# ---------------------------------------------------------
# Network Helper: Get Container IP
# ---------------------------------------------------------
def get_local_ip():
    """Detects the outgoing IP address of the container."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def b64url(s: str):
    """Base64 URL-safe encoding for BaSyx ID usage."""
    return base64.urlsafe_b64encode(s.encode()).decode().rstrip("=")

# ---------------------------------------------------------
# Camera Class (Raw Video)
# ---------------------------------------------------------
class VideoCamera:
    def __init__(self, devnode, resolution=None):
        self.devnode = devnode
        self.resolution = resolution
        self.cap = None
        self.lock = threading.Lock()

    def open(self):
        logger.info(f"🎥 Opening camera device: {self.devnode}")
        self.cap = cv2.VideoCapture(self.devnode)
        if not self.cap.isOpened():
            raise RuntimeError(f"Could not open video device {self.devnode}")
        
        if self.resolution:
            try:
                w, h = map(int, self.resolution.lower().split("x"))
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
                logger.info(f"📐 Resolution set to: {w}x{h}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to set resolution: {e}")

    def close(self):
        if self.cap:
            self.cap.release()
            logger.info("🎯 Camera resource released.")

    def get_frame(self):
        """Reads a frame and returns JPEG bytes (No Overlay)."""
        with self.lock:
            if self.cap and self.cap.isOpened():
                ret, frame = self.cap.read()
                if ret:
                    # Encode directly to JPEG without modification
                    return cv2.imencode(".jpg", frame)[1].tobytes()
        return None

# Global Instance
camera_instance = None
zeroconf = None

# ---------------------------------------------------------
# AAS Logic: Resolve & Update
# ---------------------------------------------------------
def resolve_aas_config():
    """Queries AAS for config and returns (config_dict, encoded_submodel_id)."""
    try:
        # 1. Get Shell
        enc_shell = b64url(AAS_ID)
        shell_url = f"{AAS_SERVER}/shells/{enc_shell}"
        logger.info(f"🔌 Querying AAS: {shell_url}")
        
        resp = requests.get(shell_url, timeout=5)
        resp.raise_for_status()
        shell_data = resp.json()
        shell = shell_data.get("result", shell_data)

        # 2. Find 'AssetInterface' Submodel
        asset_sm_iri = None
        for sm in shell.get("submodels", []):
            keys = sm.get("keys", [])
            if keys and "AssetInterface" in keys[0]["value"]:
                asset_sm_iri = keys[0]["value"]
                break
        
        if not asset_sm_iri:
            logger.critical("❌ 'AssetInterface' submodel not found in AAS.")
            sys.exit(1)

        # 3. Get Elements
        enc_sm = b64url(asset_sm_iri)
        sm_url = f"{AAS_SERVER}/submodels/{enc_sm}/submodel-elements"
        resp = requests.get(sm_url, timeout=5)
        elems_raw = resp.json().get("result", [])
        
        config = {e["idShort"]: e["value"] for e in elems_raw}
        return config, enc_sm

    except Exception as e:
        logger.critical(f"❌ Failed to resolve AAS config: {e}")
        sys.exit(1)

def update_aas_endpoints(enc_sm, ip, port):
    """PUTs the valid stream URLs back to the AAS."""
    base_url = f"http://{ip}:{port}"
    updates = {
        "FrameURL": f"{base_url}/frame",
        "StreamURL": f"{base_url}/video"
    }
    
    logger.info(f"🔄 Updating AAS Endpoints to: {base_url}")

    for id_short, url_val in updates.items():
        url = f"{AAS_SERVER}/submodels/{enc_sm}/submodel-elements/{id_short}"
        body = {
            "idShort": id_short,
            "modelType": "Property",
            "valueType": "xs:string",
            "value": url_val
        }
        try:
            r = requests.put(url, json=body, timeout=2)
            if r.status_code < 300:
                logger.info(f"   ✅ Updated {id_short}")
            else:
                logger.warning(f"   ⚠️ Failed {id_short}: {r.status_code}")
        except Exception as e:
            logger.error(f"   ❌ Update error: {e}")

# ---------------------------------------------------------
# Hardware & mDNS
# ---------------------------------------------------------
def find_video_device():
    if CAMERA_DEV: return CAMERA_DEV
    for i in range(10):
        if os.path.exists(f"/dev/video{i}"): return f"/dev/video{i}"
    logger.critical("❌ No /dev/video* device found.")
    sys.exit(1)

def start_mdns(port):
    global zeroconf
    try:
        ip = get_local_ip()
        hostname = socket.gethostname().split('.')[0]
        service_name = f"{hostname}-cam._camera._tcp.local."
        info = ServiceInfo(
            "_camera._tcp.local.", service_name,
            addresses=[socket.inet_aton(ip)], port=port,
            properties={"aas_id": AAS_ID}
        )
        zeroconf = Zeroconf()
        zeroconf.register_service(info)
        logger.info(f"📢 mDNS Service Registered: {service_name}")
    except Exception as e:
        logger.error(f"⚠️ mDNS Error: {e}")

def stop_mdns():
    if zeroconf: zeroconf.close()

# ---------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global camera_instance
    config = app.state.config
    
    devnode = find_video_device()
    camera_instance = VideoCamera(devnode, config.get("Resolution"))
    camera_instance.open()
    
    start_mdns(app.state.port)
    yield
    # Shutdown
    stop_mdns()
    if camera_instance: camera_instance.close()

def create_app(config, port):
    app = FastAPI(lifespan=lifespan)
    app.state.config = config
    app.state.port = port

    def generate_frames():
        fps = int(config.get("FPS", 15))
        delay = 1.0 / fps
        while True:
            if not camera_instance or not camera_instance.cap.isOpened(): break
            jpg_bytes = camera_instance.get_frame()
            if jpg_bytes:
                yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpg_bytes + b"\r\n")
            time.sleep(delay)

    @app.get("/frame")
    def frame():
        if not camera_instance: return Response(status_code=500)
        jpg = camera_instance.get_frame()
        return Response(content=jpg, media_type="image/jpeg") if jpg else Response(status_code=503)

    @app.get("/video")
    def video():
        return StreamingResponse(generate_frames(), media_type="multipart/x-mixed-replace; boundary=frame")
    
    return app

# ---------------------------------------------------------
# Main Execution
# ---------------------------------------------------------
def main():
    # 1. Get Config from AAS
    config, enc_sm_id = resolve_aas_config()
    
    # 2. Determine Port
    try:
        parsed = urlparse(config.get("FrameURL", ""))
        port = parsed.port if parsed.port else 8000
    except:
        port = 8000
        
    # 3. Detect IP and Update AAS
    local_ip = get_local_ip()
    logger.info(f"📍 Container IP: {local_ip}")
    update_aas_endpoints(enc_sm_id, local_ip, port)
    
    # 4. Start Server
    app = create_app(config, port)
    logger.info(f"🚀 Starting Camera Server on 0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")

if __name__ == "__main__":
    main()