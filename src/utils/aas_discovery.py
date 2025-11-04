# src/utils/aas_discovery.py
# -*- coding: utf-8 -*-

"""
AAS Discovery Module
--------------------
Purpose:
  - Auto discover AAS → Submodels → Properties (recursive)
  - Generate correct URLs for UI (no /value)
  - Optional mapping for REST API (/value)

Usage example:
  props = discover_all_properties("http://192.168.0.180:8081")
"""

from src.utils.aas_client import AASClient


def _walk_elements(base_url: str, enc_submodel: str, elements: list, prefix=""):
    """Recursive parsing of SubmodelElement and SubmodelElementCollection"""
    urls = {}

    for elem in elements:
        model_type = elem.get("modelType")
        id_short = elem.get("idShort")

        if not id_short:
            continue

        full_path = f"{prefix}.{id_short}" if prefix else id_short

        # ✅ UI URL（no /value）
        if model_type == "Property":
            urls[full_path] = f"{base_url}/submodels/{enc_submodel}/submodel-elements/{full_path}"

        # ✅ Recursion for SMC container
        elif model_type == "SubmodelElementCollection":
            urls.update(_walk_elements(base_url, enc_submodel, elem.get("value", []), full_path))

    return urls


def discover_properties_for_shell(aas_server: str, aas_iri: str) -> dict:
    """
    Discover all properties for a single AAS shell
    return:
      {
         "TechnicalData": { "GeneralInformation.Name": URL, ... }
         "AssetInterface": { "EnablePublishing": URL, ... }
      }
    """
    client = AASClient(aas_server)
    shell = client.get_shell(aas_iri)

    results = {}

    for sm_ref in shell["submodels"]:
        submodel_iri = sm_ref["keys"][0]["value"]
        submodel_json, enc = client.get_submodel(submodel_iri)

        submodel_name = submodel_json["idShort"]
        elements = submodel_json.get("submodelElements", [])

        urls = _walk_elements(aas_server, enc, elements)
        results[submodel_name] = urls

    return results


def discover_all_properties(aas_server: str) -> dict:
    """
    Discover all AAS on server + recurse into submodels + list properties
    return:
      {
         "sensor_Ultrasonic_A01A": {
             "AssetInterface": {"EnablePublishing": "..."}
          },
         "sensor_USB_Camera": { ... }
      }
    """
    client = AASClient(aas_server)
    shells = client.list_shells()

    result = {}

    for shell in shells.get("result", []):
        aas_iri = shell["id"]
        aas_name = shell.get("idShort", "<unnamed>")

        result[aas_name] = discover_properties_for_shell(aas_server, aas_iri)

    return result
