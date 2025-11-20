#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
统一 USB Hotplug 监控脚本
-------------------------
当任意 USB 设备被插入时，返回可以唯一识别设备的指纹：
- idVendor
- idProduct
- serial
- subsystem
- devnode
- manufacturer
- product
"""

import pyudev
import json


def get_device_fingerprint(device):
    """提取设备的唯一识别信息."""

    def _get(attr):
        val = device.get(attr)
        return val if val is None else val

    fp = {
        "idVendor": _get("ID_VENDOR_ID"),
        "idProduct": _get("ID_MODEL_ID"),
        "serial": _get("ID_SERIAL_SHORT"),
        "subsystem": device.subsystem,
        "devnode": device.device_node,
        "manufacturer": _get("ID_VENDOR"),
        "product": _get("ID_MODEL"),
    }

    return fp


def main():
    context = pyudev.Context()
    monitor = pyudev.Monitor.from_netlink(context)

    # 监听所有 USB 设备（不区分 video / tty / usb）
    monitor.filter_by(subsystem="usb")

    print("🔍 Start monitoring USB devices...\n")

    for action, device in monitor:
        if action == "add" and device.device_type == "usb_device":
            print("🔌 [ADD] USB Device detected")
            fp = get_device_fingerprint(device)

            print(json.dumps(fp, indent=2, ensure_ascii=False))

            # 返回一个真正可用于 AAS 匹配的唯一 key
            unique_key = f"{fp['idVendor']}:{fp['idProduct']}:{fp.get('serial','')}"
            print(f"👉 Unique Device Key = {unique_key}")

            print("-" * 40)


if __name__ == "__main__":
    main()
