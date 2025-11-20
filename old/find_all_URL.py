from src.utils.aas_discovery import discover_all_properties
import json

aas_server = "http://192.168.137.1:8081"   # BaSyx server

props = discover_all_properties(aas_server)

# ✅ 整洁美观的 JSON 输出（缩进 + 中文友好）
print(json.dumps(props, indent=2, ensure_ascii=False))
