#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Single-file Ultrasonic Driver (Debug PUT version)
-------------------------------------------------
✔ 打印PUT状态码和服务器返回内容（定位错误）
"""

import time
import glob
import threading
import requests
import minimalmodbus
import serial
import base64
import subprocess


AAS_SERVER = "http://192.168.137.1:8081"
AAS_ID = "urn:mt3900:sensor:1a86:55d3:ttyUSB0"
VALUE_IDSHORT = "Value"

KUKSA_SERVER = "192.168.137.1:55555"
VSS_PATH = "Vehicle.ADAS.ParkAssist.Ultrasonic.Front.Center.Distance"

BAUDRATE = 9600
SLAVE_ADDR = 1
REGISTER = 0x0101
SAMPLE_INTERVAL = 0.3


def b64url(s: str):
    return base64.urlsafe_b64encode(s.encode()).decode().rstrip("=")


def resolve_value_url():
    enc_shell = b64url(AAS_ID)
    shell_url = f"{AAS_SERVER}/shells/{enc_shell}"

    shell = requests.get(shell_url).json()
    if isinstance(shell, list):
        shell = shell[0]

    submodels = shell.get("submodels", [])

    asset_sm_iri = None
    for sm in submodels:
        iri = sm["keys"][0]["value"]
        if iri.endswith("/AssetInterface"):
            asset_sm_iri = iri

    if not asset_sm_iri:
        print("❌ AssetInterface not found in AAS")
        exit(1)

    enc_sm = b64url(asset_sm_iri)

    value_url = f"{AAS_SERVER}/submodels/{enc_sm}/submodel-elements/{VALUE_IDSHORT}"
    print(f"🔗 AAS Value URL = {value_url}")
    return value_url


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


def publish_kuksa_async(signal, value):
    def _pub():
        cmd = [
            "docker", "run",
            "-i",
            "-t",       # ⭐ 必须加
            "--rm",
            "ghcr.io/eclipse-kuksa/kuksa-databroker-cli:main",
            "--server", KUKSA_SERVER,
            "--protocol", "kuksa.val.v1",
            "publish",
            signal,
            str(value)
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    threading.Thread(target=_pub, daemon=True).start()


def main():
    ports = glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*")
    if not ports:
        print("❌ No ultrasonic sensor found")
        return

    port = ports[0]
    print(f"🔌 Using port = {port}")

    sensor = Ultrasonic(port)
    value_url = resolve_value_url()

    print("\n🚀 Start reading ultrasonic sensor...\n")

    last_publish = 0  # 上一次 Docker publish 的时间戳

    while True:
        now = time.time()

        # --- 1) 读取超声波 ---
        value = sensor.read()
        if value is None:
            print("⚠️ Read failed")
            time.sleep(SAMPLE_INTERVAL)
            continue

        print(f"📡 Distance = {value} m")

        # --- 2) PUT AAS（每0.3秒）---
        body = {
            "idShort": VALUE_IDSHORT,
            "modelType": "Property",
            "valueType": "xs:double",
            "value": str(value)
        }
        requests.put(value_url, json=body)

        # --- 3) Docker publish 每3秒一次 ---
        if now - last_publish >= 3:
            publish_kuksa_async(VSS_PATH, value)
            last_publish = now
            print("🐳 docker publish executed")

        time.sleep(SAMPLE_INTERVAL)


if __name__ == "__main__":
    main()
