# main.py
# -*- coding: utf-8 -*-

from src.orchestrator.watcher import watch_new_device
from src.orchestrator.driver_loader import load_driver_from_aas
from src.orchestrator.manager import SensorManager
from src.utils.aas_client import AASClient

AAS_ENV = "http://localhost:8081"

def main():
    print("🚀 Plug-and-Play orchestrator started.")

    client = AASClient(AAS_ENV)
    manager = SensorManager()

    for event in watch_new_device():
        path = event["path"]

        if event["type"] == "ADD":
            print(f"✅ Detected: {path}")

            driver = load_driver_from_aas(event["aas_iri"])
            manager.start(path, driver)

        elif event["type"] == "REMOVE":
            print(f"❌ Removed: {path}")
            manager.stop(path)

if __name__ == "__main__":
    main()
