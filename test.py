#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Periodic USB device watcher (poll every 10 sec)
"""

import pyudev
import time

def get_connected_devices(context):
    """Return a set of currently connected device IDs"""
    devices = set()
    for device in context.list_devices(subsystem='usb', DEVTYPE='usb_device'):
        # 组合 Vendor + Product + Serial 作为唯一标识
        info = f"{device.get('ID_VENDOR_ID')}-{device.get('ID_MODEL_ID')}-{device.get('ID_SERIAL_SHORT')}"
        devices.add(info)
    return devices


def main():
    context = pyudev.Context()

    last_devices = get_connected_devices(context)
    print("✅ 初始 USB 设备列表:")
    print(last_devices)

    while True:
        time.sleep(10)    # ⏳ 每隔10秒检查一次

        current_devices = get_connected_devices(context)

        # 新增设备
        added = current_devices - last_devices
        # 移除设备
        removed = last_devices - current_devices

        if added:
            print("\n🔌 **设备插入:**")
            for dev in added:
                print(f"  ➕ {dev}")

        if removed:
            print("\n❌ **设备移除:**")
            for dev in removed:
                print(f"  ➖ {dev}")

        last_devices = current_devices


if __name__ == "__main__":
    print("🚀 USB watcher running (checks every 10s)...")
    main()
