from __future__ import annotations
import json, sys, uuid
from pathlib import Path
from typing import Any, Dict
import yaml
from datetime import datetime

# Minimal AAS v3-like JSON builder (BaSyx JSON style)
# Two submodels: GeneralInformation & AssetInterface

# Semantic IDs (drawn from IEC 61360 & WoT TD IRIs)
CD = {
  "ManufacturerName": "0173-1#02-AAO677#002",
  "ProductDesignation": "0173-1#02-AAW338#001",
  "Address": "0173-1#02-AAQ832#005",
  "Department": "0173-1#02-AAO127#003",
  "Street": "0173-1#02-AAO128#002",
  "ZipCode": "0173-1#02-AAO129#002",
  "City": "0173-1#02-AAO132#002",
  "State": "0173-1#02-AAO133#002",
  # WoT / hypermedia terms
  "baseURI": "https://www.w3.org/2019/wot/td#baseURI",
  "forms": "https://www.w3.org/2019/wot/td#hasForm",
  "href": "https://www.w3.org/2019/wot/hypermedia#hasTarget",
  "methodName": "https://www.w3.org/2011/http#methodName",
  "contentType": "https://www.w3.org/2019/wot/hypermedia#forContentType",
  "security": "https://www.w3.org/2019/wot/td#hasSecurityConfiguration",
  "nosec_sc": "https://www.w3.org/2019/wot/security#NoSecurityScheme",
}

def external_ref(iri: str) -> Dict[str, Any]:
    return {"type": "ExternalReference", "keys": [{"type": "GlobalReference", "value": iri}]}

def property_element(id_short: str, value: Any, value_type: str, semantic_iri: str | None = None):
    elem = {
        "modelType": "Property",
        "idShort": id_short,
        "valueType": value_type,
        "value": str(value) if value is not None else ""
    }
    if semantic_iri:
        elem["semanticId"] = external_ref(semantic_iri)
    return elem

def collection(id_short: str, elements: list[dict], semantic_iri: str | None = None):
    col = {
        "modelType": "SubmodelElementCollection",
        "idShort": id_short,
        "value": elements
    }
    if semantic_iri:
        col["semanticId"] = external_ref(semantic_iri)
    return col

def list_of(id_short: str, type_value_list_element: str, items: list[dict], semantic_iri: str | None = None, semantic_iri_list_element: str | None = None):
    lst = {
        "modelType": "SubmodelElementList",
        "idShort": id_short,
        "orderRelevant": True,
        "typeValueListElement": type_value_list_element,
        "value": items
    }
    if semantic_iri:
        lst["semanticId"] = external_ref(semantic_iri)
    if semantic_iri_list_element:
        lst["semanticIdListElement"] = external_ref(semantic_iri_list_element)
    return lst

def build_general_information_sm(aas_id: str, cfg: dict) -> dict:
    sm_id = f"urn:submodel:general:{aas_id}"
    gi = cfg.get("general", {})
    address = gi.get("address", {})

    elements = [
        property_element("ManufacturerName", gi.get("manufacturerName",""), "xs:string", CD["ManufacturerName"]),
        property_element("ProductDesignation", gi.get("productDesignation",""), "xs:string", CD["ProductDesignation"]),
        collection("Address", [
            property_element("Street", address.get("street",""), "xs:string", CD["Street"]),
            property_element("ZipCode", address.get("zipCode",""), "xs:string", CD["ZipCode"]),
            property_element("City", address.get("city",""), "xs:string", CD["City"]),
            property_element("State", address.get("state",""), "xs:string", CD["State"]),
            property_element("Country", address.get("country",""), "xs:string"),
        ], CD["Address"])
    ]

    return {
        "idShort": "GeneralInformation",
        "id": sm_id,
        "kind": "Instance",
        "submodelElements": elements,
        "modelType": "Submodel"
    }

def build_asset_interface_sm(aas_id: str, cfg: dict) -> dict:
    sm_id = f"urn:submodel:asset-interface:{aas_id}"
    itf = cfg.get("interface", {})
    base_uri = itf.get("base", "")
    security = itf.get("security", "nosec_sc")
    forms = itf.get("forms", [])

    # Build forms as a SubmodelElementList of SubmodelElementCollection
    form_items = []
    for i, form in enumerate(forms, start=1):
        form_items.append(collection(f"Form{i}", [
            property_element("href", form.get("href",""), "xs:string", CD["href"]),
            property_element("methodName", form.get("method","GET"), "xs:string", CD["methodName"]),
            property_element("contentType", form.get("contentType","application/json"), "xs:string", CD["contentType"]),
        ]))

    sm_elements = [
        property_element("base", base_uri, "xs:string", CD["baseURI"]),
        property_element("security", security, "xs:string", CD["security"]),
        list_of("forms", "SubmodelElementCollection", form_items, CD["forms"])
    ]

    return {
        "idShort": "AssetInterface",
        "id": sm_id,
        "kind": "Instance",
        "semanticId": { "type": "ModelReference", "keys": [ { "type": "Submodel", "value": "https://admin-shell.io/idta/AssetInterfacesDescription/1/0/Submodel" } ] },
        "submodelElements": sm_elements,
        "modelType": "Submodel"
    }

def build_aas(cfg: dict) -> dict:
    a = cfg["asset"]
    aas_id = a["id"]
    aas = {
        "idShort": a["idShort"],
        "id": aas_id,
        "assetInformation": {
            "assetKind": a.get("assetKind", "Instance"),
            "globalAssetId": a.get("globalAssetId", aas_id),
        },
        "submodels": [
            { "type": "ModelReference", "keys": [ {"type": "Submodel", "value": f"urn:submodel:general:{aas_id}"} ] },
            { "type": "ModelReference", "keys": [ {"type": "Submodel", "value": f"urn:submodel:asset-interface:{aas_id}"} ] },
        ],
        "modelType": "AssetAdministrationShell"
    }
    if a.get("thumbnail"):
        aas["assetInformation"]["defaultThumbnail"] = {
            "path": a["thumbnail"],
            "contentType": "image/jpeg"
        }

    return {
        "assetAdministrationShells": [aas],
        "submodels": [
            build_general_information_sm(aas_id, cfg),
            build_asset_interface_sm(aas_id, cfg)
        ],
        "conceptDescriptions": [
            # Minimal set (you can extend as needed)
            {
              "idShort":"Manufacturer name",
              "id": CD["ManufacturerName"],
              "embeddedDataSpecifications":[{
                "dataSpecification": external_ref("http://admin-shell.io/DataSpecificationTemplates/DataSpecificationIEC61360/3/0"),
                "dataSpecificationContent": {"preferredName":[{"language":"en","text":"Manufacturer name"}], "modelType":"DataSpecificationIec61360"}
              }],
              "modelType":"ConceptDescription"
            },
            {
              "idShort":"Manufacturer product designation",
              "id": CD["ProductDesignation"],
              "embeddedDataSpecifications":[{
                "dataSpecification": external_ref("http://admin-shell.io/DataSpecificationTemplates/DataSpecificationIEC61360/3/0"),
                "dataSpecificationContent": {"preferredName":[{"language":"en","text":"Manufacturer product designation"}], "modelType":"DataSpecificationIec61360"}
              }],
              "modelType":"ConceptDescription"
            },
            {
              "idShort":"Address",
              "id": CD["Address"],
              "embeddedDataSpecifications":[{
                "dataSpecification": external_ref("http://admin-shell.io/DataSpecificationTemplates/DataSpecificationIEC61360/3/0"),
                "dataSpecificationContent": {"preferredName":[{"language":"en","text":"Address"}], "modelType":"DataSpecificationIec61360"}
              }],
              "modelType":"ConceptDescription"
            },
            # WoT TD
            {
              "idShort":"base",
              "id": CD["baseURI"],
              "embeddedDataSpecifications":[{
                "dataSpecification": external_ref("http://admin-shell.io/DataSpecificationTemplates/DataSpecificationIEC61360/3/0"),
                "dataSpecificationContent": {"preferredName":[{"language":"en","text":"base"}], "modelType":"DataSpecificationIec61360"}
              }],
              "modelType":"ConceptDescription"
            },
            {
              "idShort":"forms",
              "id": CD["forms"],
              "embeddedDataSpecifications":[{
                "dataSpecification": external_ref("http://admin-shell.io/DataSpecificationTemplates/DataSpecificationIEC61360/3/0"),
                "dataSpecificationContent": {"preferredName":[{"language":"en","text":"forms"}], "modelType":"DataSpecificationIec61360"}
              }],
              "modelType":"ConceptDescription"
            },
            {
              "idShort":"href",
              "id": CD["href"],
              "embeddedDataSpecifications":[{
                "dataSpecification": external_ref("http://admin-shell.io/DataSpecificationTemplates/DataSpecificationIEC61360/3/0"),
                "dataSpecificationContent": {"preferredName":[{"language":"en","text":"href"}], "modelType":"DataSpecificationIec61360"}
              }],
              "modelType":"ConceptDescription"
            },
            {
              "idShort":"htv_methodName",
              "id": CD["methodName"],
              "embeddedDataSpecifications":[{
                "dataSpecification": external_ref("http://admin-shell.io/DataSpecificationTemplates/DataSpecificationIEC61360/3/0"),
                "dataSpecificationContent": {"preferredName":[{"language":"en","text":"htv_methodName"}], "modelType":"DataSpecificationIec61360"}
              }],
              "modelType":"ConceptDescription"
            },
            {
              "idShort":"contentType",
              "id": CD["contentType"],
              "embeddedDataSpecifications":[{
                "dataSpecification": external_ref("http://admin-shell.io/DataSpecificationTemplates/DataSpecificationIEC61360/3/0"),
                "dataSpecificationContent": {"preferredName":[{"language":"en","text":"contentType"}], "modelType":"DataSpecificationIec61360"}
              }],
              "modelType":"ConceptDescription"
            },
            {
              "idShort":"security",
              "id": CD["security"],
              "embeddedDataSpecifications":[{
                "dataSpecification": external_ref("http://admin-shell.io/DataSpecificationTemplates/DataSpecificationIEC61360/3/0"),
                "dataSpecificationContent": {"preferredName":[{"language":"en","text":"security"}], "modelType":"DataSpecificationIec61360"}
              }],
              "modelType":"ConceptDescription"
            },
            {
              "idShort":"nosec_sc",
              "id": CD["nosec_sc"],
              "embeddedDataSpecifications":[{
                "dataSpecification": external_ref("http://admin-shell.io/DataSpecificationTemplates/DataSpecificationIEC61360/3/0"),
                "dataSpecificationContent": {"preferredName":[{"language":"en","text":"nosec_sc"}], "modelType":"DataSpecificationIec61360"}
              }],
              "modelType":"ConceptDescription"
            },
          ]
    }

def main(cfg_path: str, out_path: str):
    cfg = yaml.safe_load(Path(cfg_path).read_text(encoding="utf-8"))
    doc = build_aas(cfg)
    Path(out_path).write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    print("Generated:", out_path)

if __name__ == "__main__":
    cfg_path = sys.argv[1] if len(sys.argv) > 1 else "config_example.yaml"
    out_path = sys.argv[2] if len(sys.argv) > 2 else "aas_generated.json"
    main(cfg_path, out_path)
