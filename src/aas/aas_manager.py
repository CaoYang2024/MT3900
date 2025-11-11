#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
AAS Lifecycle Manager
用于 USB 即插即用：
    插入传感器 → 自动生成 AAS → 上传到 BaSyx
    拔出传感器 → 自动删除 AAS

依赖：
    pip install requests pyyaml
"""

import subprocess
import requests
import json
from pathlib import Path


# --------------------------------------------------------
#  CONFIG (根据你的项目路径改这块)
# --------------------------------------------------------
BASYX_HOST = "http://192.168.137.1:8081"           # BaSyx AAS Environment endpoint
GENERATE_SCRIPT = "src/aas/generate_aas_from_config.py"
CONFIG_FILE = "src/aas/config.yaml"
OUTPUT_JSON = "/tmp/aas_sensor.json"               # AAS JSON temporary output
LAST_AAS_ID_FILE = "/tmp/aas_last_id.txt"          # Store last AAS ID for deletion


# --------------------------------------------------------
# Helper: read stored AAS ID
# --------------------------------------------------------
def _save_aas_id(aas_id: str):
    Path(LAST_AAS_ID_FILE).write_text(aas_id)


def _load_aas_id() -> str | None:
    if not Path(LAST_AAS_ID_FILE).exists():
        return None
    return Path(LAST_AAS_ID_FILE).read_text().strip()


# --------------------------------------------------------
# Step 1: Generate AAS JSON using your script
# --------------------------------------------------------
def generate_aas():
    print("\n📦 [AAS] Generating AAS from config.yaml ...")

    # 运行你的 generate_aas_from_config.py
    subprocess.run(["python3", GENERATE_SCRIPT, CONFIG_FILE, OUTPUT_JSON], check=True)

    data = json.loads(Path(OUTPUT_JSON).read_text(encoding="utf-8"))
    aas_id = data["assetAdministrationShells"][0]["id"]

    _save_aas_id(aas_id)

    print(f"✅ AAS JSON generated: {OUTPUT_JSON}")
    print(f"🔑 AAS ID: {aas_id}")

    return aas_id


# --------------------------------------------------------
# Step 2: Upload AAS JSON to BaSyx
# --------------------------------------------------------
def publish_aas():
    print("\n🚀 [AAS] Publishing to BaSyx AAS Environment ...")

    aas_json = Path(OUTPUT_JSON).read_text(encoding="utf-8")

    r = requests.post(
        f"{BASYX_HOST}/aasenv",
        data=aas_json,
        headers={"Content-Type": "application/json"}
    )

    if r.status_code in (200, 201, 204):
        print("✅ AAS successfully uploaded to BaSyx.")
    else:
        print(f"❌ Upload failed → {r.status_code} : {r.text}")


# --------------------------------------------------------
# Step 3: Delete AAS when USB removed
# --------------------------------------------------------
def delete_aas():
    aas_id = _load_aas_id()
    if not aas_id:
        print("⚠️ No AAS ID found. Nothing to delete.")
        return

    delete_url = f"{BASYX_HOST}/shells/{aas_id}"
    print(f"\n🗑 [AAS] Deleting AAS from BaSyx ...")
    print(f"➡ DELETE {delete_url}")

    r = requests.delete(delete_url)

    if r.status_code in (200, 204):
        print("✅ AAS deleted from BaSyx.")
        Path(LAST_AAS_ID_FILE).unlink(missing_ok=True)
    elif r.status_code == 404:
        print("⚠️ AAS not found (already deleted).")
    else:
        print(f"❌ Delete failed → {r.status_code} : {r.text}")


# --------------------------------------------------------
# One-shot workflow for USB hotplug system
# --------------------------------------------------------
def create_and_upload_aas():
    aas_id = generate_aas()
    publish_aas()
    return aas_id
