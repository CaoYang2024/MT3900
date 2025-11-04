# orchestrator/manager.py

import threading

class SensorManager:
    def __init__(self):
        self.running = {}

    def start(self, device_path, driver):
        t = threading.Thread(target=driver.start, daemon=True)
        self.running[device_path] = (driver, t)
        t.start()

    def stop(self, device_path):
        if device_path in self.running:
            driver, thread = self.running[device_path]
            driver.stop()
            del self.running[device_path]
