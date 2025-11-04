#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate AAS JSON from config.yaml (AAS 3.0 compatible)
- Removes null / empty properties (AASX does not allow null)
- EnablePublishing stored as xs:boolean under Submodel: AssetInterface
- Verified by aas-test-engines and AASX Package Explorer
"""

from __future__ import annotations
import json
import uuid
from pathlib import Path
import yaml


# ======================================================================
# IEC 61360 Semantic Dictionary Entries
# Each key maps to a globally defined IEC 61360 semantic ID.
# ======================================================================
IEC = {
    "Name": "0173-1#02-AAW338#001",
    "ManufacturerName": "0173-1#02-AAO677#002",
    "SensorType": "0173-1#01-AAP906#001",
    "DataType": "0173-1#02-AAO295#002",
    "ValueRange": "0173-1#02-AAO663#002",
    "Voltage": "0173-1#02-AAM292#002",
    "Current": "0173-1#02-AAO108#003",
    "Reference": "0173-1#02-AAO198#004",

    # Boolean switch for EnablePublishing
    "Switch": "IEC61360:Switch"
}

# Required AAS IEC 61360 DataSpecification URI
DATASPEC_IEC61360 = "https://admin-shell.io/DataSpecificationTemplates/DataSpecificationIec61360/3"


# ======================================================================
# Helper functions
# ======================================================================
def semantic_ref(iri: str):
    """Return semanticId with proper AAS JSON structure."""
    return {
        "type": "ExternalReference",
        "keys": [{"type": "GlobalReference", "value": iri}]
    }


def prop_optional(idShort, value, semantic=None, valueType="xs:string"):
    """
    - Creates a Property only when value is not empty
    - Boolean must be encoded as "true"/"false" string for AAS Test Engine
    """
    if value is None:
        return None

    elem = {
        "modelType": "Property",
        "idShort": idShort,
        "valueType": valueType,
    }

    elem["value"] = (
        "true" if str(value).lower() == "true" else "false"
        if valueType == "xs:boolean"
        else str(value)
    )

    if semantic:
        elem["semanticId"] = semantic_ref(semantic)

    return elem


def prop_clean(arr: list):
    """Filter out None elements (AAS does not allow null entries)."""
    return [x for x in arr if x is not None]


# ======================================================================
# Submodels
# ======================================================================
def build_submodel_technical(aas_id: str, cfg: dict):
    """Generate TechnicalData submodel"""
    s = cfg["sensor"]
    sm_id = f"{aas_id}/submodel/TechnicalData"

    return {
        "idShort": "TechnicalData",
        "id": sm_id,
        "kind": "Instance",
        "modelType": "Submodel",
        "submodelElements": [
            {
                "modelType": "SubmodelElementCollection",
                "idShort": "GeneralInformation",
                "value": prop_clean([
                    prop_optional("Name", s["name"], IEC["Name"]),
                    prop_optional("Manufacturer", s["manufacturer"], IEC["ManufacturerName"]),
                    prop_optional("SensorType", s["type"], IEC["SensorType"]),
                ])
            },
            {
                "modelType": "SubmodelElementCollection",
                "idShort": "TechnicalProperties",
                "value": prop_clean([
                    prop_optional("DataType", s.get("datatype"), IEC["DataType"]),
                    prop_optional("ValueRange", s.get("range"), IEC["ValueRange"]),
                    prop_optional("OperatingVoltage", s.get("voltage"), IEC["Voltage"]),
                    prop_optional("OperatingCurrent", s.get("current"), IEC["Current"]),
                    prop_optional("Reference", s.get("reference"), IEC["Reference"]),
                ])
            }
        ]
    }


def build_submodel_interface(aas_id: str, cfg: dict):
    """Generate AssetInterface submodel (EnablePublishing stored here)"""
    itf = cfg["interface"]
    sm_id = f"{aas_id}/submodel/AssetInterface"

    return {
        "idShort": "AssetInterface",
        "id": sm_id,
        "kind": "Instance",
        "modelType": "Submodel",
        "submodelElements": prop_clean([
            prop_optional("Protocol", itf.get("protocol")),
            prop_optional("Endpoint", itf.get("endpoint")),
            prop_optional("SignalPath", itf.get("signal_path")),

            # ✅ enable_publishing comes from interface, not sensor
            prop_optional(
                "EnablePublishing",
                itf.get("enable_publishing"),
                IEC["Switch"],
                valueType="xs:boolean",
            ),
        ])
    }


# ======================================================================
# ConceptDescription list
# ======================================================================
def build_concept_descriptions():
    """Automatically build ConceptDescription entries"""
    cds = []
    for idShort, iri in IEC.items():
        cds.append({
            "idShort": idShort,
            "id": iri,
            "modelType": "ConceptDescription",
            "embeddedDataSpecifications": [{
                "dataSpecification": semantic_ref(DATASPEC_IEC61360),
                "dataSpecificationContent": {
                    "modelType": "DataSpecificationIec61360",
                    "preferredName": [{"language": "en", "text": idShort}],
                    "definition": [{"language": "en", "text": f"{idShort} defined by IEC 61360"}]
                }
            }]
        })
    return cds


# ======================================================================
# AAS Root
# ======================================================================
def build_aas(cfg: dict):
    """Combine AAS root + submodels + ConceptDescriptions"""
    aas_id = f"https://MT3900/YangCao/SDV/Sensor/ids/{uuid.uuid4()}"

    shell = {
        "modelType": "AssetAdministrationShell",
        "idShort": f"sensor_{cfg['sensor']['name']}",
        "id": aas_id,
        "assetInformation": {
            "assetKind": "Instance",
            "globalAssetId": aas_id
        },
        "submodels": [
            {"type": "ModelReference", "keys": [{"type": "Submodel", "value": f"{aas_id}/submodel/TechnicalData"}]},
            {"type": "ModelReference", "keys": [{"type": "Submodel", "value": f"{aas_id}/submodel/AssetInterface"}]},
        ]
    }

    return {
        "assetAdministrationShells": [shell],
        "submodels": [
            build_submodel_technical(aas_id, cfg),
            build_submodel_interface(aas_id, cfg)
        ],
        "conceptDescriptions": build_concept_descriptions()
    }


# ======================================================================
# CLI Entry
# ======================================================================
def main(cfg_file: str, out_file: str):
    cfg = yaml.safe_load(Path(cfg_file).read_text(encoding="utf-8"))
    aas_json = build_aas(cfg)
    Path(out_file).write_text(json.dumps(aas_json, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"✅ AAS JSON generated → {out_file}")


if __name__ == "__main__":
    import sys
    cfg = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
    out = sys.argv[2] if len(sys.argv) > 2 else "sensor_aas.json"
    main(cfg, out)
