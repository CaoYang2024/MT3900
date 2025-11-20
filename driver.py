#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Ultrasonic Driver v3 — AAS AUTO-CONFIG
--------------------------------------
✔ AAS_ID 从环境变量读取（orchestrator 注入）
✔ 自动从 AAS AssetInterface 获取:
    - Port          (/dev/ttyACM0)
    - VSSPath       (Vehicle.ADAS....)
✔ PUT Value → AAS
✔ publish → Kuksa (异步)
"""

import os
import time
import threading
import requests
import minimalmodbus
import serial
import base64
import subprocess
import sys

AAS_SERVER = os.environ.get("AAS_SERVER", "http://192.168.137.1:8081")
AAS_ID = os.environ.get("AAS_ID", None)

VALUE_IDSHORT = "Value"


# ============================================================
# Base64 URL Encode
# ============================================================
def b64url(s: str):
    return base64.urlsafe_b64encode(s.encode()).decode().rstrip("=")


# ============================================================
# 从 AAS 查询 AssetInterface（Port + VSSPath）
# ============================================================
def resolve_asset_interface():
    if not AAS_ID:
        print("❌ ERROR: AAS_ID not provided by orchestrator.")
        sys.exit(1)

    print(f"🔧 Driver launched with AAS_ID = {AAS_ID}")

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

    # GET AssetInterface submodel
    sm_url = f"{AAS_SERVER}/submodels/{enc_sm}"
    sm = requests.get(sm_url).json()

    port = None
    vss = None

    for elem in sm["submodelElements"]:
        if elem["idShort"] == "Port":
            port = elem["value"]
        elif elem["idShort"] == "VSSPath":
            vss = elem["value"]

    if not port:
        print("❌ ERROR: Port not found in AssetInterface")
        sys.exit(1)

    if not vss:
        print("❌ WARNING: VSSPath not found → publish disabled")

    print(f"🔌 Port from AAS = {port}")
    print(f"📡 VSSPath from AAS = {vss}")

    return port, vss, enc_sm


# ============================================================
# Ultrasonic Sensor (Modbus)
# ============================================================
BAUDRATE = 9600
SLAVE_ADDR = 1
REGISTER = 0x0101
SAMPLE_INTERVAL = 0.3


class Ultrasonic:
    def __init__(self, port):
        self.instrument = minimalmodbus.Instrument(port, SLAVE_ADDR)
        self.instrument.serial.baudrate = BAUDRATE
        self.instrument.serial.bytesize = 8
        self.instrument.serial.parity = serial.PARITY_NONE
        self.instrument.serial.stopbits = 1
        self.instrument.serial.timeout = 0.3
        self.instrument.mode = minimalmodbus.MODE_RTU

    def read(self):
        try:
            mm = self.instrument.read_register(REGISTER, 0)
            return mm / 1000.0
        except:
            return None


# ============================================================
# Kuksa publish（异步 Docker）
# ============================================================
def publish_kuksa_async(signal, value):
    def _pub():
        cmd = [
            "docker", "run",
            "-i", "-t",
            "--rm",
            "ghcr.io/eclipse-kuksa/kuksa-databroker-cli:main",
            "--server", "192.168.137.1:55555",
            "--protocol", "kuksa.val.v1",
            "publish",
            signal,
            str(value)
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    threading.Thread(target=_pub, daemon=True).start()


# ============================================================
# MAIN
# ============================================================
def main():
    port, vss, enc_sm = resolve_asset_interface()

    # Build AAS PUT URL for Value
    value_url = f"{AAS_SERVER}/submodels/{enc_sm}/submodel-elements/{VALUE_IDSHORT}"

    sensor = Ultrasonic(port)
    last_pub = 0

    print("\n🚀 Ultrasonic driver started.\n")

    while True:
        now = time.time()

        # 1) Read ultrasonic
        value = sensor.read()
        if value is None:
            print("⚠️ Read failed")
            time.sleep(SAMPLE_INTERVAL)
            continue

        print(f"📏 Distance = {value:.3f} m")

        # 2) PUT → AAS
        body = {
            "idShort": VALUE_IDSHORT,
            "modelType": "Property",
            "valueType": "xs:double",
            "value": str(value)
        }
        r = requests.put(value_url, json=body)
        print(f"➡️ PUT AAS {r.status_code}")

        # 3) Publish to Kuksa every 3s
        if vss and now - last_pub >= 3:
            publish_kuksa_async(vss, value)
            last_pub = now
            print("🐳 publish → kuksa")

        time.sleep(SAMPLE_INTERVAL)


if __name__ == "__main__":
    main()
