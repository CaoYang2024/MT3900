#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
pnp_sensor_monitor - Plug-and-Play Sensor Monitor for UGV
=========================================================

This package provides automatic discovery and integration of
PnP sensors connected to a Raspberry Pi (Intelligent Sensor Hub).

Modules:
    aas_client: Fetches and parses AAS from the Pi
    container_manager: Manages Application containers on the UGV
"""

from .aas_client import AASClient
from .container_manager import ContainerManager

__all__ = ['AASClient', 'ContainerManager']
__version__ = '1.0.0'
