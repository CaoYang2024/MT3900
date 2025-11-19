#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
AAS Client for BaSyx AAS Environment 2.0
- List AAS
- Upload AAS JSON
- Delete AAS (Base64URL)
- Delete by name
- Delete latest
- Property read/write
- Mark Connected / Disconnected
"""

import json
import base64
import requests
from pathlib import Path

# ============================================================
# CONFIG
# ============================================================

BASYX_HOST = "http://192.168.137.1:8081"
UPLOAD_API = f"{BASYX_HOST}/upload?ignore-duplicates=true"


# ============================================================
# LIST / FIND
# ============================================================

def list_all_aas():
    """Return all AAS entries."""
    r = requests.get(f"{BASYX_HOST}/shells")

    if r.status_code != 200:
        print(f"❌ Cannot list AAS: {r.status_code}")
        return []

    return r.json().get("result", [])


def find_aas(keyword: str):
    """Return AAS where keyword appears in idShort or id."""
    keyword = keyword.lower()
    return [
        a for a in list_all_aas()
        if keyword in a["idShort"].lower() or keyword in a["id"].lower()
    ]


# ============================================================
# UPLOAD (JSON file)
# ============================================================

def upload_aas_file(path: str):
    """Upload AAS JSON file using multipart/form-data (same as Postman)."""

    filename = Path(path).name

    with open(path, "rb") as f:
        files = {
            "file": (filename, f, "application/json")
        }
        headers = {"Accept": "application/json"}

        print(f"⬆️ Uploading → {UPLOAD_API}")
        r = requests.post(UPLOAD_API, files=files, headers=headers)

    if r.status_code == 200:
        print("✅ Upload successful")
    else:
        print(f"❌ Upload failed {r.status_code}: {r.text}")


def register_or_update_aas(aas_json: dict, output_file: str):
    """Write JSON to file and upload."""
    Path(output_file).write_text(
        json.dumps(aas_json, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    print(f"📄 Saved → {output_file}")
    upload_aas_file(output_file)


# ============================================================
# DELETE AAS (BaSyx uses Base64URL format)
# ============================================================

def aas_id_to_b64(aas_id: str) -> str:
    """Convert AAS ID to BaSyx Base64URL format."""
    b64 = base64.urlsafe_b64encode(aas_id.encode()).decode()
    return b64.rstrip("=")


def delete_aas(aas_id: str):
    """Delete AAS using the correct Base64URL scheme."""
    b64id = aas_id_to_b64(aas_id)
    url = f"{BASYX_HOST}/shells/{b64id}"

    print(f"🗑 DELETE {url}")
    r = requests.delete(url)

    if r.status_code in (200, 204):
        print(f"   ✅ Deleted: {aas_id}\n")
    else:
        print(f"   ❌ Delete failed {r.status_code}: {r.text}\n")


def delete_aas_by_name(keyword: str):
    """Delete all AAS where keyword in idShort or id."""
    matches = find_aas(keyword)

    if not matches:
        print(f"❌ No AAS found containing '{keyword}'")
        return

    print(f"🔍 Found {len(matches)} AAS:")
    for a in matches:
        print(f" - {a['idShort']} ({a['id']})")

    print("\n🗑 Deleting...\n")
    for a in matches:
        delete_aas(a["id"])


def delete_latest_aas():
    """Delete the last AAS in the list."""
    all_aas = list_all_aas()
    if not all_aas:
        print("❌ No AAS found.")
        return

    last = all_aas[-1]
    print(f"🗑 Deleting latest: {last['idShort']} ({last['id']})")
    delete_aas(last["id"])


# ============================================================
# PROPERTY READ / WRITE
# ============================================================

def get_property(prop_url: str):
    r = requests.get(prop_url)
    if r.status_code != 200:
        print(f"❌ GET failed {r.status_code}: {r.text}")
        return None
    return r.json()


def put_property(prop_url: str, value, value_type="xs:string"):
    body = {
        "modelType": "Property",
        "valueType": value_type,
        "value": str(value)
    }
    r = requests.put(prop_url, json=body)

    if r.status_code in (200, 204):
        print(f"✅ PUT {prop_url} = {value}")
    else:
        print(f"❌ PUT failed {r.status_code}: {r.text}")


# ============================================================
# CONNECTED FLAG
# ============================================================

from src.utils.aas_discovery import discover_properties_for_shell


def mark_connected(aas_id: str):
    props = discover_properties_for_shell(BASYX_HOST, aas_id)
    ai = props.get("AssetInterface")

    if not ai or "Connected" not in ai:
        print("❌ Cannot find AssetInterface.Connected")
        return

    put_property(ai["Connected"], True, "xs:boolean")


def mark_disconnected(aas_id: str):
    props = discover_properties_for_shell(BASYX_HOST, aas_id)
    ai = props.get("AssetInterface")

    if not ai or "Connected" not in ai:
        print("❌ Cannot find AssetInterface.Connected")
        return

    put_property(ai["Connected"], False, "xs:boolean")
