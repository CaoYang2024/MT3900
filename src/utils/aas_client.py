# src/utils/aas_client.py
# -*- coding: utf-8 -*-

"""
AASClient: One class to:
- Base64 encode/decode AAS IDs (IRI <-> base64)
- GET shells
- GET submodels
- GET property value
- PUT property value (modify)
"""

import base64
import requests

class AASClient:
    def __init__(self, aas_env_url="http://localhost:8081"):
        """
        aas_env_url: AAS Environment endpoint (BaSyx)
        Example: "http://localhost:8081"
        """
        self.base = aas_env_url.rstrip("/")

    # ───────────────────────────────────────────────
    # Base64 URL-safe utilities (AAS REST API standard)
    # ───────────────────────────────────────────────

    @staticmethod
    def encode(iri: str) -> str:
        """IRI --> base64url (used in BaSyx REST path)"""
        return base64.urlsafe_b64encode(iri.encode("utf-8")).decode("utf-8").rstrip("=")

    @staticmethod
    def decode(b64url: str) -> str:
        """base64url --> IRI (auto padding fix)"""
        padded = b64url + "=" * (-len(b64url) % 4)
        return base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8")

    # ───────────────────────────────────────────────
    # AAS API Calls
    # ───────────────────────────────────────────────

    def list_shells(self):
        """Return list of all AAS shells"""
        r = requests.get(f"{self.base}/shells", timeout=3)
        r.raise_for_status()
        return r.json()

    def get_shell(self, aas_iri: str):
        """Get a shell JSON by its IRI"""
        enc = self.encode(aas_iri)
        r = requests.get(f"{self.base}/shells/{enc}", timeout=3)
        r.raise_for_status()
        return r.json()

    def get_submodel(self, submodel_iri: str):
        """Get submodel JSON by IRI"""
        enc = self.encode(submodel_iri)
        r = requests.get(f"{self.base}/submodels/{enc}", timeout=3)
        r.raise_for_status()
        return r.json(), enc

    # ───────────────────────────────────────────────
    # Property operations
    # ───────────────────────────────────────────────

    def get_property(self, submodel_iri: str, id_short_path: str):
        """
        Get property value from submodel, supports nested idShort, e.g.,:
        "EnablePublishing" or "Segments.InternalSegment.Records.Record"
        """
        sub, enc = self.get_submodel(submodel_iri)
        url = f"{self.base}/submodels/{enc}/submodel-elements/{id_short_path}/value"
        r = requests.get(url, timeout=3)
        r.raise_for_status()
        return r.json()

    def set_property(self, submodel_iri: str, id_short_path: str, value):
        """
        Set property value (supports bool/str/number)
        """
        sub, enc = self.get_submodel(submodel_iri)
        url = f"{self.base}/submodels/{enc}/submodel-elements/{id_short_path}/value"
        r = requests.put(url, json={"value": value}, timeout=3)
        r.raise_for_status()
        return True

    # ───────────────────────────────────────────────
    # High-level function: Auto chain resolution
    # ───────────────────────────────────────────────

    def auto_set(self, aas_iri: str, submodel_idShort: str, property_idShort: str, value):
        """
        One call to do:
           - GET shells
           - find target submodel by idShort
           - modify the target property
        Example:
            client.auto_set(aas_iri, "AssetInterface", "EnablePublishing", True)
        """
        shell = self.get_shell(aas_iri)

        # find submodel with idShort
        target_iri = None
        for sm_ref in shell["submodels"]:
            if sm_ref.get("keys", [{}])[0]["value"].endswith(submodel_idShort):
                target_iri = sm_ref["keys"][0]["value"]
                break

        if not target_iri:
            raise ValueError(f"Submodel '{submodel_idShort}' not found in shell")

        return self.set_property(target_iri, property_idShort, value)
