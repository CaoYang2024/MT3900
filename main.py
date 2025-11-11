# main.py

from src.orchestrator.usb_hotplug import run_hotplug

if __name__ == "__main__":
    print("🔌 Plug & Play USB Camera → AAS")
    run_hotplug()
