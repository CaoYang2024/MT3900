#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import json
import subprocess
from pathlib import Path
import requests
import yaml
import minimalmodbus
import serial

# ================================================================
# 1. Ultrasonic Driver
# ================================================================
class UltrasonicRS485:
    def __init__(self, port="/dev/ttyACM0", slave_address=1, register=0x0101):
        self.instrument = minimalmodbus.Instrument(port, slave_address)
        self.instrument.serial.baudrate = 9600
        self.instrument.serial.bytesize = 8
        self.instrument.serial.parity = serial.PARITY_NONE
        self.instrument.serial.stopbits = 1
        self.instrument.serial.timeout = 0.3
        self.instrument.mode = minimalmodbus.MODE_RTU
        self.register = register

    def read_mm(self):
        try:
            return self.instrument.read_register(self.register, 0, functioncode=3)
        except Exception as e:
            print("[Ultrasonic ERROR]", e)
            return None


# ================================================================
# 2. Kuksa docker CLI Wrapper
# ================================================================
class KuksaClient:
    def __init__(self, server):
        self.server = server
        self.image = "ghcr.io/eclipse-kuksa/kuksa-databroker-cli:main"

    def publish(self, path, value):
        cmd = [
            "docker", "run",
            "--network=host",
            "--rm",
            self.image,
            "--server", self.server,
            "publish", path, str(value)
        ]
        print("CMD:", " ".join(cmd))
        out = subprocess.run(cmd, capture_output=True, text=True).stdout.strip()
        print("[KUKSA]", out)


# ================================================================
# 3. BaSyx AAS Client
# ================================================================
class AASClient:
    def __init__(self, aas_id, submodel_idshort, prop_idshort, host):
        self.host = host
        self.prop_idshort = prop_idshort

        # ① 获取 Submodel 编码后的 ID
        url = f"{host}/shells/{aas_id}/aas/submodels"
        res = requests.get(url).json()

        for entry in res:
            if entry["idShort"] == submodel_idshort:
                self.submodel_enc = entry["keys"][0]["value"]

        # ② 构造 PUT 地址
        self.put_url = (
            f"{host}/submodels/{self.submodel_enc}"
            f"/submodel-elements/{prop_idshort}/value"
        )

        print("AAS PUT URL =", self.put_url)

    def put(self, value):
        body = {"value": value}
        r = requests.put(self.put_url, json=body)
        print("[AAS PUT]", value, "→", r.status_code)


# ================================================================
# 4. Main Workflow
# ================================================================
if __name__ == "__main__":
    # ---------------------------
    # Load config
    # ---------------------------
    config_path = "config_ultrasonic.yaml"
    cfg = yaml.safe_load(Path(config_path).read_text())

    aas_id = cfg["id"]
    vss_path = cfg["interface"]["extra"]["vssPath"]
    value_id = cfg["interface"]["extra"]["valueIdShort"]

    BASYX = "http://192.168.137.1:8081/api/v3.0"
    KUKSA = "192.168.137.1:55555"

    print("加载配置完成。")

    # ---------------------------
    # Step 1: 生成 AAS JSON
    # ---------------------------
    from aas.generate_aas import build_aas
    aas_json = build_aas(cfg)

    AAS_FILE = "/tmp/ultrasonic.json"
    Path(AAS_FILE).write_text(json.dumps(aas_json, indent=2, ensure_ascii=False), encoding="utf-8")
    print("① 已生成 ultrasonic.json")

    # ---------------------------
    # Step 2: 上传到 BaSyx AAS-env
    # ---------------------------
    print("② 上传到 BaSyx...")
    subprocess.run([
        "curl", "-X", "POST",
        "-H", "Content-Type: application/json",
        "--data", f"@{AAS_FILE}",
        f"{BASYX}/shells"
    ])
    print("BaSyx 上传完成。")

    # ---------------------------
    # Step 3: 初始化 RS485 Sensor
    # ---------------------------
    sensor = UltrasonicRS485(port="/dev/ttyACM0")
    print("③ RS485 驱动初始化完成。")

    # ---------------------------
    # Step 4: 初始化 AAS Client
    # ---------------------------
    aas_client = AASClient(
        aas_id=aas_id,
        submodel_idshort="AssetInterface",
        prop_idshort=value_id,
        host=BASYX
    )

    # ---------------------------
    # Step 5: 初始化 Kuksa Client
    # ---------------------------
    kuksa = KuksaClient(KUKSA)
    print("④ Kuksa 客户端初始化完成。")

    print("🚀 UltraSonic → Kuksa & AAS started!")
    print("--------------------------------------")

    # ---------------------------
    # Step 6: Loop
    # ---------------------------
    while True:
        mm = sensor.read_mm()

        if mm is not None:
            m = mm / 1000.0
            print(f"📏 Distance = {mm} mm → {m} m")

            # 发送到 Kuksa
            kuksa.publish(vss_path, m)

            # PUT 到 BaSyx
            aas_client.put(m)

        else:
            print("❌ Sensor read failed")

        time.sleep(0.5)
