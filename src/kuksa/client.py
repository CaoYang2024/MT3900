import subprocess
import re
import time

class KuksaClient:
    def __init__(self, server="192.168.0.180:55555"):
        self.server = server
        self.image = "ghcr.io/eclipse-kuksa/kuksa-databroker-cli:main"

    def _run(self, args):
        """
        Start CLI as a process, send command, capture output
        """
        cmd = [
            "docker", "run", "-it", "--rm",
            "-e", "TERM=xterm",
            self.image,
            "--server", self.server,
        ] + args

        print("CMD:", " ".join(cmd))

        # 使用 Popen 才能控制 -it 模式
        p = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # 等 CLI 输出启动信息
        time.sleep(0.6)

        # 发送回车让 CLI 执行一次刷新
        p.stdin.write("\n")
        p.stdin.flush()

        output = p.stdout.read()
        return output

    def publish(self, signal, value):
        out = self._run(["publish", signal, str(value)])
        print("[PUBLISH]", out)

    def get(self, signal):
        out = self._run(["get", signal])

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
