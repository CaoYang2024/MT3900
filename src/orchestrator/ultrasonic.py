#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Ultrasonic Orchestrator (Stable Clean Version)
---------------------------------------------
功能:
- 自动发现 ttyACM* / ttyUSB*
- 插入时自动启动
- 拔出时自动停止 & delete AAS
- 自动重连驱动
- Kuksa publish
- AAS PUT
"""

import time
import json
import threading
import glob
from pathlib import Path

import yaml
from pyudev import Context, Monitor, MonitorObserver

from src.aas.aas_build import build_ultrasonic_aas     # 使用你目前的版本
from src.aas.aas_client import register_or_update_aas, delete_aas, put_value
from src.kuksa.ultrasonic2kuksa import KuksaClient
from src.drivers.ultrasonic import UltrasonicDriver


# ===================================================================
#  Ultrasonic Orchestrator Class
# ===================================================================

class SensorOrchestrator:
    def __init__(
        self,
        config_path: str,
        aas_host: str,
        kuksa_server: str,
        auto_reconnect=True,
        max_failures=20,
        reconnect_delay=2.0,
        sample_interval=0.3,
    ):
        self.cfg = yaml.safe_load(Path(config_path).read_text())
        self.aas_host = aas_host
        self.kuksa_server = kuksa_server

        self.sensor_type = self.cfg["sensor"]["type"]
        self.model = self.cfg["sensor"].get("model", "A01A")
        self.extra = self.cfg["interface"]["extra"]
        self.value_name = self.extra.get("valueIdShort", "Value")
        self.vss_path = self.extra["vssPath"]

        self.devnode = None
        self.aas_id = None

        self.driver = None
        self.kuksa = None
        self.running = False
        self.loop_thread = None

        self.auto_reconnect = auto_reconnect
        self.max_failures = max_failures
        self.reconnect_delay = reconnect_delay
        self.sample_interval = sample_interval

    # --------------------------------------------------------------
    #  自动发现 /dev/tty*
    # --------------------------------------------------------------
    def find_ultrasonic_device(self):
        ports = glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*")
        if ports:
            return ports[0]
        raise RuntimeError("❌ No ultrasonic sensor found")

    # --------------------------------------------------------------
    #  AAS 生成 + 上传 + 删除
    # --------------------------------------------------------------
    def create_and_upload_aas(self):
        aas_json = build_ultrasonic_aas(self.devnode, self.vss_path, model=self.model)
        self.aas_id = aas_json["assetAdministrationShells"][0]["id"]

        Path("/tmp/ultrasonic.json").write_text(
            json.dumps(aas_json, indent=2), encoding="utf-8"
        )
        print(f"① AAS JSON generated (id={self.aas_id})")

        print("② Uploading AAS ...")
        register_or_update_aas(aas_json)

    def delete_aas(self):
        if self.aas_id:
            delete_aas(self.aas_id)
            print(f"🗑 AAS deleted: {self.aas_id}")

    # --------------------------------------------------------------
    #  Driver + Kuksa
    # --------------------------------------------------------------
    def start_driver(self):
        self.cfg["interface"]["extra"]["port"] = self.devnode
        self.driver = UltrasonicDriver(self.cfg, devnode=self.devnode)
        print(f"③ Driver ready → {self.devnode}")

    def start_kuksa(self):
        self.kuksa = KuksaClient(self.kuksa_server)
        print("④ Kuksa backend ready")

    def restart_driver(self):
        print("♻️ Restarting ultrasonic driver ...")
        try:
            self.start_driver()
            print("   ✔ Driver restarted")
        except Exception as e:
            print(f"   ❌ Failed to restart: {e}")

    # --------------------------------------------------------------
    #  后台循环
    # --------------------------------------------------------------
    def loop(self):
        fails = 0

        while self.running:
            value = self.driver.read_value()

            if value is None:
                fails += 1

                if self.auto_reconnect and fails >= self.max_failures:
                    self.restart_driver()
                    fails = 0
                    time.sleep(self.reconnect_delay)
                    continue

                time.sleep(self.sample_interval)
                continue

            fails = 0
            print(f"📡 Ultrasonic = {value}")

            self.kuksa.publish_async(self.vss_path, value)
            put_value(self.aas_id, self.value_name, value)

            time.sleep(self.sample_interval)

        print("🛑 Ultrasonic loop stopped.")

    # --------------------------------------------------------------
    #  启动整个 Orchestrator
    # --------------------------------------------------------------
    def start_for_device(self, devnode):
        if self.running:
            return

        self.devnode = devnode
        print(f"🔌 Using device → {self.devnode}")

        self.create_and_upload_aas()
        self.start_driver()
        self.start_kuksa()

        self.running = True
        self.loop_thread = threading.Thread(target=self.loop, daemon=True)
        self.loop_thread.start()

        print("🚀 Ultrasonic orchestrator started.")

    # --------------------------------------------------------------
    def stop(self):
        if not self.running:
            return

        print("🛑 Stopping orchestrator...")
        self.running = False
        time.sleep(0.5)

        self.delete_aas()
        self.driver = None
        self.devnode = None
        self.aas_id = None

        print("✅ Orchestrator stopped.")


# ===================================================================
#  热插拔 manager（主程序调用这个）
# ===================================================================

def run_hotplug_manager(
    config_path="/home/pi/Downloads/MT3900/src/aas/ultrasonic.yaml",
    aas_host="http://192.168.137.1:8081",
    kuksa_server="192.168.137.1:55555",
):
    print("\n===============================")
    print("  📡 Ultrasonic Hotplug Manager")
    print("===============================\n")

    orch_holder = {"orch": None}

    # 启动时检查已有设备
    for dev in glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*"):
        print(f"🔌 Startup: found → {dev}")
        orch = SensorOrchestrator(config_path, aas_host, kuksa_server)
        orch.start_for_device(dev)
        orch_holder["orch"] = orch
        break

    # pyudev 事件处理
    def _on_event(action, device):
        devnode = device.device_node
        if not devnode:
            return

        if not devnode.startswith(("/dev/ttyACM", "/dev/ttyUSB")):
            return

        print(f"\n🔔 EVENT: {action} → {devnode}")

        orch = orch_holder["orch"]

        if action == "add":
            if orch is None:
                orch = SensorOrchestrator(config_path, aas_host, kuksa_server)
                orch.start_for_device(devnode)
                orch_holder["orch"] = orch
            else:
                print("⚠️ Already running, ignore add")

        elif action == "remove":
            if orch and orch.devnode == devnode:
                orch.stop()
                orch_holder["orch"] = None

    ctx = Context()
    mon = Monitor.from_netlink(ctx)
    mon.filter_by("tty")
    obs = MonitorObserver(mon, _on_event)
    obs.start()

    print("👀 Waiting for ultrasonic device hotplug events...\n")

    while True:
        time.sleep(1)
