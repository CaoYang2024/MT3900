import requests
import json

BASYX = "http://192.168.137.1:8081"

def upload_aas(aas_json):
    try:
        r = requests.post(
            f"{BASYX}/upload?ignore-duplicates=true",
            json=aas_json,
            timeout=5
        )
        return r.ok
    except Exception as e:
        print("❌ Upload error:", e)
        return False
