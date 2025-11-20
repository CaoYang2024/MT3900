#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Unified AAS Builder (Camera + Ultrasonic + File Elements)
AAS v3.0 compliant — PASS AAS Test Engine
"""

from __future__ import annotations
import json
from pathlib import Path
import socket
import cv2
import pyudev


# ============================================================
# IEC 61360 Dictionary
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
# AAS ID = USB Fingerprint
# ============================================================
def build_aas_id_from_fingerprint(fp):
    vid = fp.get("idVendor") or "unknown"
    pid = fp.get("idProduct") or "unknown"
    serial = fp.get("serial") or "noserial"
    unique = f"{vid}:{pid}:{serial}"
    return f"urn:mt3900:sensor:{unique}"


# ============================================================
# File Element — AAS v3.0 compliant
# ============================================================
def file_elem(idShort: str, path: str, content_type: str = "text/plain"):
    return {
        "modelType": "File",
        "idShort": idShort,
        "value": path,
        "contentType": content_type,   # ← AAS v3.0 required field
    }


# ============================================================
# Concept Descriptions
# ============================================================
def build_concept_descriptions():
    cds = []
    for key, iri in IEC.items():
        cds.append(
            {
                "idShort": key,
                "id": iri,
                "modelType": "ConceptDescription",
                "embeddedDataSpecifications": [
                    {
                        "dataSpecification": semantic_ref(
                            "https://admin-shell.io/DataSpecificationTemplates/DataSpecificationIec61360/3"
                        ),
                        "dataSpecificationContent": {
                            "modelType": "DataSpecificationIec61360",
                            "preferredName": [{"language": "en", "text": key}],
                            "definition": [
                                {
                                    "language": "en",
                                    "text": f"Definition of {key} according to IEC 61360",
                                }
                            ],
                        },
                    }
                ],
            }
        )
    return cds


# ============================================================
# TechnicalData Submodel
# ============================================================
def build_submodel_technical(aas_id: str, sensor_cfg: dict):
    sm_id = f"{aas_id}/submodel/TechnicalData"

    elements = [
        {
            "modelType": "SubmodelElementCollection",
            "idShort": "GeneralInformation",
            "value": clean(
                [
                    prop("Name", sensor_cfg.get("name"), semantic=IEC["Name"]),
                    prop("Manufacturer", sensor_cfg.get("manufacturer"), semantic=IEC["ManufacturerName"]),
                    prop("SensorType", sensor_cfg.get("type"), semantic=IEC["SensorType"]),
                    prop("Model", sensor_cfg.get("model")),
                    prop("Category", sensor_cfg.get("category")),
                ]
            ),
        }
    ]

    return {
        "modelType": "Submodel",
        "id": sm_id,
        "idShort": "TechnicalData",
        "kind": "Instance",
        "submodelElements": elements,
    }


# ============================================================
# AssetInterface Submodel
# ============================================================
def build_submodel_interface(aas_id: str, sensor_cfg: dict, interface_cfg: dict):
    sm_id = f"{aas_id}/submodel/AssetInterface"
    extra = interface_cfg.get("extra", {})
    elements = []

    # ===== File elements =====
    files_cfg = interface_cfg.get("files", {})
    if "driver" in files_cfg:
        elements.append(file_elem("DriverFile", files_cfg["driver"]))
    if "kuksa" in files_cfg:
        elements.append(file_elem("KuksaFile", files_cfg["kuksa"]))
    if "orchestrator" in files_cfg:
        elements.append(file_elem("OrchestratorFile", files_cfg["orchestrator"]))

    # ============================================================
    # Camera interface
    # ============================================================
    if sensor_cfg["type"] == "camera":
        frame_url = f"http://{interface_cfg['ip']}:{interface_cfg['port']}/frame"
        stream_url = f"http://{interface_cfg['ip']}:{interface_cfg['port']}{extra.get('stream', '/video')}"

        elements.extend(
            [
                prop("FrameURL", frame_url, valueType="xs:anyURI"),
                prop("StreamURL", stream_url, valueType="xs:anyURI"),
                prop("Resolution", extra.get("resolution")),
                prop("FPS", extra.get("fps"), valueType="xs:int"),
            ]
        )

    # ============================================================
    # Ultrasonic interface
    # ============================================================
    elif sensor_cfg["type"] == "ultrasonic":
        elements.extend(
            [
                prop("Port", extra.get("port")),
                prop("VSSPath", extra.get("vssPath")),
                {
                    "modelType": "Property",
                    "idShort": "Value",
                    "valueType": "xs:double",
                    "value": "0.0",
                },
            ]
        )

    return {
        "modelType": "Submodel",
        "id": sm_id,
        "idShort": "AssetInterface",
        "kind": "Instance",
        "submodelElements": clean(elements),
    }


# ============================================================
# USB Camera Detection
# ============================================================
def find_first_usb_camera():
    ctx = pyudev.Context()
    for dev in ctx.list_devices(subsystem="video4linux"):
        devnode = dev.device_node
        parent = dev.parent

        if not devnode or not parent:
            continue

        if parent.subsystem not in ("usb", "usb_device"):
            parent2 = parent.parent
            if not parent2 or parent2.subsystem != "usb":
                continue
            parent = parent2

        return {
            "devnode": devnode,
            "idVendor": parent.get("ID_VENDOR_ID"),
            "idProduct": parent.get("ID_MODEL_ID"),
            "serial": parent.get("ID_SERIAL_SHORT"),
            "manufacturer": parent.get("ID_VENDOR"),
            "product": parent.get("ID_MODEL"),
        }
    return None


def read_camera_caps(devnode: str):
    cap = cv2.VideoCapture(devnode)
    if not cap.isOpened():
        return {"width": 640, "height": 480, "fps": 30}

    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 640)
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 480)
    fps = int(cap.get(cv2.CAP_PROP_FPS) or 30)
    cap.release()
    return {"width": w, "height": h, "fps": fps}


def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


# ============================================================
# Camera AAS
# ============================================================
def build_camera_aas(api_port=8000):
    cam = find_first_usb_camera()
    if not cam:
        raise RuntimeError("No USB camera found")

    caps = read_camera_caps(cam["devnode"])
    ip = get_local_ip()

    # fingerprint → AAS ID
    aas_id = build_aas_id_from_fingerprint(cam)

    sensor_cfg = {
        "aas_id": aas_id,
        "name": cam["product"],
        "type": "camera",
        "manufacturer": cam["manufacturer"],
        "model": cam["product"],
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
            "driver": "/aasx/files/camera_driver.txt",
            "kuksa": "/aasx/files/camera_kuksa.yaml",
            "orchestrator": "/aasx/files/camera_orchestrator.txt",
        },
    }

    return build_full_aas_json(sensor_cfg, interface_cfg)


# ============================================================
# Ultrasonic AAS
# ============================================================
def build_ultrasonic_aas(devnode: str, model="A01A", vss_path="ADAS.Ultrasonic.Distance"):
    fp = {
        "idVendor": "1a86",
        "idProduct": "55d3",
        "serial": devnode.replace("/dev/", ""),
    }
    aas_id = build_aas_id_from_fingerprint(fp)

    sensor_cfg = {
        "aas_id": aas_id,
        "name": f"Ultrasonic_{model}",
        "type": "ultrasonic",
        "manufacturer": "Generic",
        "model": model,
        "category": "DistanceSensor",
    }

    interface_cfg = {
        "ip": "none",
        "port": "rs485",
        "extra": {
            "port": devnode,
            "vssPath": vss_path,
        },
        "files": {
            "driver": "/aasx/files/ultrasonic_driver.txt",
            "kuksa": "/aasx/files/ultrasonic_kuksa.yaml",
            "orchestrator": "/aasx/files/ultrasonic_orchestrator.txt",
        },
    }

    return build_full_aas_json(sensor_cfg, interface_cfg)


# ============================================================
# Master JSON Builder
# ============================================================
def build_full_aas_json(sensor_cfg, interface_cfg):
    aas_id = sensor_cfg["aas_id"]

    shell = {
        "modelType": "AssetAdministrationShell",
        "idShort": f"AAS_{sensor_cfg['name']}",
        "id": aas_id,
        "assetInformation": {
            "assetKind": "Instance",
            "globalAssetId": aas_id,
        },
        "submodels": [
            {
                "type": "ModelReference",
                "keys": [
                    {"type": "Submodel", "value": f"{aas_id}/submodel/TechnicalData"}
                ],
            },
            {
                "type": "ModelReference",
                "keys": [
                    {"type": "Submodel", "value": f"{aas_id}/submodel/AssetInterface"}
                ],
            },
        ],
    }

    return {
        "assetAdministrationShells": [shell],
        "submodels": [
            build_submodel_technical(aas_id, sensor_cfg),
            build_submodel_interface(aas_id, sensor_cfg, interface_cfg),
        ],
        "conceptDescriptions": build_concept_descriptions(),
    }


# ============================================================
# MAIN: Save JSON to current directory
# ============================================================
def main():
    out_dir = Path(__file__).parent

    # CAMERA
    try:
        cam_aas = build_camera_aas()
        cam_path = out_dir / "camera_aas.json"
        cam_path.write_text(json.dumps(cam_aas, indent=2, ensure_ascii=False))
        print(f"📸 Camera AAS saved → {cam_path}")
    except Exception as e:
        print(f"No camera detected, skipping camera AAS ({e})")

    # ULTRASONIC
    ultra = build_ultrasonic_aas("/dev/ttyUSB0")
    ultra_path = out_dir / "ultrasonic_aas.json"
    ultra_path.write_text(json.dumps(ultra, indent=2, ensure_ascii=False))
    print(f"📡 Ultrasonic AAS saved → {ultra_path}")


if __name__ == "__main__":
    main()
