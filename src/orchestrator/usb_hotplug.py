# src/orchestrator/usb_hotplug_orchestrator.py

import pyudev
from drivers.usb_camera_driver import USBCameraDriver
from orchestrator.aas_registry_client import AASRegistryClient


class USBHotplugOrchestrator:

    def __init__(self):
        self.context = pyudev.Context()
        self.driver = USBCameraDriver()

    def start_driver(self):
        self.driver.start()

        endpoint = f"http://{self.driver.ip}:{self.driver.port}/stream"
        aas_file = AASRegistryClient.generate_aas_instance(endpoint)
        AASRegistryClient.upload_or_update()
        AASRegistryClient.update_status("Online")

    def stop_driver(self):
        self.driver.stop()
        AASRegistryClient.update_status("Offline")

    def monitor(self):
        monitor = pyudev.Monitor.from_netlink(self.context)
        monitor.filter_by("video4linux")

        print("👀 Watching USB cameras...")

        for action, device in monitor:
            print(f"USB EVENT: {action}  dev={device.device_node}")

            if action in ("add", "bind"):
                self.start_driver()

            elif action in ("remove", "unbind"):
                self.stop_driver()
