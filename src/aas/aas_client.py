import requests

class AASClient:
    """
    Stable AAS v2.x / BaSyx-compatible PUT client.
    """

    def __init__(self, aas_id, submodel_idshort, element_idshort, host):
        self.aas_id = aas_id
        self.submodel_idshort = submodel_idshort
        self.element_idshort = element_idshort
        self.host = host.rstrip("/")

        # ---- Step 1: Get full AAS shell info ----
        shell_url = f"{self.host}/shells/{aas_id}"
        print("[AAS] Fetching shell:", shell_url)

        resp = requests.get(shell_url)
        data = resp.json()

        # BaSyx v2.x 结构
        sm_refs = data["assetAdministrationShell"]["submodels"]

        # ---- Step 2: Find encoded Submodel ID ----
        self.submodel_encoded = None

        for sm in sm_refs:
            if sm["idShort"] == submodel_idshort:
                # submodel ID is inside keys[0].value
                self.submodel_encoded = sm["keys"][0]["value"]

        if not self.submodel_encoded:
            raise RuntimeError(f"Submodel '{submodel_idshort}' NOT found in AAS {aas_id}")

        print("[AAS] Found Submodel:", self.submodel_encoded)

        # ---- Step 3: Prepare PUT URL ----
        self.put_url = (
            f"{self.host}/submodels/"
            f"{self.submodel_encoded}/submodel-elements/"
            f"{element_idshort}/value"
        )

        print("[AAS] PUT URL =", self.put_url)

    # --------------------------------------------------
    # PUT update
    # --------------------------------------------------
    def put(self, value):
        payload = {"value": value}
        r = requests.put(self.put_url, json=payload)

        if r.status_code in (200, 204):
            print(f"[AAS PUT OK] {value}")
        else:
            print(f"[AAS PUT ERROR] {r.status_code}: {r.text}")
