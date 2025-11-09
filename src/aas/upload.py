#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Upload generated AAS JSON to BaSyx (middleware only)
"""

import requests
from pathlib import Path
import sys


def upload_to_basyx(json_file: str, basyx_ip="192.168.137.1", port=8081):
    upload_url = f"http://{basyx_ip}:{port}/upload?ignore-duplicates=true"
    files = {"file": (Path(json_file).name, Path(json_file).read_bytes(), "application/json")}
    print(f"➡️ Upload JSON: {json_file} → {upload_url}")

    resp = requests.post(upload_url, files=files)
    if resp.status_code != 200:
        print(f"❌ Upload failed: {resp.status_code}\n{resp.text}")
        return False

    print("✅ JSON uploaded to BaSyx (/upload)")


if __name__ == "__main__":
    json_file = sys.argv[1] if len(sys.argv) > 1 else "sensor.json"
    basyx_ip = sys.argv[2] if len(sys.argv) > 2 else "192.168.137.1"

    if not Path(json_file).exists():
        print(f"❌ File not found: {json_file}")
        sys.exit(1)

    upload_to_basyx(json_file, basyx_ip=basyx_ip)
