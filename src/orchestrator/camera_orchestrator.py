#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Camera Orchestrator
- USB 插入 → 自动生成 AAS → 上传 BaSyx → 启动 FastAPI 摄像头服务
- USB 拔出 → 停止 FastAPI → delete AAS
- 不使用 PUT，不使用 Connected 属性
"""

import subprocess
import threading
import time

import pyudev

from src.aas.aas_build import (
    read_camera_caps,
    get_local_ip,
    build_aas_from_auto,
)
from src.aas.aas_client import (
    register_or_update_aas,
    delete_aas,
)

# ============================================================
# GLOBAL STATE
# ============================================================

API_PORT = 8000
server_proc = None
current_aas_id = None
lock = threading.Lock()


# ============================================================
# UTILS
# ============================================================

def camera_info_from_device(dev) -> dict:
    props = dev.properties
    return {
        "devnode": dev.device_node,
        "vendor": props.get("ID_VENDOR", "UnknownVendor"),
        "model": props.get("ID_MODEL", "UnknownModel"),
        "serial": props.get("ID_SERIAL_SHORT", ""),
    }


def start_camera_server():
    global server_proc
    if server_proc is not None and server_proc.poll() is None:
        print("🔵 Camera API already running, skip start.")
        return

    print("🚀 Starting FastAPI camera server ...")
    server_proc = subprocess.Popen(
        ["uvicorn", "src.drivers.server:app", "--host", "0.0.0.0", "--port", str(API_PORT)]
    )
    print(f"✅ Camera API started on http://0.0.0.0:{API_PORT}")


def stop_camera_server():
    global server_proc

    if server_proc is None:
        print("🔵 Camera API not running.")
        return

    if server_proc.poll() is not None:
        server_proc = None
        return

    print("🛑 Stopping FastAPI camera server ...")
    server_proc.terminate()
    try:
        server_proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        server_proc.kill()

    server_proc = None
    print("✅ Camera API stopped.")


def is_usb_capture_device(dev) -> bool:
    if dev.subsystem != "video4linux":
        return False
    props = dev.properties
    if props.get("ID_BUS") != "usb":
        return False
    return ":capture:" in props.get("ID_V4L_CAPABILITIES", "")


# ============================================================
# EVENT HANDLERS
# ============================================================

def handle_camera_add(dev):
    global current_aas_id

    with lock:
        if server_proc is not None and server_proc.poll() is None:
            print("🔵 Camera API already running, ignore ADD.")
            return

        info = camera_info_from_device(dev)
        print(f"\n🎥 USB camera added: {info['devnode']}")
        print(f"   Vendor: {info['vendor']}")
        print(f"   Model : {info['model']}")
        print(f"   Serial: {info['serial'] or 'N/A'}")

        caps = read_camera_caps(info["devnode"])
        print(f"   Caps  : {caps['width']}x{caps['height']} @ {caps['fps']}fps")

        ip = get_local_ip()
        print(f"   Pi IP : {ip}:{API_PORT}")

        aas_json = build_aas_from_auto(info, caps, ip, API_PORT)
        current_aas_id = aas_json["assetAdministrationShells"][0]["id"]
        print(f"   AAS ID: {current_aas_id}")

        register_or_update_aas(aas_json, "/tmp/auto_camera_aas.json")

        start_camera_server()
        print("✅ Camera ADD handling finished.\n")


def handle_camera_remove(dev):
    global current_aas_id

    with lock:
        info = camera_info_from_device(dev)
        print(f"\n📤 USB camera removed: {info['devnode']}")

        stop_camera_server()

        if current_aas_id:
            print(f"🗑 Deleting AAS → {current_aas_id}")
            delete_aas(current_aas_id)
        else:
            print("🔵 No AAS ID recorded, skip delete.")

        current_aas_id = None
        print("✅ Camera REMOVE handling finished.\n")


# ============================================================
# pyudev MONITOR
# ============================================================

def udev_event(device):
    action = device.action

    if not is_usb_capture_device(device):
        return

    if action == "add":
        handle_camera_add(device)
    elif action == "remove":
        handle_camera_remove(device)


def initial_scan(context):
    print("🔍 Initial scan for existing USB cameras ...")
    for dev in context.list_devices(subsystem="video4linux"):
        if is_usb_capture_device(dev):
            print(f"   Found existing camera: {dev.device_node}")
            handle_camera_add(dev)
            return
    print("   No USB camera present at startup.")


# ============================================================
# MAIN
# ============================================================

def main():
    print("\n==============================")
    print("  🚀 Camera Orchestrator")
    print("==============================\n")

    ctx = pyudev.Context()
    initial_scan(ctx)

    monitor = pyudev.Monitor.from_netlink(ctx)
    monitor.filter_by(subsystem="video4linux")
    observer = pyudev.MonitorObserver(monitor, callback=udev_event)
    observer.start()

    print("👀 Start monitoring USB cameras ...")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("🛑 exit orchestrator")
    finally:
        observer.stop()
        stop_camera_server()
