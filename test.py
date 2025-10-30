import subprocess, time, itertools

NETWORK = "kuksa"
SERVER  = "Server:55555"
PATH    = "Vehicle.Chassis.Axle.Row2.Wheel.Left.Tire.Temperature"
VALUES  = [25, 26, 27, 28]   # 自己改；也可用随机/正弦

def publish(value):
    cmd = [
        "docker","run","-t","--rm","--network",NETWORK,
        "ghcr.io/eclipse-kuksa/kuksa-databroker-cli:main",
        "--server",SERVER,
        "publish",PATH,str(value)
    ]
    print(" ".join(cmd))
    subprocess.run(cmd, check=True)

if __name__ == "__main__":
    print("🚗 连续发布到", SERVER, "—", PATH)
    for v in itertools.cycle(VALUES):
        publish(v)
        print(f"[SENSOR] {PATH} = {v}")
        time.sleep(1)
