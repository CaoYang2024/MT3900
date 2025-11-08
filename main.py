# main.py

from src.orchestrator.usb_hotplug import USBHotplugOrchestrator

if __name__ == "__main__":
    orchestrator = USBHotplugOrchestrator()

    try:
        orchestrator.monitor()
    except KeyboardInterrupt:
        orchestrator.stop_driver()
        print("\n🛑 Exit")
