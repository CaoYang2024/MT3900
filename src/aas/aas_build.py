#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Auto AAS Generator for USB Camera (no YAML)
- Detect first /dev/video* camera via pyudev
- Read basic info: vendor, model, serial
- Open camera with OpenCV to get resolution + FPS
- Detect Pi IP address + API port
- Build AAS v3 JSON with:
  - TechnicalData submodel
  - AssetInterface submodel (FrameURL + StreamURL)
- Output: camera_aas.json (可用 AASX Package Explorer 导入并另存为 .aasx)
"""

from __future__ import annotations
import json
from pathlib import Path
import socket
import subprocess

import cv2
import pyudev


# ============================================================
# 0. IEC 61360 semantic dictionary
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


def prop_bool(idShort, value):
    return {
        "modelType": "Property",
        "idShort": idShort,
        "valueType": "xs:boolean",
        "value": "true" if value else "false",
    }


def clean(arr):
    return [x for x in arr if x is not None]


# ============================================================
# 1. 自动发现 USB 摄像头信息（/dev/videoX）
# ============================================================
def find_first_usb_camera():
    """
    返回:
    {
      "devnode": "/dev/video0",
      "vendor": "Logitech",
      "model": "C270",
      "serial": "12345678" or "",
    }
    找不到摄像头则返回 None
    """
    ctx = pyudev.Context()
    for dev in ctx.list_devices(subsystem="video4linux"):
        devnode = dev.device_node    # /dev/video0
        parent = dev.parent

        if not devnode:
            continue
        if parent is None:
            continue

        # 过滤掉不是 USB Camera 的（比如 bcm2835-isp）
        subsystem = parent.subsystem
        if subsystem not in ("usb", "usb-usbv2", "usb_device"):
            # 有些系统 parent 再往上一级才是 usb，可以往上爬一层
            parent2 = parent.parent
            if not parent2 or parent2.subsystem != "usb":
                continue
            parent = parent2

        vendor = parent.get("ID_VENDOR") or "UnknownVendor"
        model = parent.get("ID_MODEL") or "UnknownModel"
        serial = parent.get("ID_SERIAL_SHORT") or ""

        return {
            "devnode": devnode,
            "vendor": vendor,
            "model": model,
            "serial": serial,
        }

    return None


# ============================================================
# 2. 获取摄像头的分辨率 / FPS（用 OpenCV）
# ============================================================
def read_camera_caps(devnode: str):
    """
    打开摄像头，读出分辨率和 FPS
    返回:
      {
        "width": int,
        "height": int,
        "fps": int
      }
    """
    cap = cv2.VideoCapture(devnode)
    if not cap.isOpened():
        print(f"⚠️ Cannot open camera {devnode} to read caps, fallback to default 640x480@30")
        return {"width": 640, "height": 480, "fps": 30}

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 640)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 480)
    fps = int(cap.get(cv2.CAP_PROP_FPS) or 30)

    cap.release()
    return {"width": width, "height": height, "fps": fps}


# ============================================================
# 3. 获取树莓派的 IP（用于构造 API URL）
# ============================================================
def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # 不需要真的连上 8.8.8.8，只是借这个确定出站网卡 IP
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


# ============================================================
# 4. 构造 AAS 结构（直接用上次你给的模板）
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
    sm_id = f"{aas_id}/submodel/AssetInterface"

    ip = interface_cfg["ip"]
    port = interface_cfg["port"]
    extra = interface_cfg.get("extra", {})

    elements = []

    # 通用字段：Connected
    elements.append(prop_bool("Connected", True))

    # 这里我们针对摄像头
    # Frame URL
    frame_url = f"http://{ip}:{port}/frame"
    elements.append(prop("FrameURL", frame_url, valueType="xs:anyURI"))

    # Stream URL (MJPEG)
    stream_path = extra.get("stream", "/video")
    stream_url = f"http://{ip}:{port}{stream_path}"
    elements.append(prop("StreamURL", stream_url, valueType="xs:anyURI"))

    # 分辨率 / FPS
    if "resolution" in extra:
        elements.append(prop("Resolution", extra["resolution"]))

    if "fps" in extra:
        elements.append(prop("FPS", extra["fps"], valueType="xs:int"))

    return {
        "modelType": "Submodel",
        "id": sm_id,
        "idShort": "AssetInterface",
        "kind": "Instance",
        "submodelElements": elements,
    }


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


def build_aas_from_auto(camera_info: dict, caps: dict, ip: str, port: int = 8000):
    """
    camera_info:
      {devnode, vendor, model, serial}
    caps:
      {width, height, fps}
    ip: 树莓派当前可达 IP
    """
    serial = camera_info.get("serial") or camera_info["devnode"]
    aas_id = f"urn:mt3900:camera:{serial}"

    resolution_str = f"{caps['width']}x{caps['height']}"

    sensor_cfg = {
        "name": camera_info["model"],
        "type": "camera",
        "manufacturer": camera_info["vendor"],
        "model": camera_info["model"],
        "category": "VisionSensor",
    }

    interface_cfg = {
        "ip": ip,
        "port": port,
        "extra": {
            "stream": "/video",
            "resolution": resolution_str,
            "fps": caps["fps"],
        },
    }

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


# ============================================================
# 5. 主入口：一键自动生成 camera_aas.json
# ============================================================
def main(out_file: str = "camera_aas.json", api_port: int = 8000):
    cam = find_first_usb_camera()
    if not cam:
        print("❌ 没有找到 USB 摄像头 (/dev/video*)，无法生成 AAS")
        return

    print(f"✅ 找到摄像头: {cam['devnode']}  {cam['vendor']} {cam['model']} (serial={cam['serial'] or 'N/A'})")

    caps = read_camera_caps(cam["devnode"])
    print(f"   分辨率: {caps['width']}x{caps['height']}  FPS: {caps['fps']}")

    ip = get_local_ip()
    print(f"   侦测到树莓派 IP: {ip}  (假设 FastAPI 在 http://{ip}:{api_port})")

    aas_json = build_aas_from_auto(cam, caps, ip, api_port)

    Path(out_file).write_text(json.dumps(aas_json, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n🎉 AAS JSON 已自动生成 → {out_file}")
    print("   你可以在 AASX Package Explorer 里：File → Import → JSON → Save as .aasx")


if __name__ == "__main__":
    main()
