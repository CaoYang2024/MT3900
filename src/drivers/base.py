from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Generator, Optional
from . import __init__ as _  # 只是确保包初始化


class DriverBase(ABC):
    """
    传感器驱动抽象基类：统一 open/read/close/iter 接口。
    """

    @abstractmethod
    def open(self) -> None:
        """打开设备/连接资源。"""
        raise NotImplementedError

    @abstractmethod
    def read(self) -> Optional[object]:
        """
        读取一次测量。
        返回 Measurement 或 None（读取失败时）。
        """
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        """释放资源。"""
        raise NotImplementedError

    def iter(self) -> Generator[object, None, None]:
        """
        默认连续读取（阻塞），交给具体驱动实现 read() 的频率控制。
        """
        while True:
            m = self.read()
            if m is None:
                break
            yield m
