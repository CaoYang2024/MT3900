#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
USB Plug-and-Play Orchestrator for AAS-based Sensor Deployment
--------------------------------------------------------------

功能：
✔ 监控 USB 设备插拔
✔ 获取 Fingerprint = VID:PID:Serial
✔ 查询 BaSyx 中是否存在对应 AAS
✔ 解析 AssetInterface Submodel 中的 File 元素
✔ 下载 DriverFile / KuksaFile / OrchestratorFile
✔ 按顺序执行：driver → kuksa → orchestrator
✔ 当 remove 时 kill 所有进程
✔ 再次 add 时自动重新启动

注意：
你需要运行 BaSyx AAS-Environment (port 8081)
"""

import os
import json
import base64
import subprocess
import requests
import pyudev
from pathlib import Path


# ============================================================
#   1. USB Fingerprint 工具
# ============================================================
def get_fingerprint(device):
    """从 pyudev 获取设备指纹"""
    def val(attr): 
        v = device.get(attr)
        return v if v else None

    fp = {
        "idVendor": val("ID_VENDOR_ID"),
        "idProduct": val("ID_MODEL_ID"),
        "serial": val("ID_SERIAL_SHORT")
    }
    return fp


def make_unique_key(fp):
    return f"{fp['idVendor']}:{fp['idProduct']}:{fp.get('serial', '')}"


# ============================================================
#   2. BaSyx AAS Client
# ============================================================
BASYX = "http://localhost:8081"   # 修改为你的 AAS 环境


def query_matching_aas(unique_key):
    """根据 fingerprint 去 BaSyx 查找 AAS"""
    url = f"{BASYX}/shells"
    resp = requests.get(url).json()

    for shell in resp.get("result", []):
        aas_id = shell["id"]
        if unique_key in aas_id:
            return aas_id

    return None


def load_submodel(aas_id, sm_name):
    """从 BaSyx 读取某个 Submodel"""
    enc = requests.utils.quote(aas_id, safe="")

    url = f"{BASYX}/shells/{enc}/submodels"
    subs = requests.get(url).json()

    for item in subs["result"]:
        if item["idShort"] == sm_name:
            sm_id = item["keys"][0]["value"]
            enc_sm = requests.utils.quote(sm_id, safe="")
            sm_url = f"{BASYX}/submodels/{enc_sm}/submodel"
            return requests.get(sm_url).json()

    return None


def download_file_element(file_elem, out_dir):
    """从 File 类型 submodel element 下载文件 (AAS 3.0)"""

    elem_id = file_elem["idShort"]
    content_url = file_elem["value"]
    content_type = file_elem["contentType"]

    # 文件名
    filename = content_url.split("/")[-1]
    local_path = Path(out_dir) / filename

    # 从 BaSyx 获取 Base64 内容
    resp = requests.get(f"{BASYX}/files/{filename}").json()
    raw = base64.b64decode(resp["content"])

    local_path.write_bytes(raw)
    os.chmod(local_path, 0o755)

    print(f"📥 下载: {elem_id} → {local_path}")
    return str(local_path)


# ============================================================
#   3. Process Manager
# ============================================================
running_processes = {}


def start_process(key, cmd_list):
    """启动子进程"""
    print(f"▶️ 启动进程 [{key}]:", cmd_list)
    p = subprocess.Popen(cmd_list)
    running_processes[key] = p


def kill_processes():
    """杀死所有运行的进程"""
    print("💀 关闭所有进程...")
    for key, proc in running_processes.items():
        try:
            proc.kill()
        except:
            pass
    running_processes.clear()


# ============================================================
#   4. 主逻辑：处理 "add" 和 "remove"
# ============================================================
def handle_add(device):
    print("🔌 USB Add Event")

    fp = get_fingerprint(device)
    unique_key = make_unique_key(fp)
    print("👉 Fingerprint:", unique_key)

    # 查找 AAS
    aas_id = query_matching_aas(unique_key)
    if not aas_id:
        print("❌ 未找到匹配的 AAS")
        return

    print("✔ 匹配到 AAS:", aas_id)

    # 读取 AssetInterface Submodel
    sm = load_submodel(aas_id, "AssetInterface")
    if not sm:
        print("❌ AssetInterface Submodel 未找到")
        return

    # 下载文件
    out_dir = "/tmp/aas_runtime"
    Path(out_dir).mkdir(exist_ok=True)

    driver_path = None
    kuksa_path = None
    orch_path = None

    for elem in sm["submodelElements"]:
        if elem["modelType"] == "File":
            if elem["idShort"] == "DriverFile":
                driver_path = download_file_element(elem, out_dir)
            elif elem["idShort"] == "KuksaFile":
                kuksa_path = download_file_element(elem, out_dir)
            elif elem["idShort"] == "OrchestratorFile":
                orch_path = download_file_element(elem, out_dir)

    # ========== 按顺序启动 ==========
    if driver_path:
        start_process("driver", ["python3", driver_path])

    if kuksa_path:
        start_process("kuksa", ["python3", kuksa_path])

    if orch_path:
        start_process("orchestrator", ["python3", orch_path])


def handle_remove(device):
    print("🔌 USB Remove Event")
    kill_processes()


# ============================================================
#   5. USB Monitor
# ============================================================
def main():
    print("👀 USB Orchestrator Started")
    ctx = pyudev.Context()
    monitor = pyudev.Monitor.from_netlink(ctx)
    monitor.filter_by("usb")

    for action, device in monitor:
        if device.device_type == "usb_device":

            if action == "add":
                handle_add(device)

            elif action == "remove":
                handle_remove(device)


if __name__ == "__main__":
    main()
