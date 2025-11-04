import base64

def b64url_encode(s: str) -> str:
    # Base64 URL-safe + 去掉结尾的 '='，符合 AAS / BaSyx REST API 的用法
    return base64.urlsafe_b64encode(s.encode("utf-8")).decode("utf-8").rstrip("=")

print(b64url_encode("https://CaoYang/AASbyLLM/tree/main/AAS_Samples/ids/aas/I2C_Temperature_TMP117"))
