import subprocess

class KuksaClient:
    """
    Minimal Kuksa Databroker CLI wrapper (non-interactive JSON mode)
    Supports:
      • publish(signal, value)
      • get(signal)
    """

    def __init__(self, server="192.168.0.180:55555"):
        """
        server: Kuksa Databroker IP:PORT
        example: "192.168.0.180:55555"
        """
        self.server = server
        self.image = "ghcr.io/eclipse-kuksa/kuksa-databroker-cli:main"

    def _run(self, args):
        """
        Execute Kuksa CLI in NON-interactive mode (NO TTY needed)
        ✅ avoids: "Error: Not a tty (os error 25)"
        ✅ avoids: "terminfo entry not found"
        """

        cmd = [
            "docker", "run", "--rm",
            "-e", "TERM=xterm",        # ✅ avoid terminfo error
            self.image,
            "--insecure", "--json",    # ✅ json output / non-interactive mode
            "--server", self.server,
        ] + args

        print("\nCMD:", " ".join(cmd))

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )

        output = (result.stdout or "") + (result.stderr or "")
        print("OUTPUT:", output)

        if result.returncode != 0:
            raise RuntimeError(f"Kuksa CLI error:\n{output}")

        return output.strip()

    # -------------------------------
    # Public API
    # -------------------------------
    def publish(self, signal: str, value):
        """
        Publish VSS signal
        """
        self._run(["publish", signal, str(value)])
        print(f"[✔] Published: {signal} = {value}")
        return value

    def get(self, signal: str):
        """
        Read VSS signal
        JSON output sample:
          {"value": 50, "path": "Vehicle.Speed", "ts":"2024..."}

        Returns: numeric/string value only
        """
        output = self._run(["get", signal])

        # extract `"value": ...`
        if '"value"' in output:
            try:
                value = output.split('"value"')[1].split(":")[1].split(",")[0].strip()
                return value.replace("}", "").strip()
            except:
                return output

        return output


# ======================================================
# Test mode (exec only when run directly)
# ======================================================
if __name__ == "__main__":
    kuksa = KuksaClient(server="192.168.0.180:55555")  # <-- modify your server IP here

    kuksa.publish("Vehicle.Speed", 55)
    value = kuksa.get("Vehicle.Speed")
    print(f"[READ] Vehicle.Speed = {value}")
