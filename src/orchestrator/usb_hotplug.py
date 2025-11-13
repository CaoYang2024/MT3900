#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import glob
import signal
import threading
import subprocess
from pathlib import Path

import requests
from pyudev import Context, Monitor, MonitorObserver

# AAS Manager
from src.aas.aas_manager import (
    register_or_update_aas,
    mark_connected,
    mark_disconnected,
)
from src.utils.aas_discovery import discover_properties_for_shell
from src.aas.generate_aas_from_config import build_aas


# ===================== Camera REST API config =====================
API_PORT = "8000"
DRIVER_DIR = "/home/pi/Downloads/MT3900/src/drivers"   
server_proc = None

debounce_lock = threading.Lock()
start_stop_lock = threading.Lock()


# ================================================================
# Camera API control
# ================================================================
def kill_uvicorn():
    subprocess.run(
        ["pkill", "-f", "uvicorn"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )


def start_api(devnode: str):
    global server_proc
    with start_stop_lock:
        kill_uvicorn()

        env = os.environ.copy()
        env["CAM_DEV"] = devnode
        env["PORT"] = API_PORT

        print(f"🚀 Starting Camera API (dev={devnode})")

        server_proc = subprocess.Popen(
            [
                "python3", "-m", "uvicorn",
                "camera_api:app",
                "--host", "0.0.0.0",
                "--port", API_PORT,
                "--app-dir", DRIVER_DIR
            ],
            env=env
        )


def stop_api():
    global server_proc
    with start_stop_lock:
        if server_proc:
            print("🛑 Stopping Camera API")
            server_proc.send_signal(signal.SIGTERM)
            try:
                server_proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                server_proc.kill()

            server_proc = None
            time.sleep(0.2)


# ================================================================
# Utility Functions
# ================================================================
def get_ip() -> str:
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "localhost"
    finally:
        s.close()


def aas_exists(aas_id: str) -> bool:
    """Check if AAS already uploaded."""
    try:
        r = requests.get("http://192.168.137.1:8081/shells")
        for sh in r.json():
            if sh["id"] == aas_id:
                return True
    except:
        pass
    return False


def select_primary_camera():
    """选择真正能打开的摄像头节点，而不是错误的 /dev/video1."""
    vids = sorted(glob.glob("/dev/video*"))
    if not vids:
        return None

    import cv2
    for dev in vids:
        cap = cv2.VideoCapture(dev)
        if cap.isOpened():
            cap.release()
            return dev

    return None


def put_stream_url(aas_id: str, url: str):
    """PUT StreamURL back to AAS."""
    print(f"🔧 Updating StreamURL for {aas_id}")

    props = discover_properties_for_shell("http://192.168.137.1:8081", aas_id)

    if "AssetInterface" not in props:
        print("❌ StreamURL update failed: no AssetInterface")
        return

    ai = props["AssetInterface"]
    if "StreamURL" not in ai:
        print("❌ StreamURL not found")
        return

    put_url = ai["StreamURL"]

    body = {
        "idShort": "StreamURL",
        "modelType": "Property",
        "valueType": "xs:anyURI",
        "value": url
    }

    print(f"➡ PUT {put_url}")
    requests.put(put_url, json=body, headers={"Content-Type": "application/json"})
    print("✅ StreamURL updated")


# ================================================================
# USB Hotplug Handler
# ================================================================
def handle_event(device):
    global server_proc

    if device.action not in ("add", "remove"):
        return

    # 防抖
    if not debounce_lock.acquire(blocking=False):
        return
    threading.Timer(0.6, debounce_lock.release).start()

    # 选择可用摄像头
    devnode = select_primary_camera()

    # AAS ID
    serial = device.properties.get("ID_SERIAL_SHORT", "USB-Camera-Unknown")
    aas_id = f"urn:mt3900:usb:{serial}"

    ip = get_ip()

    # ============================================================
    # USB 插入事件
    # ============================================================
    if device.action == "add":
        print(f"🔵 Camera added → {devnode}")

        if devnode and server_proc is None:
            start_api(devnode)

        elif server_proc:
            print("⏩ Camera API already running")

        # 第一次插入 → upload AAS 1 次
        if not aas_exists(aas_id):
            print(f"📦 Uploading AAS for {aas_id}")

            cfg = {
                "id": aas_id,
                "sensor": {
                    "name": "USB Camera",
                    "manufacturer": "UnknownVendor",
                    "type": "Camera"
                },
                "interface": {
                    "ip": ip,
                    "port": API_PORT,
                    "connected": "true"
                }
            }

            aas_json = build_aas(cfg)
            register_or_update_aas(aas_json)
        else:
            print("📦 AAS exists → skip upload")

        # PUT Connected = true
        mark_connected(aas_id)

        # PUT StreamURL
        stream = f"http://{ip}:{API_PORT}/stream"
        put_stream_url(aas_id, stream)


    # ============================================================
    # USB 拔出事件
    # ============================================================
    elif device.action == "remove":
        print("🔴 Camera removed")
        stop_api()
        mark_disconnected(aas_id)


# ================================================================
# Main Entry with startup check
# ================================================================
def run_hotplug():
    print("🔌 USB Camera Hotplug Monitor Started...")

    # ====== 启动时检查是否已经连接摄像头 ======
    existing = select_primary_camera()
    if existing:
        print(f"📷 Camera already connected on startup → {existing}")

        fake = type("Fake", (), {})()
        fake.action = "add"
        fake.device_node = existing
        fake.properties = {}
        handle_event(fake)
    else:
        print("🔍 No camera detected on startup")

    # ====== 监听 USB hotplug ======
    context = Context()
    monitor = Monitor.from_netlink(context)
    monitor.filter_by(subsystem="video4linux")

    observer = MonitorObserver(monitor, callback=handle_event)
    observer.start()

    while True:
        time.sleep(1)
