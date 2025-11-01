# kuksa_to_basyx.py
import subprocess
import re
import json
import time
import requests

# ==========================
# Kuksa Databroker CLI
# ==========================

NETWORK = "kuksa"
SERVER  = "Server:55555"
PATH    = "Vehicle.Chassis.Axle.Row2.Wheel.Left.Tire.Temperature"
IMAGE   = "ghcr.io/eclipse-kuksa/kuksa-databroker-cli:main"

def get_from_kuksa():
    cmd = [
        "docker", "run",
        "-t", "--rm",
        "--network", NETWORK,
        "-e", "TERM=dumb",
        IMAGE, "--server", SERVER,
        "get", PATH
    ]

    res = subprocess.run(cmd, capture_output=True, text=True)
    text = (res.stdout or "") + (res.stderr or "")

    # 提取 "<PATH>: <value 或 NotAvailable>"
    m = re.search(fr"{re.escape(PATH)}:\s*(.+)", text)
    if not m:
        print(f"❌ Kuksa 未返回数据:\n{text}")
        return None

    return m.group(1).strip()


# ==========================
# BaSyx PUT Submodel Element
# ==========================

AAS_ELEMENT_URL = (
    "http://localhost:8081/submodels/"
    "aHR0cHM6Ly9DYW9ZYW5nL0FBU2J5TExNL3RyZWUvbWFpbi9BQVNfU2FtcGxlcy9pZHMvc3VibW9kZWwvYXNzZXRpbnRlcmZhY2VzL3RlbXBlcmF0dXJlX2h0dHA"
    "/submodel-elements/InterfaceForHTTP.value"
)

def put_to_basyx(value):
    payload = {
        "modelType": "Property",
        "value": str(value),          # <-- 保持字符串，包括 NotAvailable
        "valueType": "xs:string",     # ⚠ Since value 可能是 "NotAvailable"
        "displayName": [
            {"language": "en", "text": "temperature value"}
        ],
        "idShort": "value"
    }

    r = requests.put(
        AAS_ELEMENT_URL,
        data=json.dumps(payload),
        headers={"Content-Type": "application/json"}
    )

    print(f"➡️ PUT BaSyx status = {r.status_code} (204 = 成功)")


# ==========================
# Main loop
# ==========================

print("🚦 启动 Kuksa → BaSyx (每 3 秒同步一次)...")

while True:
    value = get_from_kuksa()
    print(f"📥 从 Kuksa 获取 → {value}")

    if value is not None:
        put_to_basyx(value)

    time.sleep(3)
