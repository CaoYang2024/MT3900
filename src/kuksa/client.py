import subprocess
import re


class KuksaClient:
    """
    Minimal Kuksa Databroker CLI wrapper (publish + get).
    Works WITHOUT interactive mode.
    """

    def __init__(self, server="192.168.0.180:55555"):
        self.server = server
        self.image = "ghcr.io/eclipse-kuksa/kuksa-databroker-cli:main"

    def _run(self, args):
        """
        Run docker CLI, capture ONLY stdout
        """
        cmd = [
            "docker", "run", "-t", "--rm",
            self.image,
            "--server", self.server,
        ] + args

        print("CMD:", " ".join(cmd))

        result = subprocess.run(cmd, capture_output=True, text=True)

        return result.stdout  # <-- 只用 stdout，不用 stderr

    def publish(self, signal, value):
        out = self._run(["publish", signal, str(value)])
        print("[PUBLISH]", out)
        return out

    def get(self, signal):
        out = self._run(["get", signal])

        # 提取 value (示例: Vehicle.Speed: 88.00 km/h)
        m = re.search(rf"{signal}[:|]\s*(.+)", out)
        if m:
            value = m.group(1).strip()
            print(f"[GET] {signal} = {value}")
            return value

        print(f"[GET] No value found for {signal}")
        return None


if __name__ == "__main__":
    kuksa = KuksaClient("192.168.0.180:55555")

    kuksa.publish("Vehicle.Speed", 88)
    kuksa.get("Vehicle.Speed")
