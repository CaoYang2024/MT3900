# src/orchestrator/watcher.py
# -*- coding: utf-8 -*-

"""
监听 USB / 设备插拔事件，并返回 { type: "ADD" / "REMOVE", path: <device-path>, aas_iri: <AAS IRI> }
"""

import pyudev

def watch_new_device():
    context = pyudev.Context()
    monitor = pyudev.Monitor.from_netlink(context)
    monitor.filter_by(subsystem="usb")   # 如果你要支持 /dev/video, USB2Serial，这里可以扩展

    print("👀 Watching for USB devices ...")

    for device in iter(monitor.poll, None):
        dev_node = device.device_node  # /dev/ttyUSB0 / dev/video0

        if device.action == "add":
            print(f"✅ USB 插入: {dev_node}")

            # !!! 暂时返回一个固定的 AAS IRI，等你配置自动识别
            # 你把这里换成 detect_aas_from_device()
            return_data = {
                "type": "ADD",
                "path": dev_node,
                "aas_iri": "https://CaoYang/AASbyLLM/tree/main/AAS_Samples/ids/aas/I2C_Temperature_TMP117"
            }
            yield return_data

        elif device.action == "remove":
            print(f"❌ USB 拔出: {dev_node}")
            yield {
                "type": "REMOVE",
                "path": dev_node,
                "aas_iri": None
            }
