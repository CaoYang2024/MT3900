#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Ultrasonic Driver — Container Ready
-----------------------------------
This driver is designed to run inside a Docker container.
It acts as a bridge between the Physical Asset (RS485 Sensor),
the Digital Twin (BaSyx AAS), and the Data Broker (Kuksa).

Flow:
1. Starts and reads ENV variables (AAS_SERVER, AAS_ID, KUKSA...).
2. Queries AAS Server to find the 'AssetInterface' submodel.
3. Retrieves 'Port' and 'VSSPath' configuration from the AAS.
4. Auto-detects the physical serial port and updates AAS if different.
5. Loop: Reads Sensor -> Pushes to Kuksa (gRPC) -> Pushes to AAS (HTTP).
"""

import os
import time
import glob
import sys
import base64
import logging
import requests
import minimalmodbus
import serial
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from kuksa_client.grpc import VSSClient, Datapoint

# ---------------------------------------------------------
# Logging Setup
# ---------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger("driver")

# ---------------------------------------------------------
# Environment Variables (Configuration from Docker)
# ---------------------------------------------------------
# The URL of the BaSyx AAS Server (e.g., http://192.168.1.5:8081)
AAS_SERVER = os.environ.get("AAS_SERVER")

# The specific AAS ID for this device (e.g., urn:my-company:sensor:01)
AAS_ID = os.environ.get("AAS_ID")

# Kuksa Databroker Connection Details
KUKSA_ADDR = os.environ.get("KUKSA_ADDR", "localhost")
KUKSA_PORT = int(os.environ.get("KUKSA_PORT", "55555"))

# Optional: Force a specific serial port (skip auto-detection)
FORCE_PORT = os.environ.get("SENSOR_PORT", None)

VALUE_IDSHORT = "Value"

# ---------------------------------------------------------
# HTTP Session Factory (Performance & Retry)
# ---------------------------------------------------------
def create_session():
    """Creates a requests session with retries and keep-alive."""
    session = requests.Session()
    # Retry strategy for network glitches
    retries = Retry(total=3, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retries)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

# Global session instance
http = create_session()

# ---------------------------------------------------------
# Utility Helpers
# ---------------------------------------------------------
def b64url(s: str):
    """Encodes a string to Base64 URL-safe format (for BaSyx API)."""
    return base64.urlsafe_b64encode(s.encode()).decode().rstrip("=")

def find_real_port():
    """Scans for available RS485/USB serial devices."""
    if FORCE_PORT:
        log.info(f"🔧 Using forced port from ENV: {FORCE_PORT}")
        return FORCE_PORT
        
    # Check common Linux device paths
    ports = glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*")
    
    if not ports:
        return None
    
    # Return the first found port
    return ports[0]

# ---------------------------------------------------------
# AAS Logic: Resolve Configuration
# ---------------------------------------------------------
def resolve_asset_interface():
    """
    Queries the AAS Server to find the Submodel ID, Port, and VSSPath.
    """
    if not AAS_ID or not AAS_SERVER:
        log.error("❌ Critical Error: AAS_SERVER or AAS_ID not set in Environment.")
        sys.exit(1)

    log.info(f"🔧 Resolving configuration for AAS ID: {AAS_ID}")

    try:
        # 1. Fetch the AAS Shell to find Submodel References
        enc_shell = b64url(AAS_ID)
        shell_url = f"{AAS_SERVER}/shells/{enc_shell}"
        
        resp = http.get(shell_url, timeout=5)
        resp.raise_for_status()
        shell_raw = resp.json()
        
        # Handle BaSyx JSON wrapper if present
        shell = shell_raw.get("result", shell_raw)

        # 2. Find the 'AssetInterface' Submodel Reference
        asset_sm_iri = None
        for ref in shell.get("submodels", []):
            try:
                # Check keys for 'AssetInterface'
                key_val = ref["keys"][0]["value"]
                if "AssetInterface" in key_val: 
                    asset_sm_iri = key_val
                    break
            except (KeyError, IndexError):
                continue

        if not asset_sm_iri:
            log.error("❌ 'AssetInterface' submodel not found in AAS.")
            sys.exit(1)

        # 3. Fetch Submodel Elements (Port, VSSPath)
        enc_sm = b64url(asset_sm_iri)
        sm_url = f"{AAS_SERVER}/submodels/{enc_sm}/submodel-elements"
        
        sm_resp = http.get(sm_url, timeout=5)
        sm_resp.raise_for_status()
        elems = sm_resp.json().get("result", [])

        port = None
        vss_path = None

        for elem in elems:
            sid = elem.get("idShort")
            if sid == "Port":
                port = elem.get("value")
            elif sid == "VSSPath":
                vss_path = elem.get("value")

        if not port:
            log.error("❌ 'Port' element not found in AssetInterface.")
            sys.exit(1)

        log.info(f"🔌 Port defined in AAS: {port}")
        log.info(f"📡 VSSPath defined in AAS: {vss_path}")

        return port, vss_path, enc_sm

    except Exception as e:
        log.critical(f"❌ Failed to resolve AAS configuration: {e}")
        sys.exit(1)

# ---------------------------------------------------------
# AAS Logic: Updates
# ---------------------------------------------------------
def update_aas_port(enc_sm, new_port):
    """Updates the 'Port' property in the AAS if hardware changed."""
    url = f"{AAS_SERVER}/submodels/{enc_sm}/submodel-elements/Port"
    body = {
        "idShort": "Port",
        "modelType": "Property",
        "valueType": "xs:string",
        "value": new_port,
    }
    try:
        r = http.put(url, json=body, timeout=2)
        log.info(f"🔄 AAS Port updated to: {new_port} (Status: {r.status_code})")
    except Exception as e:
        log.error(f"❌ Failed to update AAS Port: {e}")

def update_aas_value(enc_sm, value):
    """Pushes the sensor value to the AAS."""
    url = f"{AAS_SERVER}/submodels/{enc_sm}/submodel-elements/{VALUE_IDSHORT}"
    body = {
        "idShort": VALUE_IDSHORT,
        "modelType": "Property",
        "valueType": "xs:double",
        "value": str(value)
    }
    try:
        # Fast non-blocking PUT
        http.put(url, json=body, timeout=1) 
    except Exception as e:
        log.warning(f"⚠ AAS Sync failed: {e}")

# ---------------------------------------------------------
# Hardware Driver (Modbus)
# ---------------------------------------------------------
REGISTER = 0x0101
BAUDRATE = 9600
SLAVE_ADDR = 1

class Ultrasonic:
    def __init__(self, port):
        self.instrument = minimalmodbus.Instrument(port, SLAVE_ADDR)
        self.instrument.serial.baudrate = BAUDRATE
        self.instrument.serial.timeout = 0.2
        self.instrument.mode = minimalmodbus.MODE_RTU
        self.instrument.clear_buffers_before_each_transaction = True

    def read(self):
        try:
            # Function code 3: Read Holding Registers
            mm = self.instrument.read_register(REGISTER, 0, functioncode=3)
            return mm / 1000.0 # Convert mm to meters
        except Exception:
            return None

# ---------------------------------------------------------
# Main Execution
# ---------------------------------------------------------
def main():
    log.info("🚀 Starting Driver Container...")

    # 1. Resolve Configuration from AAS (Plug and Play)
    port_from_aas, vss_path, enc_sm_id = resolve_asset_interface()

    # 2. Hardware Detection
    real_port = find_real_port()
    if not real_port:
        log.error("❌ No RS485 device detected on host.")
        sys.exit(1)

    # 3. Self-Correction (Update AAS if port changed)
    if real_port != port_from_aas:
        log.warning(f"⚠️ Port mismatch! AAS: {port_from_aas}, Real: {real_port}. Updating AAS...")
        update_aas_port(enc_sm_id, real_port)
    else:
        log.info(f"✅ Port matches hardware: {real_port}")

    # 4. Initialize Hardware Connection
    try:
        sensor = Ultrasonic(real_port)
        log.info("✅ Sensor initialized.")
    except Exception as e:
        log.error(f"❌ Failed to open serial port: {e}")
        sys.exit(1)

    # 5. Initialize Kuksa Connection
    kuksa = VSSClient(KUKSA_ADDR, KUKSA_PORT)
    try:
        kuksa.connect()
        log.info(f"🔗 Connected to Kuksa Databroker at {KUKSA_ADDR}:{KUKSA_PORT}")
    except Exception as e:
        log.warning(f"⚠ Failed to connect to Kuksa: {e}")

    log.info("🟢 Driver running. Publishing data...")

    # 6. Main Loop
    while True:
        start_time = time.time()
        
        # --- READ ---
        val = sensor.read()
        
        if val is not None:
            log.info(f"📏 Distance: {val:.3f} m")

            # --- PUBLISH TO KUKSA ---
            if vss_path:
                try:
                    if kuksa.connected:
                        kuksa.set_current_values({ vss_path: Datapoint(float(val)) })
                except Exception as e:
                    log.warning(f"   [Kuksa] Error: {e}")
                    # Auto-reconnect logic could go here

            # --- PUBLISH TO BASYX ---
            update_aas_value(enc_sm_id, val)
        else:
            log.warning("⚠ Sensor read timed out")

        # Rate Limiting (~3Hz)
        elapsed = time.time() - start_time
        time.sleep(max(0.1, 0.3 - elapsed))

if __name__ == "__main__":
    main()