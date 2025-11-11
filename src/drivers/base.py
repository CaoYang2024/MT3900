#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
基础 Driver 抽象层
所有驱动必须提供 start() / stop()
"""

class DriverBase:
    """最小抽象，只定义接口"""
    def start(self):
        raise NotImplementedError("Driver must implement start()")

    def stop(self):
        raise NotImplementedError("Driver must implement stop()")
