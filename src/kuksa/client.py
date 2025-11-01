import subprocess
import time
import re

class KuksaInteractiveClient:
    """
    Connect to kuksa-databroker-cli in interactive TTY mode and send commands.
    """

    def __init__(self, server="192.168.0.180:55555"):
        self.server = server
        self.image = "ghcr.io/eclipse-kuksa/kuksa-databroker-cli:main"

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

        # wait for CLI to print welcome ascii
        time.sleep(2)
        print(self.process.stdout.read())

    def send(self, cmd: str) -> str:
        """
        Send a command to the kuksa interactive CLI
        and return output
        """
        print(f">>> {cmd}")

        # send command
        self.process.stdin.write(cmd + "\n")
        self.process.stdin.flush()

        time.sleep(0.5)  # small wait for output ready
        output = self.process.stdout.read()

        print(output)
        return output

    def get(self, signal: str):
        """
        Get signal value, extract number
        """
        output = self.send(f"get {signal}")
        match = re.search(rf"{signal}[:|]\s*(.*)", output)
        if match:
            return match.group(1).strip()
        return None

    def close(self):
        self.process.stdin.write("exit\n")
        self.process.stdin.flush()
        self.process.terminate()


# ===========================================
# Usage example:
# ===========================================
if __name__ == "__main__":
    kuksa = KuksaInteractiveClient("192.168.0.180:55555")

    speed = kuksa.get("Vehicle.Speed")
    print("✅ Current speed =", speed)

    kuksa.close()
