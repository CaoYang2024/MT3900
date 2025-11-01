# get.py  —— 和 publish.py 一样的风格；分配 TTY，取出一行里的值/状态
import subprocess
import re

NETWORK = "kuksa"
SERVER  = "Server:55555"
PATH    = "Vehicle.Chassis.Axle.Row2.Wheel.Left.Tire.Temperature"
IMAGE   = "ghcr.io/eclipse-kuksa/kuksa-databroker-cli:main"

def get_once():
    cmd = [
        "docker", "run",
        "-t", "--rm",                 # ✅ 分配 TTY，防止 terminfo 报错
        "--network", NETWORK,
        "-e", "TERM=dumb",            # ✅ 告诉 CLI 不要用高级终端能力
        IMAGE, "--server", SERVER,
        "get", PATH
    ]
    print(" ".join(cmd))
    res = subprocess.run(cmd, capture_output=True, text=True)
    text = (res.stdout or "") + (res.stderr or "")
    print("----- CLI Raw Output -----")
    print(text)

    # 提取 "<PATH>: <something>" 里的 <something>
    m = re.search(fr"{re.escape(PATH)}:\s*(.+)", text)
    if not m:
        print("\n❌ 没解析到值（可能 CLI 仍未输出该行）。")
        return None

    value_str = m.group(1).strip()
    print("\n----- Extracted Value/Status -----")
    print(f"✅ extracted: {value_str}")

    # 如果你只想要数字（可能带单位 celsius），再抓第一个数字（可选）
    num = re.search(r"[-+]?\d+(?:\.\d+)?", value_str)
    if num:
        print(f"🔢 numeric-only: {num.group(0)}")
    return value_str

if __name__ == "__main__":
    get_once()
