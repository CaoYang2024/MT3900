# src/orchestrator/orchestrator.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
from pathlib import Path
import yaml
import json

from src.aas.generate_aas_from_config import build_aas
from src.aas.aas_manager import register_or_update_aas, put_value
from src.kuksa.ultrasonic2kuksa import KuksaClient
from src.drivers.ultrasonic import UltrasonicDriver


DRIVER_MAP = {
    "ultrasonic": UltrasonicDriver,
}


class SensorOrchestrator:
    def __init__(self, config_path, aas_host, kuksa_server):
        self.cfg = yaml.safe_load(Path(config_path).read_text())
        self.aas_host = aas_host
        self.kuksa_server = kuksa_server

        self.aas_id = self.cfg["id"]
        self.sensor_type = self.cfg["sensor"]["type"]
        self.extra = self.cfg["interface"]["extra"]
        self.value_name = self.extra.get("valueIdShort", "Value")

    # ====================================================
    def generate_aas(self):
        aas_json = build_aas(self.cfg)
        out = f"/tmp/{self.sensor_type}.json"
        Path(out).write_text(json.dumps(aas_json, indent=2), encoding="utf-8")
        print(f"① AAS JSON generated → {out}")
        return out

    # ====================================================
    def upload_aas(self, json_path):
        print("② Uploading AAS JSON using register_or_update_aas() ...")
        with open(json_path, "r", encoding="utf-8") as f:
            aas_json = json.load(f)
        register_or_update_aas(aas_json)

    # ====================================================
    def init_driver(self):
        Driver = DRIVER_MAP[self.sensor_type]
        self.driver = Driver(self.cfg)
        print(f"③ {self.sensor_type} driver initialized.")

    # ====================================================
    def init_backend(self):
        self.kuksa = KuksaClient(self.kuksa_server)
        print("④ Kuksa ready — BaSyx PUT using aas_manager.")

    # ====================================================
    # MAIN LOOP: Continuous publish + PUT
    # ====================================================
    def start_loop(self):
        print("🚀 Orchestrator started!")
        vss_path = self.extra["vssPath"]

        while True:
            value = self.driver.read_value()
            if value is None:
                print("❌ Sensor read failed")
                time.sleep(0.5)
                continue

            print(f"📡 {self.sensor_type} → {value}")

            # publish to Kuksa (non-blocking)
            self.kuksa.publish_async(vss_path, value)

            # update AAS
            put_value(self.aas_id, self.value_name, value)

            time.sleep(0.5)
