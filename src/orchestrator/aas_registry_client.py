# src/orchestrator/aas_registry_client.py

import requests
import json
import subprocess
from pathlib import Path

BASYX_REGISTRY = "http://192.168.137.1:8081/registry"
GENERATE_SCRIPT = "src/aas/generate_from_config.py"  # 你的 AAS 自动生成器
TEMP_AAS_FILE = "temp_camera_aas.json"


class AASRegistryClient:
    
    @staticmethod
    def upload_aasx(aasx_path: str):
        url = "http://localhost:8081/upload?ignore-duplicates=true"
        with open(aasx_path, "rb") as f:
            files = {
                "file": (aasx_path, f, "application/octet-stream")
            }
            headers = {"Accept": "application/json"}
            res = requests.post(url, files=files, headers=headers)

        print(f"📤 Uploaded AASX → status={res.status_code}")
        print(f"↪ Response: {res.text}")
        
    @staticmethod
    def generate_aas_instance(endpoint: str):
        """
        调用你已有的 config→AAS 生成器，动态写 Endpoint 到 submodel
        """
        subprocess.run([
            "python3",
            GENERATE_SCRIPT,
            "--config", "src/aas/templates/camera_config.yaml",
            "--endpoint", endpoint,
            "--out", TEMP_AAS_FILE
        ], check=True)

        return Path(TEMP_AAS_FILE)

    @staticmethod
    def upload_or_update():
        """
        上传 AAS 文件到 BaSyx，如果存在则 UPDATE
        """
        with open(TEMP_AAS_FILE, "r") as f:
            aas_data = json.load(f)

        aas_id = aas_data["assetAdministrationShells"][0]["id"]

        r = requests.get(f"{BASYX_REGISTRY}/shell-descriptors/{aas_id}")

        if r.status_code == 200:
            print("🔁 AAS exists, updating…")
            requests.put(
                f"{BASYX_REGISTRY}/shell-descriptors/{aas_id}",
                json=aas_data
            )
        else:
            print("🆕 Uploading new AAS…")
            requests.post(
                f"{BASYX_REGISTRY}/shell-descriptors",
                json=aas_data
            )

        print(f"✅ AAS uploaded/updated: {aas_id}")

    @staticmethod
    def update_status(status: str):
        """
        PATCH 更新 Submodel 中 status 属性
        """
        url = f"{BASYX_REGISTRY}/submodels/CameraInterface/submodel-elements/status/value"
        requests.put(url, data=json.dumps(status))
        print(f"📌 AAS status updated → {status}")
