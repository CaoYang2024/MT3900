#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import glob
import subprocess

def list_serial_ports():
    print("\n==============================")
    print("🔵 检测树莓派串口设备")
    print("==============================")

    ports = glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyAMA*")
    if ports:
        print("找到串口设备:")
        for p in ports:
            print(f"  • {p}")
    else:
        print("⚠️ 没有找到 ttyACM*/ttyUSB*/ttyAMA* 设备")

def print_dmesg():
    print("\n==============================")
    print("🔵 打印与串口相关的 dmesg 日志")
    print("==============================")

    try:
        output = subprocess.check_output("dmesg | grep -i tty", shell=True, text=True)
        print(output if output.strip() else "⚠️ dmesg 中未找到 tty 相关信息")
    except Exception as e:
        print(f"读取 dmesg 失败: {e}")

def guess_port():
    print("\n==============================")
    print("🔵 自动推断可能的超声波串口")
    print("==============================")

    # 优先顺序：USB → ACM → AMA
    candidates = (
        glob.glob("/dev/ttyUSB*") +
        glob.glob("/dev/ttyACM*") +
        glob.glob("/dev/ttyAMA*")
    )

    if not candidates:
        print("⚠️ 没有可用串口")
        return

    print("可能的串口候选（按优先级排序）:")
    for c in candidates:
        print(f"  • {c}")

    print("\n👉 最有可能的端口是:", candidates[0])

def main():
    list_serial_ports()
    print_dmesg()
    guess_port()

if __name__ == "__main__":
    main()
