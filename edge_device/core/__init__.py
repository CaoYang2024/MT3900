"""
Core modules for the AAS Plug-and-Play Bootstrap Agent.

This package contains the main functional components:
- hw_detector: USB device detection using pyudev
- cloud_client: HTTP client for the OEM cloud proxy
- container_mgr: Docker container lifecycle management
- aas_processor: AAS JSON parsing and processing
"""

from .hw_detector import HardwareDetector
from .cloud_client import CloudClient
from .container_mgr import ContainerManager
from .aas_processor import AASProcessor

__all__ = [
    'HardwareDetector',
    'CloudClient',
    'ContainerManager',
    'AASProcessor',
]
