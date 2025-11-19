#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Main entrypoint for Camera Sensor Adapter
- 只负责启动 USB Camera Orchestrator
- 不包含任何业务逻辑（保持产品稳定）
"""

from src.orchestrator.camera_orchestrator import main as camera_main


if __name__ == "__main__":
    print("\n====================================")
    print("        🚀 Sensor Adapter")
    print("      (USB Camera Version)")
    print("====================================\n")

    # 调用摄像头适配器（热插拔监听 + AAS 自动生成）
    camera_main()
