import subprocess

class KuksaClient:
    """
    Minimal Kuksa Databroker CLI wrapper.
    Only supports: publish() and get()
    """

    def __init__(self, network="kuksa", server="Server:55555"):
        self.network = network
        self.server = server
        self.image = "ghcr.io/eclipse-kuksa/kuksa-databroker-cli:main"

    def _run(self, args):
        cmd = [
            "docker", "run", "-t", "--rm",
            "--network", self.network,
            self.image,
            "--server", self.server,
        ] + args

        print("CMD:", " ".join(cmd))

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print("STDERR:", result.stderr)
            raise RuntimeError(result.stderr)

        return result.stdout.strip()

    def publish(self, signal, value):
        """
        Publish a numeric value to VSS
        """
        self._run(["publish", signal, str(value)])
        return f"[publish] {signal} = {value}"

    def get(self, signal):
        """
        Get value from VSS and return parsed result
        """
        result = self._run(["get", signal])

        # 输出可能是:
        # Vehicle.Speed: 30.00 km/h 或者 Vehicle.Speed | 30
        for sep in ["|", ":"]:
            if sep in result:
                return result.split(sep)[-1].strip()

        return result
