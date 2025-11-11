#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate AAS v3.0 JSON for USB Camera
- TechnicalData (static)
- AssetInterface (runtime: StreamURL / Connected)
"""

from __future__ import annotations
import json
from pathlib import Path
import yaml

IEC = {
    "Name": "0173-1#02-AAW338#001",
    "ManufacturerName": "0173-1#02-AAO677#002",
    "SensorType": "0173-1#01-AAP906#001",
}

def semantic_ref(iri: str):
    return {"type": "ExternalReference", "keys": [{"type": "GlobalReference", "value": iri}]}

def prop_optional(idShort, value, semantic=None, valueType="xs:string"):
    if value is None:
        return None
    return {
        "modelType": "Property",
        "idShort": idShort,
        "valueType": valueType,
        "value": str(value) if valueType != "xs:boolean" else ("true" if value else "false"),
        **({"semanticId": semantic_ref(semantic)} if semantic else {})
    }

def prop_clean(arr: list):
    return [x for x in arr if x is not None]

def build_submodel_technical(aas_id: str, cfg: dict):
    s = cfg["sensor"]
    sm_id = f"{aas_id}/submodel/TechnicalData"
    return {
        "modelType": "Submodel",
        "id": sm_id,
        "idShort": "TechnicalData",
        "kind": "Instance",
        "submodelElements": [
            {
                "modelType": "SubmodelElementCollection",
                "idShort": "GeneralInformation",
                "value": prop_clean([
                    prop_optional("Name", s["name"], IEC["Name"]),
                    prop_optional("Manufacturer", s["manufacturer"], IEC["ManufacturerName"]),
                    prop_optional("SensorType", s["type"], IEC["SensorType"]),
                ])
            }
        ]
    }

def build_submodel_interface(aas_id: str, cfg: dict):
    itf = cfg["interface"]
    ip = itf["ip"]
    port = itf["port"]
    stream_url = f"http://{ip}:{port}/stream"
    sm_id = f"{aas_id}/submodel/AssetInterface"
    return {
        "modelType": "Submodel",
        "id": sm_id,
        "idShort": "AssetInterface",
        "kind": "Instance",
        "submodelElements": [
            {
                "modelType": "Property",
                "idShort": "StreamURL",
                "valueType": "xs:anyURI",
                "value": stream_url,
            },
            {
                "modelType": "Property",
                "idShort": "Connected",
                "valueType": "xs:boolean",
                "value": "true" if itf["connected"] else "false"
            }
        ]
    }

def build_concept_descriptions():
    return [
        {
            "idShort": k,
            "id": v,
            "modelType": "ConceptDescription",
            "embeddedDataSpecifications": [{
                "dataSpecification": semantic_ref("https://admin-shell.io/DataSpecificationTemplates/DataSpecificationIec61360/3"),
                "dataSpecificationContent": {
                    "modelType": "DataSpecificationIec61360",
                    "preferredName": [{"language": "en", "text": k}],
                },
            }],
        }
        for k, v in IEC.items()
    ]

def build_aas(cfg: dict):
    aas_id = cfg["id"]  # 固定ID（来自 USB 唯一ID）
    shell = {
        "modelType": "AssetAdministrationShell",
        "idShort": f"AAS_{cfg['sensor']['name']}",
        "id": aas_id,
        "assetInformation": {"assetKind": "Instance", "globalAssetId": aas_id},
        "submodels": [
            {"type": "ModelReference", "keys": [{"type": "Submodel", "value": f"{aas_id}/submodel/TechnicalData"}]},
            {"type": "ModelReference", "keys": [{"type": "Submodel", "value": f"{aas_id}/submodel/AssetInterface"}]},
        ]
    }
    return {
        "assetAdministrationShells": [shell],
        "submodels": [
            build_submodel_technical(aas_id, cfg),
            build_submodel_interface(aas_id, cfg),
        ],
        "conceptDescriptions": build_concept_descriptions(),
    }

def main(cfg_file: str, out_file: str):
    cfg = yaml.safe_load(Path(cfg_file).read_text(encoding="utf-8"))
    aas_json = build_aas(cfg)
    Path(out_file).write_text(json.dumps(aas_json, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"✅ AAS generated → {out_file}")

if __name__ == "__main__":
    import sys
    cfg = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
    out = sys.argv[2] if len(sys.argv) > 2 else "/tmp/aas_sensor.json"
    main(cfg, out)
