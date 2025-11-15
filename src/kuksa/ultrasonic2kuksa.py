# src/kuksa/ultrasonic2kuksa.py
import subprocess
import threading


class KuksaClient:
    """
    静默 publish，不阻塞 Ctrl+C，不打印任何内容
    """

    def __init__(self, server="192.168.137.1:55555"):
        self.server = server
        self.image = "ghcr.io/eclipse-kuksa/kuksa-databroker-cli:main"

    def publish_async(self, signal, value):
        t = threading.Thread(
            target=self._publish_blocking,
            args=(signal, value),
            daemon=True
        )
        t.start()

    def _publish_blocking(self, signal, value):
        """完全静默执行 publish"""

        cmd = [
            "docker", "run",
            "--rm",
            self.image,
            "--server", self.server,
            "--protocol", "kuksa.val.v1",
            "publish", signal, str(value)
        ]

        # 不要打印、不占用 terminal，不影响 Ctrl+C
        subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
