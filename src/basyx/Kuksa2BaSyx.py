# Kuksa2BaSyx.py
import subprocess
import json
import time
import re
import requests
import sys


# --------------------------------------------
# ✅ Kuksa Databroker Client (works WITHOUT docker network)
# --------------------------------------------
class KuksaClient:
    def __init__(self, server="192.168.0.180:55555"):
        self.server = server
        self.image = "ghcr.io/eclipse-kuksa/kuksa-databroker-cli:main"

    def _run(self, args):
        cmd = [
            "docker", "run", "-it", "--rm",
            self.image,
            "--server", self.server,
        ] + args

        print("CMD:", " ".join(cmd))
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout  # only stdout

    def publish(self, signal, value):
        out = self._run(["publish", signal, str(value)])
        print(f"[PUBLISH] {signal} -> {value} | {out.strip()}")
        return out.strip()

    def get(self, signal):
        out = self._run(["get", signal])
        m = re.search(rf"{signal}\s*[:|]\s*(.+)", out)
        if m:
            value = m.group(1).strip()
            print(f"[GET] {signal} = {value}")
            return value
        print(f"[GET] No value found for {signal}")
        return None


# --------------------------------------------
# ✅ Sync Kuksa → BaSyx AAS Property
# --------------------------------------------
class BaSyxSync:
    def __init__(self, vss_path, aas_property_url, server="192.168.0.180:55555"):
        self.vss_path = vss_path
        self.aas_property_url = aas_property_url
        self.kuksa = KuksaClient(server)

        print("\n✅ BaSyxSync initialized:")
        print(f"    VSS Path        = {self.vss_path}")
        print(f"    AAS Property URL= {self.aas_property_url}\n")

    # GET AAS property JSON
    def get_property_json(self):
        try:
            r = requests.get(self.aas_property_url)
            if r.status_code == 200:
                return r.json()
            print(f"⚠️ GET property failed (HTTP {r.status_code})")

            # ✅ 新增逻辑：直接退出程序
            print("❌ Cannot update AAS: property not found, program stopped.")
            sys.exit(1)

        except Exception as e:
            print(f"❌ GET error: {e}")
            print("❌ Cannot update AAS: program stopped.")
            sys.exit(1)

    # PUT to AAS (only update value)
    def put_property_json(self, new_value):
        data = self.get_property_json()
        if not data:
            print("❌ Cannot update AAS: empty JSON, program stopped.")
            sys.exit(1)

        data["value"] = new_value

        r = requests.put(
            self.aas_property_url,
            data=json.dumps(data),
            headers={"Content-Type": "application/json"}
        )
        print(f"➡️ PUT BaSyx: {r.status_code} | value={new_value}")

    # Loop: Kuksa → AAS
    def run(self, interval=1.0):
        print("🚦 Start syncing Kuksa → BaSyx (Ctrl + C to stop)\n")
        while True:
            value = self.kuksa.get(self.vss_path)
            if value is not None:
                self.put_property_json(value)
            time.sleep(interval)


# --------------------------------------------
# ✅ Command Line Run
# --------------------------------------------
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("\n❌ Usage:")
        print("  python Kuksa2BaSyx.py <vss_path> <aas_property_url> [interval seconds]")
        print("\nExample:")
        print("  python Kuksa2BaSyx.py Vehicle.Speed http://192.168.0.180:8081/.../value 1")
        sys.exit(1)

    vss_path = sys.argv[1]
    aas_property_url = sys.argv[2]
    interval = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0

    sync = BaSyxSync(vss_path=vss_path, aas_property_url=aas_property_url)
    sync.run(interval=interval)
