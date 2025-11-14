# src/kuksa/ultrasonic2kuksa.py
import subprocess
import threading


class KuksaClient:
    def __init__(self, server="192.168.137.1:55555"):
        self.server = server
        self.image = "ghcr.io/eclipse-kuksa/kuksa-databroker-cli:main"

    def publish_async(self, signal, value):
        """Non-blocking publish"""
        t = threading.Thread(
            target=self._publish_blocking,
            args=(signal, value),
            daemon=True
        )
        t.start()

    def _publish_blocking(self, signal, value):
        cmd = [
            "docker", "run", "--rm", "--network=host",
            self.image,
            "--server", self.server,
            "publish", signal, str(value)
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
