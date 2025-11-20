#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Unified AAS Builder (Camera + Ultrasonic)
-----------------------------------------
你要求的“一个py文件版本”，统一 camera 和 ultrasonic 的 AAS 生成方式。

特点：
- camera 仍然保持使用 frame / video 接口 (从你的原代码复制)
- ultrasonic 复用同样的 submodel + conceptDescription 构造方式
- 未来你可以模块化拆分，现在先保持单文件
"""

from __future__ import annotations
import json
from pathlib import Path
import socket
import cv2
import pyudev


# ============================================================
# 0. IEC 61360 semantic dict
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
# build ConceptDescriptions
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
# build Submodels
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
                    prop(
                        "Manufacturer",
                        sensor_cfg.get("manufacturer"),
                        semantic=IEC["ManufacturerName"],
                    ),
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


def build_submodel_interface(aas_id: str, sensor_cfg: dict, interface_cfg: dict):
    """
    interface_cfg 根据 sensor 类型自动区分：
    - camera: HTTP FrameURL/StreamURL/resolution/fps
    - ultrasonic: RS485 port + vssPath + Value(新增)
    """
    sm_id = f"{aas_id}/submodel/AssetInterface"
    extra = interface_cfg.get("extra", {})
    elements = []

    if sensor_cfg["type"] == "camera":
        # Camera interface
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

    elif sensor_cfg["type"] == "ultrasonic":
        # Ultrasonic RS485 interface
        elements.extend(
            [
                prop("Port", extra.get("port")),
                prop("VSSPath", extra.get("vssPath")),

                # ⭐⭐⭐ 新增: ultrasonic 的 Value 属性 ⭐⭐⭐
                {
                    "modelType": "Property",
                    "idShort": "Value",
                    "valueType": "xs:double",
                    "value": "0.0"
                }
                # ⭐⭐⭐⭐⭐⭐⭐⭐⭐⭐⭐⭐⭐⭐⭐⭐⭐⭐⭐⭐⭐⭐⭐⭐⭐⭐⭐
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
# Camera info + caps
# ============================================================
def find_first_usb_camera():
    ctx = pyudev.Context()
    for dev in ctx.list_devices(subsystem="video4linux"):
        devnode = dev.device_node
        parent = dev.parent

        if not devnode or not parent:
            continue

        subsystem = parent.subsystem
        if subsystem not in ("usb", "usb_device"):
            parent2 = parent.parent
            if not parent2 or parent2.subsystem != "usb":
                continue
            parent = parent2

        return {
            "devnode": devnode,
            "vendor": parent.get("ID_VENDOR") or "UnknownVendor",
            "model": parent.get("ID_MODEL") or "UnknownModel",
            "serial": parent.get("ID_SERIAL_SHORT") or "",
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
# Camera version
# ============================================================
def build_camera_aas(api_port=8000):
    cam = find_first_usb_camera()
    if not cam:
        raise RuntimeError("No USB camera found")

    caps = read_camera_caps(cam["devnode"])
    ip = get_local_ip()

    aas_id = f"urn:mt3900:camera:{cam['serial'] or cam['devnode']}"

    sensor_cfg = {
        "aas_id": aas_id,
        "name": cam["model"],
        "type": "camera",
        "manufacturer": cam["vendor"],
        "model": cam["model"],
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
    }

    return build_full_aas_json(sensor_cfg, interface_cfg)


# ============================================================
# Ultrasonic version
# ============================================================
def build_ultrasonic_aas(devnode: str, vss_path: str, model="A01A"):
    aas_id = f"urn:mt3900:ultrasonic:{devnode.replace('/dev/','')}"

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
    }

    return build_full_aas_json(sensor_cfg, interface_cfg)


# ============================================================
# Master builder
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
                "keys": [{"type": "Submodel", "value": f"{aas_id}/submodel/TechnicalData"}],
            },
            {
                "type": "ModelReference",
                "keys": [{"type": "Submodel", "value": f"{aas_id}/submodel/AssetInterface"}],
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
