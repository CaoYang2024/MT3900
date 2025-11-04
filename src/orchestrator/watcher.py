# orchestrator/driver_loader.py

import importlib
from utils.aas_client import AASClient

client = AASClient()

def load_driver_from_aas(aas_iri: str):
    """从 AAS 解析 driver module 并动态 import"""

    # 读取 Submodel → Driver name / VSS Path / EnablePublishing property
    shell = client.get_shell(aas_iri)

    # 只找 Submodel idShort = AssetInterface
    for ref in shell["submodels"]:
        iri = ref["keys"][0]["value"]
        submodel, _ = client.get_submodel(iri)

        driver_module = submodel["submodelElements"]["Driver"]["value"]
        vss_path      = submodel["submodelElements"]["VSSPath"]["value"]
        enable_key    = "EnablePublishing"

        module = importlib.import_module(f"drivers.{driver_module}")
        DriverClass = getattr(module, "Driver")

        return DriverClass(vss_path, aas_iri, enable_key)
