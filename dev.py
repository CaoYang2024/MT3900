#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pyudev

def dump_basic(dev, indent=""):
    print(f"{indent}Device: {dev.device_path}")
    print(f"{indent}Subsystem: {dev.subsystem}")
    print(f"{indent}Device type: {dev.device_type}")
    print(f"{indent}Devnode: {dev.device_node}")
    print("")

def dump_attributes(dev, indent=""):
    print(f"{indent}Attributes:")
    for attr in dev.attributes.available_attributes:
        try:
            val = dev.attributes.get(attr)
            if val is not None:
                val = val.decode(errors="ignore")
            print(f"{indent}  {attr}: {val}")
        except:
            pass
    print("")

def dump_env(dev, indent=""):
    print(f"{indent}Environment:")
    for k, v in dev.items():
        print(f"{indent}  {k}: {v}")
    print("")

def main():
    ctx = pyudev.Context()

    print("\n========== USB CAMERA DEVICES ==========\n")

    for dev in ctx.list_devices(subsystem="video4linux"):
        devnode = dev.device_node
        if not devnode:
            continue

        print("========================================")
        print(f"🎥 Found video device: {devnode}")
        print("----------------------------------------\n")

        # 打印 video 节点信息
        print("📌 video4linux node info:")
        dump_basic(dev, "  ")
        dump_attributes(dev, "  ")
        dump_env(dev, "  ")

        # 找到 USB 父设备
        print("🔼 Searching USB parent...")
        parent = dev
        usb_dev = None

        while parent:
            if parent.subsystem == "usb" and parent.device_type == "usb_device":
                usb_dev = parent
                break
            parent = parent.parent

        if usb_dev is None:
            print("❌ This video device is NOT a USB camera (probably CSI camera).")
            print("")
            continue

        print("\n🎉 USB camera parent found!")
        print("📌 USB device info:")
        dump_basic(usb_dev, "  ")
        dump_attributes(usb_dev, "  ")
        dump_env(usb_dev, "  ")

        print("========================================\n")

if __name__ == "__main__":
    main()
