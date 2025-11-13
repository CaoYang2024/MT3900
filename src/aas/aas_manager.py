#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
from pathlib import Path
import requests
from src.utils.aas_discovery import discover_properties_for_shell


BASYX_HOST = "http://192.168.137.1:8081"
UPLOAD_API = f"{BASYX_HOST}/upload?ignore-duplicates=true"
OUTPUT_JSON = "/tmp/aas_sensor.json"


# ===========================================================
# Upload AAS JSON to BaSyx
# ===========================================================
def upload_json(json_path: str):
    print(f"\n🚀 Uploading AAS JSON → {UPLOAD_API}")

    with open(json_path, "rb") as f:
        r = requests.post(
            UPLOAD_API,
            files={"file": ("aas.json", f, "application/json")}
        )

    if r.status_code == 200:
        print("✅ Upload successful.\n")
    else:
        print(f"❌ Upload failed {r.status_code}: {r.text}\n")


def register_or_update_aas(aas_json: dict):
    Path(OUTPUT_JSON).write_text(json.dumps(aas_json, ensure_ascii=False, indent=2))
    print(f"📄 Saved → {OUTPUT_JSON}")
    upload_json(OUTPUT_JSON)


# ===========================================================
# Find Connected URL in AssetInterface
# ===========================================================
def find_connected_url(aas_id: str):
    print(f"\n🔍 Discovering Connected in AssetInterface → {aas_id}")

    try:
        props = discover_properties_for_shell(BASYX_HOST, aas_id)
    except Exception as e:
        print(f"❌ Discovery failed: {e}")
        return None

    if "AssetInterface" not in props:
        print("❌ AssetInterface not found.")
        return None

    ai = props["AssetInterface"]

    if "Connected" not in ai:
        print("❌ Connected not found.")
        return None

    print(f"  ✅ Found URL: {ai['Connected']}")
    return ai["Connected"]


# ===========================================================
# PUT update (stable for boolean-as-string)
# ===========================================================
def put_property(url: str, value: str):
    """
    PUT full Property object.
    value should be "true" or "false" (string).
    """
    body = {
        "idShort": "Connected",
        "modelType": "Property",
        "valueType": "xs:boolean",
        "value": value     # keep string format
    }

    print(f"➡ PUT {url}")
    print(f"➡ BODY: {body}")

    r = requests.put(
        url,
        json=body,
        headers={"Content-Type": "application/json"}
    )

    if r.status_code in (200, 204):
        print("✅ PUT success.")
        return True
    else:
        print(f"❌ PUT failed {r.status_code}: {r.text}")
        return False


# ===========================================================
# Public API
# ===========================================================
def mark_disconnected(aas_id: str):
    print(f"\n🔌 Marking disconnected → {aas_id}")

    url = find_connected_url(aas_id)
    if not url:
        return

    put_property(url, "false")


def mark_connected(aas_id: str):
    print(f"\n🔌 Marking connected → {aas_id}")

    url = find_connected_url(aas_id)
    if not url:
        return

    put_property(url, "true")


# ===========================================================
# Test Entry
# ===========================================================
if __name__ == "__main__":
    print("=== AAS Manager Test ===")
    aas_id = input("Enter AAS ID: ").strip()

    print("1. mark_connected")
    print("2. mark_disconnected")
    ch = input("Select (1/2): ").strip()

    if ch == "1":
        mark_connected(aas_id)
    elif ch == "2":
        mark_disconnected(aas_id)
    else:
        print("Invalid choice.")
