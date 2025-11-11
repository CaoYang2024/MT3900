#!/usr/bin/env python3

import sys
from pathlib import Path

# ✅ 确保可以 import src.*
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi import FastAPI
from src.drivers.usb_camera import USBCameraDriver
import uvicorn

print("✅ [run_usb_camera_api.py] Loaded")

driver = USBCameraDriver(device_index=0)
app = driver.get_app()

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        lifespan="on"
    )
