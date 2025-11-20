#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Unified AAS Builder (Camera + Ultrasonic)
=========================================
规则约定：
- 全局资产ID (globalAssetId) = 指纹ID = AAS 的 id
- 统一格式：
    urn:mt3900:sensor:<vendor>:<product>:<serial>

例如：
    urn:mt3900:sensor:05a3:9331:Ucamera001
    urn:mt3900:sensor:1a86:55d3:594C037906

只保留一个 File 元素：DriverFile
"""

from __future__ import annotations
import json
from pathlib import Path
import socket
import cv2
import pyudev


# ============================================================
# IEC Dictionary
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
    return {
        "modelType": "Property",
        "idShort": idShort,
        "valueType": valueType,
        "value": str(value),
        **({"semanticId": semantic_ref(semantic)} if semantic else {}),
    }


def clean(arr):
    return [x for x in arr if x is not None]


# ============================================================
# USB Fingerprint Helper
# ============================================================
def build_fingerprint(dev):
    """
    从 pyudev 设备提取 vendor/product/serial
    这里用 attributes，是树莓派上稳定可用的方式。
    """
    vendor = dev.attributes.get("idVendor")
    product = dev.attributes.get("idProduct")
    serial = dev.attributes.get("serial")

    if vendor:
        vendor = vendor.decode()
    if product:
        product = product.decode()
    if serial:
        serial = serial.decode()

    # 防止出现 None:None:None
    vendor = vendor or "unknownVendor"
    product = product or "unknownProduct"
    serial = serial or "unknownSerial"

    return {"vendor": vendor, "product": product, "serial": serial}


def build_global_asset_id(fp):
    """
    ✅ 这是全局资产ID (globalAssetId)，同时也作为 AAS 的 id 使用
    规则：urn:mt3900:sensor:vendor:product:serial
    """
    return f"urn:mt3900:sensor:{fp['vendor']}:{fp['product']}:{fp['serial']}"


# ============================================================
# USB DEVICE SCANNING
# ============================================================
def list_real_usb_devices():
    """只返回真实传感器 USB 设备（排除 root hub / hub）。"""
    ctx = pyudev.Context()
    result = []

    for dev in ctx.list_devices(subsystem="usb", DEVTYPE="usb_device"):
        vid = dev.attributes.get("idVendor")
        if not vid:
            continue
        vid = vid.decode()

        # Skip Linux root hub
        if vid == "1d6b":
            continue

        # Skip VIA internal hub
        if vid == "2109":
            continue

        result.append(dev)

    return result


def find_camera_device():
    """找到摄像头对应的真正 USB 设备 + 指纹（不再 Unknown）。"""
    ctx = pyudev.Context()

    for dev in ctx.list_devices(subsystem="video4linux"):
        devnode = dev.device_node
        if not devnode:
            continue

        # 🔥 一层一层向上找真正的 USB Device（带 idVendor/idProduct/serial）
        parent = dev
        usb_dev = None

        while parent:
            if parent.subsystem == "usb" and parent.device_type == "usb_device":
                usb_dev = parent
                break
            parent = parent.parent

        if not usb_dev:
            continue

        # 指纹
        fp = build_fingerprint(usb_dev)
        fp["devnode"] = devnode

        man = usb_dev.attributes.get("manufacturer")
        prod = usb_dev.attributes.get("product")

        fp["manufacturer"] = man.decode() if man else "Unknown"
        fp["name"] = prod.decode() if prod else "Unknown"

        # 调试输出一下，方便你确认
        print("🎥 Camera found:")
        print("  DevNode      :", devnode)
        print("  Vendor       :", fp['vendor'])
        print("  Product      :", fp['product'])
        print("  Serial       :", fp['serial'])
        print("  Manufacturer :", fp['manufacturer'])
        print("  Name         :", fp['name'])

        return fp

    return None


def find_ultrasonic_device():
    """找到带 ttyACM/ttyUSB 的 USB 串口设备（超声波传感器）。"""
    devs = list_real_usb_devices()

    for dev in devs:
        fp = build_fingerprint(dev)

        # 找 tty 子节点
        for ch in dev.children:
            if ch.device_node and ("ttyACM" in ch.device_node or "ttyUSB" in ch.device_node):
                fp["port"] = ch.device_node
                return fp

    return None


# ============================================================
# Camera Info
# ============================================================
def read_camera_caps(devnode):
    cap = cv2.VideoCapture(devnode)
    if not cap.isOpened():
        return {"width": 640, "height": 480, "fps": 30}

    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 640)
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 480)
    fps = int(cap.get(cv2.CAP_PROP_FPS) or 30)

    cap.release()
    return {"width": w, "height": h, "fps": fps}


def get_ip():
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
    smid = f"{global_asset_id}/submodel/AssetInterface"
    extra = interface_cfg["extra"]

    elements = []

    # ===== ONLY ONE FILE ELEMENT =====
    if "driver" in interface_cfg["files"]:
        elements.append(
            {
                "modelType": "File",
                "idShort": "DriverFile",
                "value": interface_cfg["files"]["driver"],
                "contentType": "text/plain",
            }
        )

    # Camera elements
    if sensor_cfg["type"] == "camera":
        frame = f"http://{interface_cfg['ip']}:{interface_cfg['port']}/frame"
        stream = f"http://{interface_cfg['ip']}:{interface_cfg['port']}{extra['stream']}"

        elements += [
            prop("FrameURL", frame, "xs:anyURI"),
            prop("StreamURL", stream, "xs:anyURI"),
            prop("Resolution", extra["resolution"]),
            prop("FPS", extra["fps"], "xs:int"),
        ]

    # Ultrasonic
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
# AAS Assembly
# ============================================================
def build_full(global_asset_id, sensor_cfg, interface_cfg):
    """
    ⚠ 注意：
    - AAS.id == assetInformation.globalAssetId == global_asset_id
    - global_asset_id = urn:mt3900:sensor:vendor:product:serial
    """
    shell = {
        "modelType": "AssetAdministrationShell",
        "id": global_asset_id,
        "idShort": f"AAS_{sensor_cfg['name']}",
        "assetInformation": {
            "assetKind": "Instance",
            "globalAssetId": global_asset_id,
        },
        "submodels": [
            {
                "type": "ModelReference",
                "keys": [{"type": "Submodel", "value": f"{global_asset_id}/submodel/TechnicalData"}],
            },
            {
                "type": "ModelReference",
                "keys": [{"type": "Submodel", "value": f"{global_asset_id}/submodel/AssetInterface"}],
            },
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

    # CAMERA
    try:
        cam = build_camera()
        (out / "camera_aas.json").write_text(json.dumps(cam, indent=2))
        print("📸 Camera AAS generated.")
    except Exception as e:
        print("⚠ No camera AAS:", e)

    # ULTRASONIC
    try:
        us = build_ultrasonic()
        (out / "ultrasonic_aas.json").write_text(json.dumps(us, indent=2))
        print("📡 Ultrasonic AAS generated.")
    except Exception as e:
        print("⚠ No ultrasonic AAS:", e)


if __name__ == "__main__":
    main()
