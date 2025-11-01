import subprocess
import re


class KuksaClient:
    """
    Minimal Kuksa Databroker CLI wrapper (publish + get)
    Works like the CLI:
        docker run --rm -e TERM=xterm ghcr.io/eclipse-kuksa/kuksa-databroker-cli:main --server <IP> publish <signal> <value>
    """

    def __init__(self, server="192.168.0.180:55555"):
        self.server = server
        self.image = "ghcr.io/eclipse-kuksa/kuksa-databroker-cli:main"

    def _run(self, args):
        """
        run docker CLI, return full output text
        """
        cmd = [
            "docker", "run", "--rm",
            "-e", "TERM=xterm",
            self.image,
            "--server", self.server,
        ] + args

        print("CMD:", " ".join(cmd))  # debug print

        result = subprocess.run(cmd, capture_output=True, text=True)
        return (result.stdout or "") + (result.stderr or "")

    def publish(self, signal, value):
        """
        publish value to vss
        """
        output = self._run(["publish", signal, str(value)])
        print("[PUBLISH]", output)
        return output

    def get(self, signal):
        """
        get value, extract last part
        Example output:
            Vehicle.Speed: 120.00 km/h
        We just return `120.00 km/h`
        """
        output = self._run(["get", signal])

        # extract last piece after ":" or "|"
        m = re.search(rf"{signal}[:|]\s*(.+)", output)
        if m:
            value = m.group(1).strip()
            print(f"[GET] {signal} =", value)
            return value

        print(f"[GET] No value found for {signal}")
        return None


if __name__ == "__main__":
    kuksa = KuksaClient("192.168.0.180:55555")

    # just test publish + get
    kuksa.publish("Vehicle.Speed", 88)
    kuksa.get("Vehicle.Speed")
