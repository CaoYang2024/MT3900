#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
USB Camera Hotplug → AAS
插 USB : 生成 AAS JSON + 上传 (Connected=true)
拔 USB : 自动发现 Submodel + PATCH Connected=false
"""

import os
import time
import glob
import signal
import threading
import subprocess
from pathlib import Path

from pyudev import Context, Monitor, MonitorObserver

from src.aas.generate_aas_from_config import build_aas
from src.aas.aas_manager import register_or_update_aas, mark_disconnected


# ===================== Camera REST API config =====================
API_PORT = "8000"
PROJECT_DIR = "/home/pi/Downloads/MT3900/src/drivers"   # <<< 改成你的 drivers 目录
server_proc = None

debounce_lock = threading.Lock()
start_stop_lock = threading.Lock()


# =================================================================
# Camera control
# =================================================================
def kill_uvicorn():
    subprocess.run(["pkill", "-f", "uvicorn"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def start_api(devnode: str):
    """启动 Camera REST API"""
    global server_proc
    with start_stop_lock:

        kill_uvicorn()  # 避免端口被占用

        env = os.environ.copy()
        env["CAM_DEV"] = devnode
        env["PORT"] = API_PORT

        print(f"🚀 Camera API started (dev={devnode})")

        server_proc = subprocess.Popen(
            ["python3", "-m", "uvicorn", "camera_api:app",
             "--host", "0.0.0.0", "--port", API_PORT, "--app-dir", PROJECT_DIR],
            env=env
        )


def stop_api():
    """关闭 Camera API"""
    global server_proc
    with start_stop_lock:
        if server_proc:
            print("🛑 Stop Camera API process")
            server_proc.send_signal(signal.SIGTERM)

            try:
                server_proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                server_proc.kill()

            server_proc = None
            time.sleep(0.2)


# =================================================================
# Utility
# =================================================================
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


# =================================================================
# USB hotplug handler
# =================================================================
def handle_event(device):
    global server_proc

    # 只处理 add / remove，不处理 bind/change
    if device.action not in ("add", "remove"):
        return

    # 防抖（过滤短时间多次触发）
    if not debounce_lock.acquire(blocking=False):
        return
    threading.Timer(0.6, debounce_lock.release).start()

    # ------- 设备节点 -------
    devnode = getattr(device, "device_node", None)
    if not devnode or not str(devnode).startswith("/dev/video"):
        vids = sorted(glob.glob("/dev/video*"))
        devnode = vids[0] if vids else None

    # ------- AAS ID ------
    serial = device.properties.get("ID_SERIAL_SHORT", "USB-Camera-Unknown") \
        if hasattr(device, "properties") else "USB-Camera-Unknown"

    vendor = device.properties.get("ID_VENDOR_FROM_DATABASE", "UnknownVendor") \
        if hasattr(device, "properties") else "UnknownVendor"

    model = device.properties.get("ID_MODEL_FROM_DATABASE", "USB-Camera") \
        if hasattr(device, "properties") else "USB-Camera"

    aas_id = f"urn:mt3900:usb:{serial}"
    ip = get_ip()

    # =================================================================
    # 插入摄像头：启动 API + 生成 AAS + 上传 JSON
    # =================================================================
    if device.action == "add":

        if server_proc is None:
            start_api(devnode)
        else:
            print(f"⏩ API already running, skip duplicate add event")

        cfg = {
            "id": aas_id,
            "sensor": {
                "name": model,
                "manufacturer": vendor,
                "type": "Camera",
                "datatype": "video"
            },
            "interface": {
                "ip": ip,
                "port": API_PORT,
                "connected": True
            }
        }

        aas_json = build_aas(cfg)           # 生成 AAS JSON
        register_or_update_aas(aas_json)    # 上传到 BaSyx


    # =================================================================
    # 拔出摄像头：停止 API + PATCH Connected=false
    # =================================================================
    elif device.action == "remove":
        stop_api()
        mark_disconnected(aas_id)
        print(f"🔌 Camera removed ({devnode})")


# =================================================================
# Main Entry (called by main.py)
# =================================================================
def run_hotplug():
    print("🔌 Plug & Play USB Camera → AAS")
    print("🔌 USB Camera Hotplug Monitor Started ...")

    # 检查当前系统里真正已连接的设备
    context = Context()

    for dev in context.list_devices(subsystem="video4linux"):
        if dev.device_node and "usb" in dev.sys_path.lower():
            fake = type("Fake", (), {})()
            fake.action = "add"
            fake.device_node = dev.device_node
            fake.properties = dev.properties
            handle_event(fake)

    monitor = Monitor.from_netlink(context)
    monitor.filter_by(subsystem="video4linux")

    observer = MonitorObserver(monitor, callback=handle_event)
    observer.start()

    while True:
        time.sleep(1)
