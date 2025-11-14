#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from src.orchestrator.ultrasonic import SensorOrchestrator


def main():
    print("\n============================")
    print("   🚀 Ultrasonic Orchestrator")
    print("============================\n")

    orch = SensorOrchestrator(
        config_path="/home/pi/Downloads/MT3900/src/aas/ultrasonic.yaml",
        aas_host="http://192.168.137.1:8081",
        kuksa_server="192.168.137.1:55555"
    )

    # 1. 生成 AAS JSON
    json_path = orch.generate_aas()

    # 2. 上传到 BaSyx
    orch.upload_aas(json_path)

    # 3. 初始化超声波 driver
    orch.init_driver()

    # 4. 初始化 Kuksa（非阻塞 publish）
    orch.init_backend()

    # 5. 持续循环：读取 → Publish → PUT
    orch.start_loop()


if __name__ == "__main__":
    main()
