#!/usr/bin/env python3
from pyudev import Context

ctx = Context()

print("\n🔍 Scanning all USB devices...\n")

usb_devices = []

# 遍历所有设备，找 usb_device
for dev in ctx.list_devices(subsystem='usb', DEVTYPE='usb_device'):
    vendor = dev.attributes.get('idVendor')
    product = dev.attributes.get('idProduct')
    serial = dev.attributes.get('serial')

    # 找该 USB device 下的所有子节点（ttyUSB, video, HID, etc.）
    children = []
    for child in dev.children:
        node = getattr(child, "device_node", None)
        if node:
            children.append(node)

    usb_devices.append({
        "vendor": vendor.decode() if vendor else None,
        "product": product.decode() if product else None,
        "serial": serial.decode() if serial else None,
        "children": children,
        "sys_path": dev.sys_path,
    })

# 打印结果
for i, dev in enumerate(usb_devices, 1):
    print(f"Device {i}:")
    print(f"  Vendor : {dev['vendor']}")
    print(f"  Product: {dev['product']}")
    print(f"  Serial : {dev['serial']}")
    print(f"  Nodes  : {dev['children']}")
    print(f"  Sysfs  : {dev['sys_path']}")
    print("-" * 40)
