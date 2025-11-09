#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate AAS v3.0 JSON from config.yaml

Features:
- Removes empty/null fields (AAS3.0 requirement)
- Builds TechnicalData submodel (IDTA Technical Data compatible)
- Builds AssetInterfaceDescription submodel (IDTA 02017-1-0 strictly compliant)
- Generates valid AAS v3.0 JSON (can be opened in AASX Package Explorer)
"""

from __future__ import annotations
import json
import uuid
from pathlib import Path
import yaml


# ======================================================================
# IEC 61360 Semantic Dictionary Entries
# ======================================================================
# Used to assign global semantic identifiers to properties
IEC = {
    "Name": "0173-1#02-AAW338#001",
    "ManufacturerName": "0173-1#02-AAO677#002",
    "SensorType": "0173-1#01-AAP906#001",
    "DataType": "0173-1#02-AAO295#002",
    "ValueRange": "0173-1#02-AAO663#002",
    "Voltage": "0173-1#02-AAM292#002",
    "Current": "0173-1#02-AAO108#003",
    "Reference": "0173-1#02-AAO198#004",
    # Used for AssetInterfaceDescription → EnablePublishing
    "Switch": "IEC61360:Switch",
}

DATASPEC_IEC61360 = "https://admin-shell.io/DataSpecificationTemplates/DataSpecificationIec61360/3"


# ======================================================================
# Helper Functions
# ======================================================================
def semantic_ref(iri: str):
    """Return external semantic reference structure"""
    return {
        "type": "ExternalReference",
        "keys": [{"type": "GlobalReference", "value": iri}]
    }


def prop_optional(idShort, value, semantic=None, valueType="xs:string"):
    """Return property only if value exists (AAS cannot contain null entries)."""
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
    """Filter None entries from list (AAS spec forbids null SubmodelElements)."""
    return [x for x in arr if x is not None]


# ======================================================================
# Submodel: TechnicalData
# ======================================================================
def build_submodel_technical(aas_id: str, cfg: dict):
    """Build TechnicalData submodel (GeneralInformation + TechnicalProperties)"""
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


# ======================================================================
# Submodel: Asset Interface Description (IDTA 02017-1-0)
# ======================================================================
def build_submodel_interface(aas_id: str, cfg: dict):
    """Build Asset Interface Description submodel (HTTP endpoint metadata + publish switch)"""
    itf = cfg["interface"]
    sm_id = f"{aas_id}/submodel/AssetInterface"

    return {
        "modelType": "Submodel",
        "id": sm_id,
        "idShort": "AssetInterface",
        "kind": "Instance",

        # Required semanticId from IDTA template
        "semanticId": semantic_ref(
            "https://admin-shell.io/idta/AssetInterfacesDescription/1/0/Submodel"
        ),

        "submodelElements": [
            {
                "modelType": "SubmodelElementCollection",
                "idShort": "InterfaceTemplateForHTTP",

                "semanticId": semantic_ref(
                    "https://admin-shell.io/idta/AssetInterfacesDescription/1/0/Interface"
                ),

                "value": [
                    # ---- Endpoint Metadata ----
                    {
                        "modelType": "SubmodelElementCollection",
                        "idShort": "EndpointMetadata",
                        "semanticId": semantic_ref(
                            "https://admin-shell.io/idta/AssetInterfacesDescription/1/0/EndpointMetadata"
                        ),
                        "value": [
                            {
                                "modelType": "Property",
                                "idShort": "base",
                                "valueType": "xs:anyURI",
                                "value": str(itf.get("endpoint", "")),
                            },
                            {
                                "modelType": "Property",
                                "idShort": "contentType",
                                "valueType": "xs:string",
                                "value": "application/json",
                            },
                        ]
                    },

                    # ---- EnablePublishing boolean ----
                    {
                        "modelType": "Property",
                        "idShort": "EnablePublishing",
                        "valueType": "xs:boolean",
                        "value": "true" if itf.get("enable_publishing") else "false",
                        "semanticId": semantic_ref(IEC["Switch"]),
                    }
                ]
            }
        ]
    }


# ======================================================================
# ConceptDescriptions (semantic dictionary binding)
# ======================================================================
def build_concept_descriptions():
    """Generate all ConceptDescription entries matching IEC61360 dictionary"""
    return [
        {
            "idShort": idShort,
            "id": iri,
            "modelType": "ConceptDescription",
            "embeddedDataSpecifications": [{
                "dataSpecification": semantic_ref(DATASPEC_IEC61360),
                "dataSpecificationContent": {
                    "modelType": "DataSpecificationIec61360",
                    "preferredName": [{"language": "en", "text": idShort}],
                    "definition": [{"language": "en", "text": f"{idShort} defined by IEC 61360"}],
                }
            }]
        }
        for idShort, iri in IEC.items()
    ]


# ======================================================================
# Build Complete AAS v3.0 JSON Environment
# ======================================================================
def build_aas(cfg: dict):
    aas_id = f"https://MT3900/Sensor/ids/{uuid.uuid4()}"

    # Asset Administration Shell
    shell = {
        "modelType": "AssetAdministrationShell",
        "idShort": f"AAS_{cfg['sensor']['name']}",
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

    # Top-level must NOT contain `"modelType"` (AASX Package Explorer requirement)
    return {
        "assetAdministrationShells": [shell],
        "submodels": [
            build_submodel_technical(aas_id, cfg),
            build_submodel_interface(aas_id, cfg)
        ],
        "conceptDescriptions": build_concept_descriptions()
    }


# ======================================================================
# CLI Entry Point
# ======================================================================
def main(cfg_file: str, out_file: str):
    cfg = yaml.safe_load(Path(cfg_file).read_text(encoding="utf-8"))
    env = build_aas(cfg)
    Path(out_file).write_text(json.dumps(env, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"✅ AAS v3.0 JSON generated → {out_file}")


if __name__ == "__main__":
    import sys
    cfg = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
    out = sys.argv[2] if len(sys.argv) > 2 else "sensor.json"
    main(cfg, out)
