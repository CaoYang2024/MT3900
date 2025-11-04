# drivers/base.py

from utils.aas_client import AASClient

class DriverBase:
    def __init__(self, vss_path, aas_iri, enable_key):
        self.vss_path = vss_path
        self.aas_iri = aas_iri
        self.enable_key = enable_key
        self.running = True
        self.aas = AASClient()

    def should_publish(self):
        return self.aas.get_property_from_shell(
            self.aas_iri,
            "AssetInterface",
            self.enable_key
        )

    def stop(self):
        self.running = False
