#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import requests
from pathlib import Path

BASYX_HOST = "http://192.168.137.1:8081"
UPLOAD_API = f"{BASYX_HOST}/upload?ignore-duplicates=true"
OUTPUT_JSON = "/tmp/aas_sensor.json"

# ✅ 先硬编码 PATCH URL（确保 demo 成功）
CONNECTED_PATCH_URL = (
    "http://192.168.137.1:8081/submodels/"
    "dXJuOm10MzkwMDp1c2I6VVNCLUNhbWVyYS1Vbmtub3duL3N1Ym1vZGVsL0Fzc2V0SW50ZXJmYWNl"
    "/submodel-elements/Connected/$value"
)

def upload_json(json_path: str):
    print(f"\n🚀 Uploading AAS JSON → {UPLOAD_API}")

    with open(json_path, "rb") as f:
        r = requests.post(
            UPLOAD_API,
            files={"file": ("sensor.json", f, "application/json")}
        )

    if r.status_code == 200:
        print("✅ JSON uploaded successfully to BaSyx.\n")
    else:
        print(f"❌ Upload failed: {r.status_code} → {r.text}\n")


def register_or_update_aas(aas_json: dict):
    Path(OUTPUT_JSON).write_text(json.dumps(aas_json, indent=2, ensure_ascii=False))
    print(f"📄 JSON saved → {OUTPUT_JSON}")
    upload_json(OUTPUT_JSON)


def mark_disconnected(aas_id: str):
    print(f"\n🔌 Updating AAS Connected=false → {aas_id}")
    print(f"➡ PATCH URL: {CONNECTED_PATCH_URL}")
    print(f"➡ Body: false")

    r = requests.patch(
        CONNECTED_PATCH_URL,
        data=json.dumps(False),
        headers={"Content-Type": "application/json"}
    )

    if r.status_code in (200, 204):
        print("✅ Connected=false updated!")
    else:
        print(f"❌ PATCH failed → {r.status_code}, {r.text}")
