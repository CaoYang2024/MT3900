#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Sensor Driver Template
- 提供线程驱动的数据读取循环
- 支持 AAS EnablePublishing 控制
"""

from __future__ import annotations
import threading
from typing import Optional
from .base import DriverBase
from src.utils.aas_client import AASClient   # ✅ 如未使用 AAS，可不导入


class SensorDriverBase(DriverBase):
    def __init__(self, vss_path: str = None, aas_iri: str = None, enable_key: str = None):
        """
        vss_path: 发布到 Kuksa 的路径 (可选)
        aas_iri : AAS Shell ID，用于读取 enable 开关 (可选)
        enable_key: Submodel 中 EnablePublishing 的 idShort (可选)
        """
        self.vss_path = vss_path
        self.aas_iri = aas_iri
        self.enable_key = enable_key

        self.running = False
        self.thread: Optional[threading.Thread] = None

        self.aas = AASClient() if aas_iri else None


    # ---------------- AAS 开关控制 ----------------
    def should_publish(self) -> bool:
        """从 AAS 读取 enable_publishing 状态"""
        if not self.aas or not self.aas_iri or not self.enable_key:
            return True  # 如果没有 AAS，默认允许 publish

        try:
            value = self.aas.get_property_from_shell(
                aas_iri=self.aas_iri,
                submodel_idShort="AssetInterface",
                property_idShort=self.enable_key
            )
            return bool(value)
        except:
            return False


    # ---------------- 生命周期控制 ----------------
    def _loop(self):
        """内部统一循环：read → publish"""
        self.open()  # 子类自己实现

        for measurement in self.iter():  # generator
            if not self.running:
                break

            if self.should_publish():
                self.publish(measurement)

        self.close()


    def start(self):
        """启动驱动循环（不会阻塞主线程）"""
        if self.running:
            print("⚠️ driver already running")
            return

        print(f"▶ Driver start: {self.__class__.__name__}")
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()


    def stop(self):
        """停止循环"""
        print(f"⏹ Driver stop: {self.__class__.__name__}")
        self.running = False


    # ---------------- 子类必须 override ----------------
    def open(self):
        """初始化资源，例如打开串口 / 视频流"""
        pass

    def iter(self):
        """读数循环，必须 yield"""
        yield None

    def close(self):
        """释放资源"""
        pass

    def publish(self, measurement):
        """默认行为：打印，可 override"""
        print(f"[{self.vss_path}] = {measurement}")
