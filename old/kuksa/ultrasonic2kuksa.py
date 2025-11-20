# src/kuksa/ultrasonic2kuksa.py
import subprocess
import threading


class KuksaClient:
    """
    Docker-based Kuksa Databroker publisher (silent mode).
    Uses: docker run -it --rm <image> publish <signal> <value>
    """

    def __init__(self, server="192.168.137.1:55555"):
        self.server = server
        self.image = "ghcr.io/eclipse-kuksa/kuksa-databroker-cli:main"

    def publish_async(self, signal, value):
        """Publish in a non-blocking background thread."""
        t = threading.Thread(
            target=self._publish_blocking,
            args=(signal, value),
            daemon=True
        )
        t.start()

    def _publish_blocking(self, signal, value):
        """Execute Docker publish command silently."""

        cmd = [
            "docker", "run",
            "-i",            # keep STDIN open
            "-t",            # allocate TTY (required for OK output behavior)
            "--rm",
            self.image,
            "--server", self.server,
            "--protocol", "kuksa.val.v1",
            "publish",
            signal,
            str(value)
        ]

        # Silent execution
        subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
