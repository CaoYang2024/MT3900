import time
import math
import random
import json
import requests

# === AAS Submodel Element 目标 URL ===
AAS_URL = (
    "http://localhost:8081/submodels/"
    "aHR0cHM6Ly9DYW9ZYW5nL0FBU2J5TExNL3RyZWUvbWFpbi9BQVNfU2FtcGxlcy9pZHMvc3VibW9kZWwvcnVudGltZS9yczQ4NV91bHRyYXNvbmljX2EwMWE"
    "/submodel-elements/Distance_m"
)

HEADERS = {"Content-Type": "application/json"}

def virtual_distance():
    """生成一个模拟传感器读数"""
    t = time.time()
    return round(5 + 2 * math.sin(t) + random.uniform(-0.1, 0.1), 3)

def upload_distance():
    while True:
        value = virtual_distance()

        # 构造 Property JSON（符合 AAS v3 格式）
        payload = {
            "modelType": "Property",
            "semanticId": {
                "keys": [
                    {
                        "type": "GlobalReference",
                        "value": "Vehicle.ADAS.ParkAssist.Ultrasonic.Front.Center.Distance"
                    }
                ],
                "type": "ExternalReference"
            },
            "value": str(value),          # 注意：AAS 的 value 是字符串，即使类型是 double
            "valueType": "xs:double",
            "description": [
                {
                    "language": "en",
                    "text": "Measured distance to nearest obstacle."
                }
            ],
            "idShort": "Distance_m"
        }

        try:
            r = requests.put(AAS_URL, json=payload, headers=HEADERS, timeout=5)
            if r.status_code in (200, 204):
                print(f"[OK] Updated Distance_m = {value}")
            else:
                print(f"[WARN] {r.status_code}: {r.text}")
        except requests.RequestException as e:
            print("[ERROR]", e)

        time.sleep(0.5)  # 每 0.5 秒上传一次

if __name__ == "__main__":
    upload_distance()
