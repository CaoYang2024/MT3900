import subprocess

class KuksaClient:
    """
    Minimal Kuksa Databroker CLI wrapper (Docker-based).
    Supports:
      • publish(signal, value)
      • get(signal)
    Runs correctly on Raspberry Pi + SSH + Windows.
    """

    def __init__(self, server="192.168.0.180:55555"):
        """
        server: Kuksa Databroker 地址，如 "192.168.0.180:55555"
        """
        self.server = server
        self.image = "ghcr.io/eclipse-kuksa/kuksa-databroker-cli:main"

    def _run(self, args):
        cmd = [
                  "docker", "run", "-i", "--rm",  # ✅ 不要使用 -t，只用 -i
                  "-e", "TERM=xterm",  # ✅ 仍然避免 terminfo not found
                  self.image,
                  "--server", self.server,
              ] + args

        print("\nCMD:", " ".join(cmd))

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True
        )

        output = (result.stdout or "") + (result.stderr or "")
        print("OUTPUT:", output)

        if result.returncode != 0:
            raise RuntimeError(f"Kuksa CLI error:\n{output}")

        return output.strip()
    # -------------------------------
    # API exposed functions
    # -------------------------------
    def publish(self, signal: str, value):
        """
        Publish a numeric/string value to a VSS signal
        """
        self._run(["publish", signal, str(value)])
        print(f"[✔] Published: {signal} = {value}")
        return value

    def get(self, signal: str):
        """
        Get a VSS signal value (returns pure string or number)
        output example:
            Vehicle.Speed: 55 km/h
            OR
            Vehicle.Speed | 55
        """
        res = self._run(["get", signal])

        # extract value
        for sep in ["|", ":"]:
            if sep in res:
                return res.split(sep)[-1].strip()
        return res


# ---------------------------------------
# CLI test (executed only when run directly)
# ---------------------------------------
if __name__ == "__main__":
    kuksa = KuksaClient(server="192.168.0.180:55555")

    # test publish
    kuksa.publish("Vehicle.Speed", 55)

    # test get
    v = kuksa.get("Vehicle.Speed")
    print(f"[READ] Vehicle.Speed = {v}")
