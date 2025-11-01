# kuksa_to_basyx.py

import subprocess
import json
import time
import re
import requests
import sys


class BaSyxSync:
    """
    Sync data from Kuksa VSS → BaSyx AAS Property
    """

    def __init__(self,
                 vss_path: str,
                 aas_property_url: str,
                 network="kuksa",
                 server="Server:55555",
                 image="ghcr.io/eclipse-kuksa/kuksa-databroker-cli:main"):

        self.vss_path = vss_path
        self.aas_property_url = aas_property_url
        self.network = network
        self.server = server
        self.image = image

        print(f"✅ BaSyxSync init:")
        print(f"    VSS Path        = {self.vss_path}")
        print(f"    AAS Property URL= {self.aas_property_url}")


    # -------------------
    # Kuksa Databroker: GET value from VSS signal
    # -------------------
    def get_from_kuksa(self):
        cmd = [
            "docker", "run",
            "-t", "--rm",
            "--network", self.network,
            "-e", "TERM=dumb",
            self.image, "--server", self.server,
            "get", self.vss_path
        ]

        res = subprocess.run(cmd, capture_output=True, text=True)
        output = (res.stdout or "") + (res.stderr or "")

        match = re.search(fr"{re.escape(self.vss_path)}:\s*(.+)", output)
        if not match:
            print(f"⚠️   No value returned from Kuksa: {output}")
            return None

        return match.group(1).strip()


    # -------------------
    # BaSyx REST PUT update submodel property
    # -------------------
    def put_to_basyx(self, value):
        payload = {
            "modelType": "Property",
            "value": str(value),
            "valueType": "xs:string",
            "displayName": [{"language": "en", "text": self.vss_path}],
        }

        r = requests.put(
            self.aas_property_url,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"}
        )

        print(f"➡️ PUT BaSyx: {r.status_code} | value={value}")


    # -------------------
    # Loop: Get → Sync → Sleep
    # -------------------
    def run(self, interval=2):
        print("🚦 Start syncing Kuksa → BaSyx (Ctrl + C to stop)")
        while True:
            value = self.get_from_kuksa()
            if value is not None:
                self.put_to_basyx(value)
            time.sleep(interval)


# ------------------------------------------------------
# ✅ Command line usage
# ------------------------------------------------------
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("\n❌ Usage:")
        print("  python kuksa_to_basyx.py <vss_path> <aas_property_url> [interval]\n")
        print("Example:")
        print("  python kuksa_to_basyx.py Vehicle.Speed "
              "http://localhost:8081/submodels/.../submodel-elements/Value\n")
        sys.exit(1)

    vss_path = sys.argv[1]
    aas_property_url = sys.argv[2]
    interval = float(sys.argv[3]) if len(sys.argv) > 3 else 2.0

    sync = BaSyxSync(vss_path=vss_path, aas_property_url=aas_property_url)
    sync.run(interval=interval)
