#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Orchestrator v4 (FINAL — English)
=================================
Features:
✔ Exact AAS matching using fingerprint (vendor:product:serial)
✔ Automatically downloads driver.py from AAS
✔ Injects environment variables AAS_ID and AAS_SERVER into driver
✔ Supports both Camera and Ultrasonic sensors
"""

import os
import signal
import subprocess
import base64
import requests
import pyudev

AAS_SERVER = "http://192.168.137.1:8081"
FILE_IDSHORT = "DriverFile"
DRIVER_NAME = "driver.py"

# Active driver process information
active_proc = None
active_fp_key = None
active_devpath = None


# ============================================================
# Helpers
# ============================================================
def b64url(s: str):
    """Encode string using URL-safe Base64 (for BaSyx REST paths)."""
    return base64.urlsafe_b64encode(s.encode()).decode().rstrip("=")


def get_usb_fingerprint(dev):
    """Extract vendor/product/serial attributes from a USB device."""
    vendor = dev.attributes.get("idVendor")
    product = dev.attributes.get("idProduct")
    serial = dev.attributes.get("serial")

    return {
        "vendor": vendor.decode() if vendor else "",
        "product": product.decode() if product else "",
        "serial": serial.decode() if serial else "",
    }


def fp_key(fp):
    """Fingerprint key format used for AAS matching."""
    return f"{fp['vendor']}:{fp['product']}:{fp['serial']}"


# ============================================================
# AAS Matching
# ============================================================
def find_aas_by_fingerprint(fp):
    """Find AAS whose ID ends with vendor:product:serial."""
    key = fp_key(fp)
    print(f"🔍 Searching AAS matching fingerprint: {key}")

    shells = requests.get(f"{AAS_SERVER}/shells").json().get("result", [])

    for sh in shells:
        aas_id = sh["id"]
        if aas_id.endswith(key):
            print(f"   ✔ Found AAS: {aas_id}")
            return aas_id

    print("   ❌ No AAS matched")
    return None


# ============================================================
# Download Driver File
# ============================================================
def download_driver(aas_id, out_path):
    """Download driver.py from the AssetInterface File element in AAS."""
    print(f"⬇️ Requesting DriverFile from AAS {aas_id}")

    enc_shell = b64url(aas_id)
    shell = requests.get(f"{AAS_SERVER}/shells/{enc_shell}").json()
    if isinstance(shell, list):
        shell = shell[0]

    # Locate AssetInterface submodel
    ai_iri = None
    for sm in shell["submodels"]:
        iri = sm["keys"][0]["value"]
        if iri.endswith("/AssetInterface"):
            ai_iri = iri

    if not ai_iri:
        raise RuntimeError("❌ No AssetInterface found in AAS")

    enc_sm = b64url(ai_iri)
    url = f"{AAS_SERVER}/submodels/{enc_sm}/submodel-elements/{FILE_IDSHORT}/attachment"

    print(f"   → GET {url}")
    r = requests.get(url)

    if r.status_code != 200:
        raise RuntimeError(f"❌ Download failed {r.status_code}: {r.text}")

    with open(out_path, "wb") as f:
        f.write(r.content)

    print(f"📥 Saved → {out_path}\n")


# ============================================================
# Start / Stop Driver
# ============================================================
def start_driver(script, fp, aas_id):
    """Start driver.py with injected AAS_ID and AAS_SERVER."""
    global active_proc, active_fp_key

    key = fp_key(fp)
    active_fp_key = key

    print(f"🚀 Starting driver for {key}")
    print(f"   → Inject AAS_ID={aas_id}")
    print(f"   → Inject AAS_SERVER={AAS_SERVER}")

    env = os.environ.copy()
    env["AAS_ID"] = aas_id
    env["AAS_SERVER"] = AAS_SERVER

    active_proc = subprocess.Popen(
        ["python3", script],
        preexec_fn=os.setsid,
        env=env
    )


def stop_driver():
    """Terminate the currently running driver process."""
    global active_proc, active_fp_key

    if not active_proc:
        return

    print("🛑 Stopping driver...")
    try:
        os.killpg(active_proc.pid, signal.SIGTERM)
    except:
        pass

    active_proc = None
    active_fp_key = None

    print("   ✔ stopped\n")


# ============================================================
# USB Hotplug Handlers
# ============================================================
def handle_add(dev):
    """Handle USB device insertion event."""
    global active_devpath

    fp = get_usb_fingerprint(dev)
    key = fp_key(fp)

    print(f"🔌 [ADD] USB Device {key}")
    active_devpath = dev.device_path

    aas_id = find_aas_by_fingerprint(fp)
    if not aas_id:
        return

    download_driver(aas_id, DRIVER_NAME)
    start_driver(DRIVER_NAME, fp, aas_id)


def handle_remove(dev):
    """Handle USB device removal event."""
    global active_devpath

    print(f"🔌 [REMOVE] devpath={dev.device_path}")

    if dev.device_path == active_devpath:
        stop_driver()
        active_devpath = None
    else:
        print("   (Not the active device)")


# ============================================================
# Initial Scan
# ============================================================
def initial_scan():
    """At program start, check if any sensor is already connected."""
    print("🔎 Initial USB scan...")

    ctx = pyudev.Context()

    for dev in ctx.list_devices(subsystem="usb", DEVTYPE="usb_device"):
        fp = get_usb_fingerprint(dev)
        if not fp["vendor"]:
            continue

        aas_id = find_aas_by_fingerprint(fp)
        if not aas_id:
            continue

        print("💡 Found existing sensor → starting driver")

        global active_devpath
        active_devpath = dev.device_path

        download_driver(aas_id, DRIVER_NAME)
        start_driver(DRIVER_NAME, fp, aas_id)
        return

    print("⚪ No existing devices.\n")


# ============================================================
# MAIN LOOP
# ============================================================
def main():
    print("\n======================================")
    print("         🚗 Sensor Orchestrator v4")
    print("   Match AAS by vendor:product:serial")
    print("======================================\n")

    initial_scan()

    print("👀 Watching USB hotplug...\n")

    ctx = pyudev.Context()
    monitor = pyudev.Monitor.from_netlink(ctx)
    monitor.filter_by(subsystem="usb")

    for action, dev in monitor:
        if dev.device_type != "usb_device":
            continue

        if action == "add":
            handle_add(dev)
        elif action == "remove":
            handle_remove(dev)


# ============================================================
# Exit Hooks
# ============================================================
def shutdown(sig, frame):
    """Gracefully terminate orchestrator and running driver."""
    print("\n👋 Shutdown orchestrator")
    stop_driver()
    exit(0)


signal.signal(signal.SIGINT, shutdown)
signal.signal(signal.SIGTERM, shutdown)


if __name__ == "__main__":
    main()
