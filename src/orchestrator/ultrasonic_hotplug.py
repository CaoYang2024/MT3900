#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import glob
import signal
import threading
import subprocess

import requests
from pyudev import Context, Monitor, MonitorObserver

from src.aas.aas_manager import (
    register_or_update_aas,
    mark_connected,
    mark_disconnected,
)
from src.utils.aas_discovery import discover_properties_for_shell
from src.aas.generate_aas_from_config import build_aas


# ================= RS485 Driver Config ====================
API_PORT = "8100"   # RS485 FastAPI 服务端口
DRIVER_DIR = "/home/pi/Downloads/MT3900/src/drivers"

server_proc = None

debounce_lock = threading.Lock()
start_stop_lock = threading.Lock()


# ================================================================
# RS485 API Control
# ================================================================
def kill_uvicorn():
    subprocess.run(["pkill", "-f", "uvicorn"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def start_api(port_dev: str):
    """启动 RS485 传感器 FastAPI"""
    global server_proc

    with start_stop_lock:
        kill_uvicorn()

        env = os.environ.copy()
        env["SERIAL_DEV"] = port_dev   # e.g. /dev/ttyUSB0
        env["PORT"] = API_PORT

        print(f"🚀 Starting Ultrasonic API (dev={port_dev})")

        server_proc = subprocess.Popen(
            [
                "python3", "-m", "uvicorn",
                "ultrasonic_api:app",
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
            print("🛑 Stopping RS485 API")
            server_proc.send_signal(signal.SIGTERM)

            try:
                server_proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                server_proc.kill()

            server_proc = None
            time.sleep(0.2)


# ================================================================
# Utility
# ================================================================
def get_ip():
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except:
        return "localhost"
    finally:
        s.close()


def aas_exists(aas_id: str):
    try:
        r = requests.get("http://192.168.137.1:8081/shells")
        for sh in r.json():
            if sh["id"] == aas_id:
                return True
    except:
        pass
    return False


def select_rs485_usb():
    """找到 /dev/ttyUSB*"""
    devs = sorted(glob.glob("/dev/ttyUSB*"))
    return devs[0] if devs else None


# ================================================================
# Hotplug Handler
# ================================================================
def handle_event(device):
    global server_proc

    if device.action not in ("add", "remove"):
        return

    # 防抖
    if not debounce_lock.acquire(blocking=False):
        return
    threading.Timer(0.5, debounce_lock.release).start()

    port = select_rs485_usb()
    serial = device.properties.get("ID_SERIAL_SHORT", "Ultrasonic-Unknown")

    aas_id = f"urn:mt3900:rs485:{serial}"
    ip = get_ip()

    # ============================================================
    # Add Event
    # ============================================================
    if device.action == "add":
        print(f"🔵 RS485 device added → {port}")

        if port and server_proc is None:
            start_api(port)
        else:
            print("⏩ RS485 API already running")

        # Upload AAS only first time
        if not aas_exists(aas_id):
            print(f"📦 Uploading AAS for {aas_id}")

            cfg = {
                "id": aas_id,
                "sensor": {
                    "name": "Ultrasonic RS485 Sensor",
                    "manufacturer": "UnknownVendor",
                    "type": "Ultrasonic",
                    "datatype": "distance"
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

        # Mark Connected=true
        mark_connected(aas_id)

    # ============================================================
    # Remove Event
    # ============================================================
    elif device.action == "remove":
        print("🔴 RS485 device removed")

        stop_api()
        mark_disconnected(aas_id)


# ================================================================
# Main Entry (startup check)
# ================================================================
def run_hotplug():
    print("🔌 RS485 Hotplug Monitor Started...")

    existing = select_rs485_usb()

    if existing:
        print(f"📡 RS485 device detected at startup → {existing}")
        fake = type("Fake", (), {})()
        fake.action = "add"
        fake.device_node = existing
        fake.properties = {}
        handle_event(fake)

    context = Context()
    monitor = Monitor.from_netlink(context)
    monitor.filter_by(subsystem="tty")

    observer = MonitorObserver(monitor, callback=handle_event)
    observer.start()

    while True:
        time.sleep(1)
