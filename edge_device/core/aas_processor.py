#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
AAS Processor — Fully Compatible with the New AAS Template (ConceptDescription-based)
------------------------------------------------------------------------------------

This processor extracts:
  ✓ DriverImage
  ✓ DriverVersion
  ✓ DriverCommand (JSON decoded)
  ✓ Port
  ✓ VSSPath
  ✓ FrameURL / StreamURL (camera only)
  ✓ SensorType
  ✓ HardwareSignature (if needed)
  
Designed for your AAS structure:

  TechnicalData
  AssetInterface
  EdgeDriver
  Application

All properties use:
  semanticId.keys[0].type == "ConceptDescription"
  semanticId.keys[0].value == "urn:my-company:cd:<PropertyName>"

This module replaces the old ContainerImageURL logic.
"""

import copy
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger("AAS")

# ---------------------------------------------------------------------------
# ConceptDescription URNs used in your AAS template
# ---------------------------------------------------------------------------
CD = {
    "DriverImage": "urn:my-company:cd:DriverImage",
    "DriverVersion": "urn:my-company:cd:DriverVersion",
    "DriverCommand": "urn:my-company:cd:DriverCommand",

    "Port": "urn:my-company:cd:Port",
    "VSSPath": "urn:my-company:cd:VSSPath",
    "FrameURL": "urn:my-company:cd:FrameURL",
    "StreamURL": "urn:my-company:cd:StreamURL",
    "Value": "urn:my-company:cd:Value",

    "SensorType": "urn:my-company:cd:SensorType",
    "HardwareSignature": "urn:my-company:cd:HardwareSignature",
}


# ---------------------------------------------------------------------------
# Main Processor
# ---------------------------------------------------------------------------
class AASProcessor:
    """Extracts driver info, interface info, and runtime injection."""

    def __init__(self):
        logger.info("AASProcessor initialized (ConceptDescription mode enabled)")

    # -----------------------------------------------------------------------
    # Top-level public function: extract driver + integration info
    # -----------------------------------------------------------------------
    def extract_driver_info(self, aas_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract driver definition from the NEW EdgeDriver submodel.
        Supports:
        - DriverImage
        - DriverCommand (JSON)
        """

        logger.info("Extracting driver information from AAS...")

        result = {
            "driver_image": None,
            "driver_command": None,
            "sensor_type": None,
            "port": None,
        }

        submodels = aas_data.get("submodels", [])

        for sm in submodels:
            sm_id = sm.get("idShort")

            # ------------------------------------------------------------
            # 1) EdgeDriver Submodel
            # ------------------------------------------------------------
            if sm_id == "EdgeDriver":
                for elem in sm.get("submodelElements", []):
                    idshort = elem.get("idShort")

                    # DriverImage
                    if idshort == "DriverImage":
                        result["driver_image"] = elem.get("value")
                        logger.info(f"✓ DriverImage: {result['driver_image']}")

                    # DriverCommand (JSON)
                    elif idshort == "DriverCommand":
                        import json
                        try:
                            cmd = json.loads(elem.get("value"))
                            result["driver_command"] = cmd
                            logger.info(f"✓ DriverCommand: {cmd}")
                        except Exception:
                            logger.error("DriverCommand is not valid JSON!")

            # ------------------------------------------------------------
            # 2) AssetInterface — find Port
            # ------------------------------------------------------------
            elif sm_id == "AssetInterface":
                for elem in sm.get("submodelElements", []):
                    if elem.get("idShort") == "Port":
                        result["port"] = elem.get("value")
                        logger.info(f"✓ Port: {result['port']}")

            # ------------------------------------------------------------
            # 3) TechnicalData — find SensorType
            # ------------------------------------------------------------
            elif sm_id == "TechnicalData":
                for elem in sm.get("submodelElements", []):
                    for child in elem.get("value", []):
                        if child.get("idShort") == "SensorType":
                            result["sensor_type"] = child.get("value")
                            logger.info(f"✓ SensorType: {result['sensor_type']}")

        # ------------------------------------------------------------
        # FINAL VALIDATION
        # ------------------------------------------------------------

        if not result["driver_image"]:
            logger.error("❌ EdgeDriver.DriverImage not found!")
            return None

        if not result["driver_command"]:
            logger.error("❌ EdgeDriver.DriverCommand not found!")
            return None

        return result


    # -----------------------------------------------------------------------
    # Extract one property by semanticId
    # -----------------------------------------------------------------------
    def _extract_property(self, elem: Dict[str, Any], result: Dict[str, Any]):
        """Checks semanticId and updates result dict."""

        model_type = elem.get("modelType")
        id_short = elem.get("idShort")
        value = elem.get("value")

        # If it's a collection, recursively parse children
        if model_type == "SubmodelElementCollection":
            for child in elem.get("value", []):
                self._extract_property(child, result)
            return

        # If not Property, ignore
        if model_type != "Property":
            return

        # semanticId must exist
        semantic = elem.get("semanticId", {})
        keys = semantic.get("keys", [])
        if not keys:
            return

        key0 = keys[0]
        if key0.get("type") != "ConceptDescription":
            return  # not your field

        cd_value = key0.get("value")

        # ----------------- DriverImage -----------------
        if cd_value == CD["DriverImage"]:
            result["driver_image"] = value

        elif cd_value == CD["DriverVersion"]:
            result["driver_version"] = value

        elif cd_value == CD["DriverCommand"]:
            try:
                result["driver_command"] = json.loads(value)
            except Exception:
                logger.error(f"❌ DriverCommand JSON parse failed: {value}")

        # ----------------- AssetInterface -----------------
        elif cd_value == CD["Port"]:
            result["device_path"] = value

        elif cd_value == CD["VSSPath"]:
            result["vss_path"] = value

        elif cd_value == CD["FrameURL"]:
            result["frame_url"] = value

        elif cd_value == CD["StreamURL"]:
            result["stream_url"] = value

        elif cd_value == CD["Value"]:
            result["value"] = value

        # ----------------- TechnicalData -----------------
        elif cd_value == CD["SensorType"]:
            result["sensor_type"] = value

        # ignore other CD definitions

    # -----------------------------------------------------------------------
    # Create runtime instance (same as your previous logic)
    # -----------------------------------------------------------------------
    def create_instance(self, aas, signature, edge_id, local_ip):
        """Inject runtime fields into AAS instance."""
        instance = copy.deepcopy(aas)

        instance["id"] = f"{aas['id']}:instance:{edge_id}"

        asset_info = instance.get("assetInformation", {})
        asset_info["assetKind"] = "Instance"
        asset_info["globalAssetId"] = f"{asset_info.get('globalAssetId')}:{signature}"

        instance["assetInformation"] = asset_info

        # runtime injection
        runtime_values = {
            "HardwareSignature": signature,
            "CurrentIP": local_ip,
            "EdgeDeviceId": edge_id,
            "Status": "ONLINE",
            "LastHeartbeat": datetime.utcnow().isoformat() + "Z",
        }

        for sm in instance.get("submodels", []):
            self._inject_runtime(sm, runtime_values)

        return instance

    def _inject_runtime(self, elem, values):
        """Recursively update runtime placeholders."""
        if elem.get("modelType") == "Property":
            id_short = elem.get("idShort")
            if id_short in values:
                v = elem.get("value", "")
                if "TO_BE_FILLED" in str(v) or not v:
                    elem["value"] = values[id_short]

        # recurse children
        for child in elem.get("submodelElements", []):
            self._inject_runtime(child, values)
        for child in elem.get("value", []):
            if isinstance(child, dict):
                self._inject_runtime(child, values)
