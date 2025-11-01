# publish.py
import subprocess
import time
import itertools

NETWORK = "kuksa"
SERVER  = "Server:55555"
PATH    = "Vehicle.Chassis.Axle.Row2.Wheel.Left.Tire.Temperature"

# 你想模拟的温度曲线
VALUES = [25, 26, 27, 28]

def publish(value):
    cmd = [
        "docker", "run", "-t", "--rm",
        "--network", NETWORK,
        "ghcr.io/eclipse-kuksa/kuksa-databroker-cli:main",
        "--server", SERVER,
        "publish", PATH, str(value)
    ]

    print(" ".join(cmd))
    subprocess.run(cmd, check=True)

if __name__ == "__main__":
    print("🚗 持续 publish 温度到 Kuksa Databroker（不使用 set）")

    for v in itertools.cycle(VALUES):
        publish(v)
        print(f"[publish] {PATH} = {v}")
        time.sleep(1)
