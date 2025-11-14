# src/aas/aas_manager.py
import json
from pathlib import Path
import requests
from src.utils.aas_discovery import discover_properties_for_shell

BASYX_HOST = "http://192.168.137.1:8081"
UPLOAD_API = f"{BASYX_HOST}/upload?ignore-duplicates=true"
OUTPUT_JSON = "/tmp/aas_sensor.json"


def register_or_update_aas(aas_json: dict):
    Path(OUTPUT_JSON).write_text(json.dumps(aas_json, indent=2), encoding="utf-8")

    print(f"\n📄 Saved → {OUTPUT_JSON}")
    print(f"🚀 Uploading AAS JSON → {UPLOAD_API}")

    with open(OUTPUT_JSON, "rb") as f:
        r = requests.post(
            UPLOAD_API,
            files={"file": ("aas.json", f, "application/json")}
        )

    if r.status_code == 200:
        print("✅ Upload successful.\n")
    else:
        print(f"❌ Upload failed {r.status_code}: {r.text}\n")


def find_value_url(aas_id: str, id_short: str):
    props = discover_properties_for_shell(BASYX_HOST, aas_id)
    if "AssetInterface" not in props:
        print("❌ AssetInterface not found")
        return None

    sm = props["AssetInterface"]
    if id_short not in sm:
        print(f"❌ Property {id_short} not found")
        return None

    return sm[id_short]


def put_value(aas_id: str, id_short: str, value):
    url = find_value_url(aas_id, id_short)
    if not url:
        return

    body = {
        "idShort": id_short,
        "modelType": "Property",
        "valueType": "xs:double",
        "value": str(value)
    }

    r = requests.put(url, json=body, headers={"Content-Type": "application/json"})

    if r.status_code in (200, 204):
        print(f"✅ PUT {id_short}={value}")
    else:
        print(f"❌ PUT failed {r.status_code}: {r.text}")
