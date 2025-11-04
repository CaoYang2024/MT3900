#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate AAS JSON from config.yaml for SDV Plug-and-Play sensor
Author: Yang Cao
"""

from __future__ import annotations
import json
import uuid
from pathlib import Path
import yaml

# ✅ IEC 61360 semantic IDs —— 已查证（Electropedia / IEC 61360 CDD）
IEC = {
    "Name": "0173-1#02-AAW338#001",
    "ManufacturerName": "0173-1#02-AAO677#002",
    "SensorType": "0173-1#01-AAP906#001",
    "DataType": "0173-1#02-AAO295#002",
    "ValueRange": "0173-1#02-AAO663#002",
    "Voltage": "0173-1#02-AAM292#002",
    "Current": "0173-1#02-AAO108#003",
    "Reference": "0173-1#02-AAO198#004",

    # ✅ boolean 开关（EnablePublishing）对应 IEC CDD 语义词条
    "Switch": "IEC61360:Switch"
}


# -----------------------------------------------------------------------------
# Utility helpers
# -----------------------------------------------------------------------------
def semantic_ref(iri: str):
    """Wrap semantic ID"""
    return {"type": "ExternalReference", "keys": [{"type": "GlobalReference", "value": iri}]}


def prop_optional(idShort, value, semantic=None, valueType="xs:string"):
    """跳过 null / unknown 字段"""
    if value is None:
        return None
    if isinstance(value, str) and value.strip().lower() in ["", "unknown", "none", "null"]:
        return None

    elem = {
        "modelType": "Property",
        "idShort": idShort,
        "valueType": valueType,
        "value": str(value),
    }
    if semantic:
        elem["semanticId"] = semantic_ref(semantic)
    return elem


def smc(idShort, elements):
    """SubmodelElementCollection，自动过滤 None"""
    filtered = [e for e in elements if e is not None]
    return {"modelType": "SubmodelElementCollection", "idShort": idShort, "value": filtered}


# -----------------------------------------------------------------------------
# ConceptDescriptions (semantic dictionary entries)
# -----------------------------------------------------------------------------
def build_concept_descriptions():
    cds = []
    for idShort, iri in IEC.items():
        cds.append({
            "idShort": idShort,
            "id": iri,
            "embeddedDataSpecifications": [{
                "dataSpecification": semantic_ref(
                    "http://admin-shell.io/DataSpecificationTemplates/DataSpecificationIEC61360/3/0"
                ),
                "dataSpecificationContent": {
                    "modelType": "DataSpecificationIec61360",
                    "preferredName": [{"language": "en", "text": idShort}],
                    "definition": [{"language": "en", "text": f"{idShort} defined by IEC 61360"}]
                }
            }],
            "modelType": "ConceptDescription"
        })
    return cds


# -----------------------------------------------------------------------------
# Build TechnicalData Submodel
# -----------------------------------------------------------------------------
def build_submodel_technical(aas_id: str, cfg: dict):
    sm_id = f"{aas_id}/submodel/TechnicalData"
    s = cfg["sensor"]

    # Required fields check
    required = ["name", "manufacturer", "type"]
    for f in required:
        if f not in s or not s[f]:
            raise ValueError(f"❌ ERROR: sensor.{f} is required in config.yaml")

    return {
        "idShort": "TechnicalData",
        "id": sm_id,
        "kind": "Instance",
        "submodelElements": [
            smc("GeneralInformation", [
                prop_optional("Name", s["name"], IEC["Name"]),
                prop_optional("Manufacturer", s["manufacturer"], IEC["ManufacturerName"]),
                prop_optional("SensorType", s["type"], IEC["SensorType"]),
            ]),
            smc("TechnicalProperties", [
                prop_optional("DataType", s.get("datatype"), IEC["DataType"]),
                prop_optional("ValueRange", s.get("range"), IEC["ValueRange"]),
                prop_optional("OperatingVoltage", s.get("voltage"), IEC["Voltage"]),
                prop_optional("OperatingCurrent", s.get("current"), IEC["Current"]),
                prop_optional("Reference", s.get("reference"), IEC["Reference"]),
            ])
        ],
        "modelType": "Submodel"
    }


# -----------------------------------------------------------------------------
# Build AssetInterface Submodel (driver + endpoint + enable publishing)
# -----------------------------------------------------------------------------
def build_submodel_interface(aas_id: str, cfg: dict):
    sm_id = f"{aas_id}/submodel/AssetInterface"

    s = cfg["sensor"]        # enable_publishing 从 sensor 解析
    itf = cfg["interface"]   # endpoint、protocol、signal_path 属于 interface

    return {
        "idShort": "AssetInterface",
        "id": sm_id,
        "kind": "Instance",
        "submodelElements": [
            prop_optional("Protocol", itf.get("protocol")),
            prop_optional("Endpoint", itf.get("endpoint")),
            prop_optional("SignalPath", itf.get("signal_path")),

            # ✅ 这里放开关属性 —— 运行时由 AASClient 控制 driver.publish()
            prop_optional("EnablePublishing",
                          s.get("enable_publishing"),
                          IEC["Switch"],
                          "xs:boolean"),
        ],
        "modelType": "Submodel"
    }


# -----------------------------------------------------------------------------
# Build AAS document
# -----------------------------------------------------------------------------
def build_aas(cfg: dict):
    aas_id = f"https://MT3900/YangCao/SDV/Sensor/ids/{uuid.uuid4()}"

    aas = {
        "idShort": f"sensor_{cfg['sensor']['name']}",
        "id": aas_id,
        "assetInformation": {
            "assetKind": "Instance",
            "globalAssetId": aas_id,
        },
    }

    sm_tech = build_submodel_technical(aas_id, cfg)
    sm_intf = build_submodel_interface(aas_id, cfg)

    return {
        "assetAdministrationShells": [{
            **aas,
            "submodels": [
                {"type": "ModelReference", "keys": [{"type": "Submodel", "value": sm_tech["id"]}]},
                {"type": "ModelReference", "keys": [{"type": "Submodel", "value": sm_intf["id"]}]},
            ]
        }],
        "submodels": [sm_tech, sm_intf],
        "conceptDescriptions": build_concept_descriptions(),
    }


# -----------------------------------------------------------------------------
# Main entry
# -----------------------------------------------------------------------------
def main(cfg_file: str, out_file: str):
    cfg = yaml.safe_load(Path(cfg_file).read_text(encoding="utf-8"))
    doc = build_aas(cfg)
    Path(out_file).write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"✅ Generated AAS JSON → {out_file}")


if __name__ == "__main__":
    import sys
    cfg = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
    out = sys.argv[2] if len(sys.argv) > 2 else "sensor_aas.json"
    main(cfg, out)
