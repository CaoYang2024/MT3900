import re
import time
import requests
from random import randint
from datetime import datetime, timezone

URL = ("http://localhost:8081/submodels/"
       "aHR0cHM6Ly9hZG1pbi1zaGVsbC5pby9pZHRhL1N1Ym1vZGVsVGVtcGxhdGUvVGltZVNlcmllcy8xLzE"
       "/submodel-elements/Segments.InternalSegment.Records.Record")
HEADERS = {"Content-Type": "application/json"}

# 频率 & 数值
HZ = 1.0
BASE = 150
JITTER = 10
MAX_POINTS = 300  # 可选：最多保留多少个编号（成对计数），None 表示不限制

# 语义 URI（与你模板一致）
SEM_RECORD = "https://admin-shell.io/idta/TimeSeries/Record/1/1"
SEM_TIME   = "https://admin-shell.io/idta/TimeSeries/RelativePointInTime/1/1"
SEM_AX     = "https://sample.com/AccelerationX/1/1"

def epoch_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)

def get_record():
    r = requests.get(URL, timeout=8)
    r.raise_for_status()
    return r.json()

def save_record(rec):
    r = requests.put(URL, json=rec, headers=HEADERS, timeout=10)
    if not r.ok:
        raise RuntimeError(f"PUT failed: HTTP {r.status_code} {r.text}")

def ensure_envelope(rec):
    rec.setdefault("modelType", "SubmodelElementCollection")
    rec.setdefault("idShort",  rec.get("idShort", "Record"))
    rec.setdefault("semanticId", {
        "type": "ExternalReference",
        "keys": [{"type":"GlobalReference","value": SEM_RECORD}]
    })
    rec.setdefault("value", [])
    return rec

def cleanup_unindexed(value):
    """删除未带编号的 'Time' / 'sampleAccelerationX'，避免干扰绘图解析。"""
    return [el for el in value if el.get("idShort") not in ("Time", "sampleAccelerationX")]

def next_index(value):
    pat = re.compile(r"^(Time|sampleAccelerationX)(\d{2,3})$")
    nmax = 0
    for el in value:
        m = pat.match(el.get("idShort",""))
        if m: nmax = max(nmax, int(m.group(2)))
    nxt = nmax + 1
    return f"{nxt:02d}" if nxt < 100 else f"{nxt:03d}"

def make_time(id_short, val_ms):
    return {
        "modelType":"Property","idShort":id_short,
        "semanticId":{"type":"ExternalReference","keys":[{"type":"GlobalReference","value":SEM_TIME}]},
        "valueType":"xs:long","value":str(val_ms),"category":"VARIABLE"
    }

def make_x(id_short, val):
    return {
        "modelType":"Property","idShort":id_short,
        "semanticId":{"type":"ExternalReference","keys":[{"type":"GlobalReference","value":SEM_AX}]},
        "valueType":"xs:long","value":str(val),"category":"VARIABLE"
    }

def truncate_pairs(value):
    if not MAX_POINTS:
        return value
    # 计算已有编号集合
    pat = re.compile(r"^(?:Time|sampleAccelerationX)(\d{2,3})$")
    idxs = sorted({int(pat.match(el["idShort"]).group(1))
                   for el in value if pat.match(el.get("idShort",""))})
    if len(idxs) <= MAX_POINTS:
        return value
    drop = set(idxs[:-MAX_POINTS])
    newv = []
    for el in value:
        m = pat.match(el.get("idShort",""))
        if m and int(m.group(1)) in drop:
            continue
        newv.append(el)
    return newv

def append_once():
    rec = ensure_envelope(get_record())
    val = rec["value"]

    # 第一次运行先清理未带编号的字段
    new_val = cleanup_unindexed(val)
    if len(new_val) != len(val):
        rec["value"] = new_val
        save_record(rec)
        val = new_val

    idx = next_index(val)
    t = epoch_ms()
    x = BASE + randint(-JITTER, JITTER)

    val.append(make_time(f"Time{idx}", t))
    val.append(make_x(f"sampleAccelerationX{idx}", x))

    rec["value"] = truncate_pairs(val)
    save_record(rec)
    return idx, t, x

def main():
    print("[START] Clean+Append mode: 删除未带编号字段 -> 追加 TimeNN/XNN -> PUT 回父 URL")
    dt = 1.0 / HZ if HZ > 0 else 1.0
    try:
        while True:
            idx, t, x = append_once()
            print(f"{datetime.now().strftime('%H:%M:%S')}  Time{idx}={t}   X{idx}={x}")
            time.sleep(dt)
    except KeyboardInterrupt:
        print("\nStopped.")

if __name__ == "__main__":
    main()
