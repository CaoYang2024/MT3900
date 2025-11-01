import subprocess
import time
import re

class KuksaInteractiveClient:
    """
    Control kuksa-databroker-cli in interactive mode (exactly like manual CLI)
    Supports:
      • send("publish Vehicle.Speed 55")
      • get("Vehicle.Speed")
    """

    def __init__(self, server="192.168.0.180:55555"):
        self.server = server
        self.image = "ghcr.io/eclipse-kuksa/kuksa-databroker-cli:main"

        print(f"🔌 Connecting to Kuksa Databroker @ {self.server}")

        # ✅ interactive CLI (same as your manual command)
        self.process = subprocess.Popen(
            [
                "docker", "run", "-it", "--rm",
                "-e", "TERM=xterm",
                self.image,
                "--server", self.server,
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )

        # 等待欢迎界面输出完毕
        time.sleep(2)
        print(self.process.stdout.read())

    def send(self, cmd: str):
        """
        Send command to interactive CLI
        """
        print(f">>> {cmd}")
        self.process.stdin.write(cmd + "\n")
        self.process.stdin.flush()

        time.sleep(0.4)
        output = self.process.stdout.read()
        print(output)
        return output

    def get(self, signal: str):
        """
        Read VSS value
        """
        output = self.send(f"get {signal}")

        m = re.search(rf"{signal}[:|]\s*(.*)", output)
        if m:
            return m.group(1).strip()
        return None

    def close(self):
        self.send("exit")
        self.process.terminate()


# ===============================
# Test
# ===============================
if __name__ == "__main__":
    kuksa = KuksaInteractiveClient("192.168.0.180:55555")

    # publish
    kuksa.send("publish Vehicle.Speed 120")

    # get
    v = kuksa.get("Vehicle.Speed")
    print("✅ speed =", v)

    kuksa.close()
