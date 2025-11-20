#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import signal
import subprocess
import time
import base64
import requests
import pyudev


AAS_SERVER = "http://192.168.137.1:8081"

# 两种 File 属性
FILE_CAMERA = "CameraFile"
FILE_ULTRA = "DriverFile"

active = {}
devpath_map = {}          # device_path → fingerprint key
devnode_map = {}          # fingerprint key → /dev/video* or /dev/ttyUSB*


def b64url(s: str):
    return base64.urlsafe_b64encode(s.encode()).decode().rstrip("=")


# ======================================================
# USB FINGERPRINT
# ======================================================

def get_usb_fingerprint(device):
    return {
        "idVendor": device.get("ID_VENDOR_ID") or "",
        "idProduct": device.get("ID_MODEL_ID") or "",
        "serial": device.get("ID_SERIAL_SHORT") or "",
    }


def make_key(fp):
    return f"{fp['idVendor']}:{fp['idProduct']}"


# ======================================================
# 判断设备类型
# ======================================================

def detect_device_type(device):
    """
    返回 'camera' / 'ultrasonic' / None
    """

    # 向下查找 video 设备
    for child in device.children:
        if child.subsystem == "video4linux":     # camera
            return "camera"

    # 向下查找 ttyUSB/ACM
    for child in device.children:
        if child.device_node and child.device_node.startswith(("/dev/ttyUSB", "/dev/ttyACM")):
            return "ultrasonic"

    return None


# ======================================================
# AAS MATCH
# ======================================================

def find_aas(key_short):
    shells = requests.get(f"{AAS_SERVER}/shells").json().get("result", [])
    for sh in shells:
        if key_short in sh["id"]:
            return sh["id"]
    return None


# ======================================================
# DOWNLOAD DRIVER FILE
# ======================================================

def download_driver(aas_id, out_path, file_idshort):
    enc_shell = b64url(aas_id)
    shell = requests.get(f"{AAS_SERVER}/shells/{enc_shell}").json()
    if isinstance(shell, list):
        shell = shell[0]

    # find AssetInterface
    ai = None
    for sm in shell["submodels"]:
        iri = sm["keys"][0]["value"]
        if iri.endswith("/AssetInterface"):
            ai = iri
    if not ai:
        raise RuntimeError("No AssetInterface found")

    enc_sm = b64url(ai)

    # download
    url = (
        f"{AAS_SERVER}/submodels/{enc_sm}/submodel-elements/"
        f"{file_idshort}/attachment"
    )

    print(f"⬇ Download: {url}")

    r = requests.get(url)
    if r.status_code != 200:
        raise RuntimeError(f"Download failed {r.status_code}: {r.text}")

    with open(out_path, "wb") as f:
        f.write(r.content)

    print(f"📥 File saved → {out_path}")


# ======================================================
# START / STOP DRIVER
# ======================================================

def start_driver(script, key):
    print(f"🚀 Starting driver: {script}")
    proc = subprocess.Popen(["python3", script], preexec_fn=os.setsid)
    active[key] = proc


def stop_driver(key):
    if key not in active:
        return

    proc = active[key]
    print(f"🛑 Killing driver for {key}...")
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except:
        pass
    try:
        proc.wait(timeout=1)
    except:
        pass

    del active[key]
    print("   ✔ Killed")


# ======================================================
# HOTPLUG HANDLERS
# ======================================================

def handle_add(device):

    fp = get_usb_fingerprint(device)
    key = make_key(fp)
    devpath_map[device.device_path] = key

    dev_type = detect_device_type(device)
    print(f"🔌 [ADD] {key} ({dev_type})")

    if dev_type is None:
        print("❌ Unrecognized sensor type")
        return

    aas_id = find_aas(key)
    if not aas_id:
        print("❌ No matching AAS")
        return

    # decide which File to use
    if dev_type == "camera":
        file_idshort = FILE_CAMERA
        script = f"driver_camera_{key.replace(':','_')}.py"
    else:
        file_idshort = FILE_ULTRA
        script = f"driver_ultra_{key.replace(':','_')}.py"

    # download + start
    download_driver(aas_id, script, file_idshort)
    start_driver(script, key)


def handle_remove(device):
    devpath = device.device_path
    key = devpath_map.get(devpath)

    print(f"🔌 [REMOVE] {devpath} → key={key}")

    if key:
        stop_driver(key)
        del devpath_map[devpath]
    else:
        print("   (no active driver)")


# ======================================================
# MAIN
# ======================================================

def main():
    print("👀 Monitoring sensors (Camera + Ultrasonic)...")

    context = pyudev.Context()
    monitor = pyudev.Monitor.from_netlink(context)
    monitor.filter_by(subsystem="usb")

    for action, device in monitor:
        if device.device_type != "usb_device":
            continue

        if action == "add":
            handle_add(device)
        elif action == "remove":
            handle_remove(device)


# kill on Ctrl+C
def shutdown_all(signum, frame):
    print("\n👋 Exit, killing drivers...")
    for key in list(active.keys()):
        stop_driver(key)
    exit(0)


signal.signal(signal.SIGINT, shutdown_all)
signal.signal(signal.SIGTERM, shutdown_all)


if __name__ == "__main__":
    main()
