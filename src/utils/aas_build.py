#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Unified AAS Builder (Camera + Ultrasonic + Empty Template)
==========================================================

Rules:
- The globalAssetId is also the AAS ID.
- ID format is fixed:
      urn:mt3900:sensor:<vendor>:<product>:<serial>

Examples:
      urn:mt3900:sensor:05a3:9331:Ucamera001
      urn:mt3900:sensor:1a86:55d3:594C037906

This builder:
  ✓ Generates Camera AAS
  ✓ Generates Ultrasonic AAS
  ✓ Generates an empty template for new sensors
  ✓ Keeps only one File element: DriverFile
"""

from __future__ import annotations
import json
from pathlib import Path
import socket
import cv2
import pyudev


# ============================================================
# IEC Dictionary (common semantic IDs)
# ============================================================
IEC = {
    "Name": "0173-1#02-AAW338#001",
    "ManufacturerName": "0173-1#02-AAO677#002",
    "SensorType": "0173-1#01-AAP906#001",
}


def semantic_ref(iri: str):
    return {
        "type": "ExternalReference",
        "keys": [{"type": "GlobalReference", "value": iri}],
    }


def prop(idShort, value, valueType="xs:string", semantic=None):
    """Create a Property element with optional semantic link."""
    return {
        "modelType": "Property",
        "idShort": idShort,
        "valueType": valueType,
        "value": str(value),
        **({"semanticId": semantic_ref(semantic)} if semantic else {}),
    }


def clean(arr):
    """Remove None from list."""
    return [x for x in arr if x is not None]


# ============================================================
# USB Fingerprint
# ============================================================
def build_fingerprint(dev):
    """
    Extract vendor/product/serial from pyudev USB device.
    Using attributes ensures stability on Raspberry Pi.
    """
    vendor = dev.attributes.get("idVendor")
    product = dev.attributes.get("idProduct")
    serial = dev.attributes.get("serial")

    vendor = vendor.decode() if vendor else "unknownVendor"
    product = product.decode() if product else "unknownProduct"
    serial = serial.decode() if serial else "unknownSerial"

    return {"vendor": vendor, "product": product, "serial": serial}


def build_global_asset_id(fp):
    """URN: urn:mt3900:sensor:vendor:product:serial"""
    return f"urn:mt3900:sensor:{fp['vendor']}:{fp['product']}:{fp['serial']}"


# ============================================================
# USB Device Scanning
# ============================================================
def list_real_usb_devices():
    """
    Return real USB sensor devices.
    Skip Linux root hubs and VIA internal hubs.
    """
    ctx = pyudev.Context()
    result = []

    for dev in ctx.list_devices(subsystem="usb", DEVTYPE="usb_device"):
        vid = dev.attributes.get("idVendor")
        if not vid:
            continue
        vid = vid.decode()

        if vid in ["1d6b", "2109"]:  # Linux root hub / VIA hub
            continue

        result.append(dev)

    return result


def find_camera_device():
    """
    Locate the correct USB device behind the /dev/video* node.
    This ensures proper vendor/product/serial.
    """
    ctx = pyudev.Context()

    for dev in ctx.list_devices(subsystem="video4linux"):
        devnode = dev.device_node
        if not devnode:
            continue

        parent = dev
        usb_dev = None

        # Walk upward to find actual USB device
        while parent:
            if parent.subsystem == "usb" and parent.device_type == "usb_device":
                usb_dev = parent
                break
            parent = parent.parent

        if not usb_dev:
            continue

        fp = build_fingerprint(usb_dev)
        fp["devnode"] = devnode

        man = usb_dev.attributes.get("manufacturer")
        prod = usb_dev.attributes.get("product")

        fp["manufacturer"] = man.decode() if man else "Unknown"
        fp["name"] = prod.decode() if prod else "Unknown"

        print("🎥 Camera detected:")
        print("  DevNode      :", devnode)
        print("  Vendor       :", fp['vendor'])
        print("  Product      :", fp['product'])
        print("  Serial       :", fp['serial'])
        print("  Manufacturer :", fp['manufacturer'])
        print("  Name         :", fp['name'])

        return fp

    return None


def find_ultrasonic_device():
    """Look for USB-to-serial devices providing ttyUSB/ttyACM."""
    devs = list_real_usb_devices()

    for dev in devs:
        fp = build_fingerprint(dev)

        for ch in dev.children:
            if ch.device_node and ("ttyACM" in ch.device_node or "ttyUSB" in ch.device_node):
                fp["port"] = ch.device_node
                return fp

    return None


# ============================================================
# Camera Info
# ============================================================
def read_camera_caps(devnode):
    """Read resolution and FPS from camera using OpenCV."""
    cap = cv2.VideoCapture(devnode)
    if not cap.isOpened():
        return {"width": 640, "height": 480, "fps": 30}

    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 640)
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 480)
    fps = int(cap.get(cv2.CAP_PROP_FPS) or 30)
    cap.release()

    return {"width": w, "height": h, "fps": fps}


def get_ip():
    """Get local IP address of Raspberry Pi."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    s.close()
    return ip


# ============================================================
# Build Submodels
# ============================================================
def build_sm_technical(global_asset_id, cfg):
    """Build TechnicalData submodel."""
    smid = f"{global_asset_id}/submodel/TechnicalData"
    return {
        "modelType": "Submodel",
        "id": smid,
        "idShort": "TechnicalData",
        "kind": "Instance",
        "submodelElements": [
            {
                "modelType": "SubmodelElementCollection",
                "idShort": "GeneralInformation",
                "value": clean(
                    [
                        prop("Name", cfg["name"], semantic=IEC["Name"]),
                        prop("Manufacturer", cfg["manufacturer"], semantic=IEC["ManufacturerName"]),
                        prop("SensorType", cfg["type"], semantic=IEC["SensorType"]),
                        prop("Model", cfg["model"]),
                        prop("Category", cfg["category"]),
                    ]
                ),
            }
        ],
    }


def build_sm_interface(global_asset_id, sensor_cfg, interface_cfg):
    """Build AssetInterface submodel with DriverFile + sensor specific elements."""
    smid = f"{global_asset_id}/submodel/AssetInterface"
    extra = interface_cfg["extra"]

    elements = []

    # Only one File element
    if "driver" in interface_cfg["files"]:
        elements.append(
            {
                "modelType": "File",
                "idShort": "DriverFile",
                "value": interface_cfg["files"]["driver"],
                "contentType": "text/plain",
            }
        )

    if sensor_cfg["type"] == "camera":
        frame = f"http://{interface_cfg['ip']}:{interface_cfg['port']}/frame"
        stream = f"http://{interface_cfg['ip']}:{interface_cfg['port']}{extra['stream']}"

        elements += [
            prop("FrameURL", frame, "xs:anyURI"),
            prop("StreamURL", stream, "xs:anyURI"),
            prop("Resolution", extra["resolution"]),
            prop("FPS", extra["fps"], "xs:int"),
        ]

    if sensor_cfg["type"] == "ultrasonic":
        elements += [
            prop("Port", extra["port"]),
            prop("VSSPath", extra["vssPath"]),
            prop("Value", "0.0", "xs:double"),
        ]

    return {
        "modelType": "Submodel",
        "id": smid,
        "idShort": "AssetInterface",
        "kind": "Instance",
        "submodelElements": elements,
    }


# ============================================================
# Build AAS
# ============================================================
def build_full(global_asset_id, sensor_cfg, interface_cfg):
    """Assemble complete AAS structure."""
    shell = {
        "modelType": "AssetAdministrationShell",
        "id": global_asset_id,
        "idShort": f"AAS_{sensor_cfg['name']}",
        "assetInformation": {
            "assetKind": "Instance",
            "globalAssetId": global_asset_id,
        },
        "submodels": [
            {"type": "ModelReference", "keys": [{"type": "Submodel", "value": f"{global_asset_id}/submodel/TechnicalData"}]},
            {"type": "ModelReference", "keys": [{"type": "Submodel", "value": f"{global_asset_id}/submodel/AssetInterface"}]},
        ],
    }

    return {
        "assetAdministrationShells": [shell],
        "submodels": [
            build_sm_technical(global_asset_id, sensor_cfg),
            build_sm_interface(global_asset_id, sensor_cfg, interface_cfg),
        ],
    }


# ============================================================
# New Sensor Empty Template
# ============================================================
def build_empty_template():
    """
    Generate a completely empty AAS template so new sensors (Radar/Lidar/IMU)
    can be easily added.
    """
    template = {
        "assetAdministrationShells": [
            {
                "modelType": "AssetAdministrationShell",
                "id": "urn:mt3900:sensor:VENDOR:PRODUCT:SERIAL",
                "idShort": "AAS_NewSensor",
                "assetInformation": {
                    "assetKind": "Instance",
                    "globalAssetId": "urn:mt3900:sensor:VENDOR:PRODUCT:SERIAL"
                },
                "submodels": [
                    {
                        "type": "ModelReference",
                        "keys": [
                            {
                                "type": "Submodel",
                                "value": "urn:mt3900:sensor:VENDOR:PRODUCT:SERIAL/submodel/TechnicalData"
                            }
                        ]
                    },
                    {
                        "type": "ModelReference",
                        "keys": [
                            {
                                "type": "Submodel",
                                "value": "urn:mt3900:sensor:VENDOR:PRODUCT:SERIAL/submodel/AssetInterface"
                            }
                        ]
                    }
                ]
            }
        ],
        "submodels": [
            {
                "modelType": "Submodel",
                "id": "urn:mt3900:sensor:VENDOR:PRODUCT:SERIAL/submodel/TechnicalData",
                "idShort": "TechnicalData",
                "kind": "Instance",
                "submodelElements": []
            },
            {
                "modelType": "Submodel",
                "id": "urn:mt3900:sensor:VENDOR:PRODUCT:SERIAL/submodel/AssetInterface",
                "idShort": "AssetInterface",
                "kind": "Instance",
                "submodelElements": [
                    {
                        "modelType": "File",
                        "idShort": "DriverFile",
                        "value": "",
                        "contentType": "text/plain"
                    }
                ]
            }
        ]
    }

    Path("new_sensor_template.json").write_text(
        json.dumps(template, indent=2)
    )
    print("📄 New sensor template saved → new_sensor_template.json")


# ============================================================
# Build Camera AAS
# ============================================================
def build_camera(api_port=8000):
    cam = find_camera_device()
    if not cam:
        raise RuntimeError("No USB camera found")

    fp = {"vendor": cam["vendor"], "product": cam["product"], "serial": cam["serial"]}
    global_asset_id = build_global_asset_id(fp)

    caps = read_camera_caps(cam["devnode"])
    ip = get_ip()

    sensor_cfg = {
        "name": cam["name"],
        "type": "camera",
        "manufacturer": cam["manufacturer"],
        "model": cam["name"],
        "category": "VisionSensor",
    }

    interface_cfg = {
        "ip": ip,
        "port": api_port,
        "extra": {
            "stream": "/video",
            "resolution": f"{caps['width']}x{caps['height']}",
            "fps": caps["fps"],
        },
        "files": {
            "driver": "/aasx/files/camera_driver.py",
        },
    }

    return build_full(global_asset_id, sensor_cfg, interface_cfg)


# ============================================================
# Build Ultrasonic AAS
# ============================================================
def build_ultrasonic(vss_path="Vehicle.ADAS.ParkAssist.Ultrasonic.Front.Center.Distance"):
    us = find_ultrasonic_device()
    if not us:
        raise RuntimeError("No ultrasonic sensor found")

    fp = {"vendor": us["vendor"], "product": us["product"], "serial": us["serial"]}
    global_asset_id = build_global_asset_id(fp)

    sensor_cfg = {
        "name": f"Ultrasonic_{us['product']}",
        "type": "ultrasonic",
        "manufacturer": "Generic",
        "model": us["product"],
        "category": "DistanceSensor",
    }

    interface_cfg = {
        "ip": "none",
        "port": "rs485",
        "extra": {
            "port": us["port"],
            "vssPath": vss_path,
        },
        "files": {
            "driver": "/aasx/files/ultrasonic_driver.py",
        },
    }

    return build_full(global_asset_id, sensor_cfg, interface_cfg)


# ============================================================
# MAIN
# ============================================================
def main():
    out = Path(__file__).parent

    # Build CAMERA AAS
    try:
        cam = build_camera()
        (out / "camera_aas.json").write_text(json.dumps(cam, indent=2))
        print("📸 Camera AAS generated.")
    except Exception as e:
        print("⚠ No camera AAS:", e)

    # Build ULTRASONIC AAS
    try:
        us = build_ultrasonic()
        (out / "ultrasonic_aas.json").write_text(json.dumps(us, indent=2))
        print("📡 Ultrasonic AAS generated.")
    except Exception as e:
        print("⚠ No ultrasonic AAS:", e)

    # Build New Sensor Template
    build_empty_template()


if __name__ == "__main__":
    main()
