#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Universal AAS Generator (Ultrasonic / Camera / Future Sensors)
- Creates TechnicalData
- Creates AssetInterface
- Supports dynamic fields from config['interface']['extra']
"""

from __future__ import annotations
import json
from pathlib import Path
import yaml

# ========== IEC 61360 Semantic Dictionary ==========
IEC = {
    "Name": "0173-1#02-AAW338#001",
    "ManufacturerName": "0173-1#02-AAO677#002",
    "SensorType": "0173-1#01-AAP906#001",
}

def semantic_ref(iri: str):
    return {
        "type": "ExternalReference",
        "keys": [{"type": "GlobalReference", "value": iri}]
    }

def prop(idShort, value, valueType="xs:string", semantic=None):
    return {
        "modelType": "Property",
        "idShort": idShort,
        "valueType": valueType,
        "value": str(value),
        **({"semanticId": semantic_ref(semantic)} if semantic else {})
    }

def prop_bool(idShort, value):
    return {
        "modelType": "Property",
        "idShort": idShort,
        "valueType": "xs:boolean",
        "value": "true" if value else "false"
    }

def clean(arr):
    return [x for x in arr if x is not None]


# ===========================================================================
# 1. TechnicalData Submodel
# ===========================================================================
def build_submodel_technical(aas_id: str, cfg: dict):
    s = cfg["sensor"]

    sm_id = f"{aas_id}/submodel/TechnicalData"

    elements = [
        {
            "modelType": "SubmodelElementCollection",
            "idShort": "GeneralInformation",
            "value": clean([
                prop("Name", s.get("name"), semantic=IEC["Name"]),
                prop("Manufacturer", s.get("manufacturer"), semantic=IEC["ManufacturerName"]),
                prop("SensorType", s.get("type"), semantic=IEC["SensorType"]),
                prop("Model", s.get("model")),
                prop("Category", s.get("category")),
            ])
        }
    ]

    return {
        "modelType": "Submodel",
        "id": sm_id,
        "idShort": "TechnicalData",
        "kind": "Instance",
        "submodelElements": elements
    }


# ===========================================================================
# 2. AssetInterface Submodel (supports ultrasonic + camera)
# ===========================================================================
def build_submodel_interface(aas_id: str, cfg: dict):
    itf = cfg["interface"]
    extra = itf.get("extra", {})
    sensor_type = cfg["sensor"]["type"].lower()

    sm_id = f"{aas_id}/submodel/AssetInterface"

    elements = []

    # ----- Common Field -----
    elements.append(prop_bool("Connected", itf.get("connected", False)))

    # ===================================================================
    # Ultrasonic Sensor
    # ===================================================================
    if sensor_type == "ultrasonic":
        if "vssPath" in extra:
            elements.append(prop("VSSPath", extra["vssPath"]))

        if "unit" in extra:
            elements.append(prop("Unit", extra["unit"]))

        if "api" in extra:
            full_api = f"http://{itf['ip']}:{itf['port']}{extra['api']}"
            elements.append(prop("API", full_api, valueType="xs:anyURI"))

        # 动态 PUT 的属性（Value）
        if "valueIdShort" in extra:
            elements.append({
                "modelType": "Property",
                "idShort": extra["valueIdShort"],
                "valueType": "xs:double",
                "value": "0"     # 初始值
            })

    # ===================================================================
    # Camera (for future sensors)
    # ===================================================================
    elif sensor_type == "camera":
        stream = extra.get("stream", "/stream")
        url = f"http://{itf['ip']}:{itf['port']}{stream}"
        elements.append(prop("StreamURL", url, valueType="xs:anyURI"))

        if "resolution" in extra:
            elements.append(prop("Resolution", extra["resolution"]))

        if "fps" in extra:
            elements.append(prop("FPS", extra["fps"], valueType="xs:int"))

    # ===================================================================
    # Unknown type
    # ===================================================================
    else:
        elements.append(prop("Info", f"Unsupported sensor type: {sensor_type}"))

    # Return final AssetInterface Submodel
    return {
        "modelType": "Submodel",
        "id": sm_id,
        "idShort": "AssetInterface",
        "kind": "Instance",
        "submodelElements": elements,
    }


# ===========================================================================
# 3. Concept Descriptions
# ===========================================================================
def build_concept_descriptions():
    cds = []
    for key, iri in IEC.items():
        cds.append({
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
                        "definition": [{"language": "en", "text": f"Definition of {key} according to IEC 61360"}]
                    }
                }
            ]
        })
    return cds


# ===========================================================================
# 4. Build AAS Root
# ===========================================================================
def build_aas(cfg: dict):
    aas_id = cfg["id"]

    shell = {
        "modelType": "AssetAdministrationShell",
        "idShort": f"AAS_{cfg['sensor']['name']}",
        "id": aas_id,
        "assetInformation": {
            "assetKind": "Instance",
            "globalAssetId": aas_id,
        },
        "submodels": [
            {"type": "ModelReference", "keys": [{"type": "Submodel", "value": f"{aas_id}/submodel/TechnicalData"}]},
            {"type": "ModelReference", "keys": [{"type": "Submodel", "value": f"{aas_id}/submodel/AssetInterface"}]},
        ],
    }

    return {
        "assetAdministrationShells": [shell],
        "submodels": [
            build_submodel_technical(aas_id, cfg),
            build_submodel_interface(aas_id, cfg),
        ],
        "conceptDescriptions": build_concept_descriptions(),
    }


# ===========================================================================
# 5. Main Entry
# ===========================================================================
def main(cfg_file: str, out_file: str):
    cfg = yaml.safe_load(Path(cfg_file).read_text(encoding="utf-8"))
    aas_json = build_aas(cfg)
    Path(out_file).write_text(json.dumps(aas_json, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"✅ AAS JSON generated → {out_file}")


if __name__ == "__main__":
    import sys
    config = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
    output = sys.argv[2] if len(sys.argv) > 2 else "/tmp/aas.json"
    main(config, output)
