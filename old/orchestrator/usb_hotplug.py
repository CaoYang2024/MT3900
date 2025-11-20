#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
USB Camera Orchestrator
- hotplug detection
- startup auto-detection
- AAS generate
- AAS upload
- mark connected/disconnected
- launch MJPEG FastAPI server
"""

import os
import time
import threading
import subprocess
from pathlib import Path
import pyudev
import yaml

from src.aas.generate_aas_from_config import build_aas
from src.aas.aas_manager import (
    register_or_update_aas,
    mark_connected,
    mark_disconnected
)

from src.drivers.usb_camera import USBCameraDriver

driver = USBCameraDriver()

API_PORT = 8000
CAMERA_SERVER_DIR = "/home/pi/Downloads/MT3900/src/camera_server"
CONFIG_PATH = "/home/pi/Downloads/MT3900/src/aas/config_camera.yaml"

debounce_lock = threading.Lock()
last_event_time = 0
DEBOUNCE_MS = 800

server_proc = None
start_stop_lock = threading.Lock()


# --------------------------------------------------------------
# Kill uvicorn
# --------------------------------------------------------------
def kill_uvicorn():
    subprocess.run(["pkill", "-f", "uvicorn"],
                   stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)


# --------------------------------------------------------------
# Try open a camera
# --------------------------------------------------------------
def is_valid_camera_node(dev):
    try:
        cap = USBCameraDriver()
        ok = cap.open(dev)
        cap.close()
        return ok
    except:
        return False


# --------------------------------------------------------------
# Find real camera
# --------------------------------------------------------------
def find_real_camera():
    videos = sorted(Path("/dev").glob("video*"))
    for v in videos:
        dev = str(v)
        if is_valid_camera_node(dev):
            return dev
    return None


# --------------------------------------------------------------
# Start API server
# --------------------------------------------------------------
def start_api(devnode: str):
    global server_proc

    with start_stop_lock:
        kill_uvicorn()

        print(f"📷 Starting Camera API for {devnode}")

        env = os.environ.copy()
        env["DEVICE_PATH"] = devnode

        server_proc = subprocess.Popen(
            [
                "uvicorn",
                "camera_server.main:app",
                "--host", "0.0.0.0",
                "--port", str(API_PORT),
            ],
            cwd=CAMERA_SERVER_DIR,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        print(f"🚀 Camera Stream: http://<PI-IP>:{API_PORT}/stream\n")


def stop_api():
    print("🛑 Stopping Camera API ...")
    kill_uvicorn()


# ==============================================================
# Hotplug handler
# ==============================================================
def handle_hotplug(action: str, devnode: str):
    global last_event_time

    # debounce
    with debounce_lock:
        now = time.time() * 1000
        if now - last_event_time < DEBOUNCE_MS:
            return
        last_event_time = now

    if "video" not in devnode:
        return

    if action == "add":
        print(f"🔔 EVENT: add → {devnode}")

        cam = find_real_camera()
        if not cam:
            print("❌ No valid camera found")
            return

        if not driver.open(cam):
            print("❌ Failed to open camera driver")
            return

        cfg = yaml.safe_load(Path(CONFIG_PATH).read_text())
        aas_json = build_aas(cfg)
        register_or_update_aas(aas_json)
        mark_connected(cfg["id"])

        start_api(cam)

    elif action == "remove":
        print(f"🔔 EVENT: remove → {devnode}")

        cfg = yaml.safe_load(Path(CONFIG_PATH).read_text())

        driver.close()
        stop_api()
        mark_disconnected(cfg["id"])


# ==============================================================
# Monitor Loop
# ==============================================================
def monitor_loop():
    print("👀 Watching for USB cameras...")
    print(f"➡ MJPEG Stream: http://<PI-IP>:{API_PORT}/stream\n")

    # ========== Startup auto-detection ==========
    existing = find_real_camera()
    if existing:
        print(f"📸 Camera already connected → {existing}")
        handle_hotplug("add", existing)

    # ========== Hotplug events ==========
    context = pyudev.Context()
    monitor = pyudev.Monitor.from_netlink(context)
    monitor.filter_by(subsystem="video4linux")

    observer = pyudev.MonitorObserver(
        monitor,
        callback=lambda device: handle_hotplug(device.action, device.device_node),
    )

    observer.start()

    while True:
        time.sleep(1)


# ==============================================================
# Entry
# ==============================================================
def main():
    print("\n========================================")
    print("      🚀 USB Camera Orchestrator")
    print("========================================\n")

    monitor_loop()


if __name__ == "__main__":
    main()
