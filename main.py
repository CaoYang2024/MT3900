# main.py

from src.orchestrator.usb_hotplug import run_hotplug

if __name__ == "__main__":
    print("🔌 USB camera orchestrator started")
    run_hotplug()
