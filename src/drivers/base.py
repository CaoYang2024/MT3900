# src/drivers/sensor_driver.py
from __future__ import annotations
from typing import Optional
from .base import DriverBase
from src.utils.aas_client import AASClient


class SensorDriverBase(DriverBase):
    """
    扩展 DriverBase：
    ✅ 支持 AAS EnablePublishing 控制开关
    ✅ 支持 VSS 信号发布路径
    ✅ 提供 start() / stop() 统一管理线程循环
    """

    def __init__(self, vss_path: str, aas_iri: str, enable_key: str):
        self.vss_path = vss_path
        self.aas_iri = aas_iri
        self.enable_key = enable_key

        self.running = True
        self.aas = AASClient()

    # ──────────────────────────────
    # AAS control
    # ──────────────────────────────
    def should_publish(self) -> bool:
        """
        从 AAS Submodel 读取 EnablePublishing 属性
        """
        try:
            return bool(self.aas.get_property_from_shell(
                aas_iri=self.aas_iri,
                submodel_idShort="AssetInterface",
                property_idShort=self.enable_key
            ))
        except Exception:
            return False  # AAS 不可达时不 publish

    # ──────────────────────────────
    # Unified publish loop
    # ──────────────────────────────
    def start(self) -> None:
        """
        主循环：
        open() → iter(read) → publish() → close()
        """
        print(f"▶ Driver started: {self.vss_path}")

        self.open()
        for measurement in self.iter():
            if not self.running:
                break

            if self.should_publish():
                self.publish(measurement)

        self.close()
        print(f"⏹ Driver stopped: {self.vss_path}")

    def publish(self, measurement: object) -> None:
        """
        派生驱动需要 override 或者在这里加 Kuksa 发布逻辑
        """
        print(f"📡 VSS publish [{self.vss_path}] = {measurement}")

    def stop(self):
        """中断 start() 循环"""
        self.running = False
