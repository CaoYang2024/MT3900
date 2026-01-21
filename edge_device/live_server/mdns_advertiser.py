"""
mDNS Advertiser Module

This module handles mDNS (multicast DNS) advertisement of the AAS service.
When a sensor is active, we advertise it so other systems on the local
network can discover it without knowing the IP address in advance.

How mDNS works:
- mDNS allows devices to advertise services on the local network
- Other devices can query for services by type (e.g., "_http._tcp")
- No central DNS server is required - it's peer-to-peer
- Common implementation: Apple Bonjour, Linux Avahi

Our service advertisement:
- Service type: _aas._tcp (Asset Administration Shell over TCP)
- Service name: edge-id-sensor-name (e.g., "pi-01-webcam")
- TXT records: Additional metadata (AAS ID, version, etc.)

Implementation:
On Linux, we create an Avahi service file in /etc/avahi/services/.
Avahi monitors this directory and automatically advertises/removes services.
"""

import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger('mDNS')


class MDNSAdvertiser:
    """
    Advertises the AAS service via mDNS using Avahi.
    
    Avahi is the standard mDNS implementation on Linux. We advertise
    our service by creating a .service file in /etc/avahi/services/.
    Avahi monitors this directory and handles the mDNS protocol.
    
    Usage:
        advertiser = MDNSAdvertiser("192.168.1.100", 8080, "pi-01")
        advertiser.advertise("webcam")  # Start advertising
        advertiser.stop()  # Stop advertising
    """
    
    # Default paths for Avahi service files
    AVAHI_SERVICES_DIR = "/etc/avahi/services"
    SERVICE_FILE_NAME = "aas-pnp.service"
    
    def __init__(self, host: str, port: int, edge_id: str):
        """
        Initialize the mDNS advertiser.
        
        Args:
            host: IP address of the AAS server
            port: Port number of the AAS server
            edge_id: Unique identifier for this edge device
        """
        self.host = host
        self.port = port
        self.edge_id = edge_id
        self.service_file_path = Path(self.AVAHI_SERVICES_DIR) / self.SERVICE_FILE_NAME
        self.is_advertising = False
        
        logger.info(f"mDNS Advertiser initialized for {edge_id}")
    
    def _create_service_file_content(self, sensor_name: str) -> str:
        """
        Create the content for an Avahi service file.
        
        The service file is XML that tells Avahi what to advertise.
        
        Args:
            sensor_name: Human-readable name for the sensor
            
        Returns:
            XML content for the service file
        """
        service_name = f"{self.edge_id}-{sensor_name}".replace(' ', '-').lower()
        
        content = f"""<?xml version="1.0" standalone='no'?>
<!DOCTYPE service-group SYSTEM "avahi-service.dtd">
<!--
    AAS Plug-and-Play Service Advertisement
    Generated automatically - do not edit manually
    
    Edge Device: {self.edge_id}
    Sensor: {sensor_name}
-->
<service-group>
    <name>{service_name}</name>
    
    <service>
        <type>_aas._tcp</type>
        <port>{self.port}</port>
        
        <!-- TXT records provide additional metadata -->
        <txt-record>id={self.edge_id}</txt-record>
        <txt-record>path=/shell</txt-record>
        <txt-record>sensor={sensor_name}</txt-record>
        <txt-record>version=2.0</txt-record>
    </service>
    
    <!-- Also advertise as HTTP for generic discovery -->
    <service>
        <type>_http._tcp</type>
        <port>{self.port}</port>
        <txt-record>path=/shell</txt-record>
    </service>
</service-group>
"""
        return content
    
    def advertise(self, sensor_name: str) -> bool:
        """
        Start advertising the AAS service.
        
        Creates an Avahi service file that causes Avahi to advertise
        our AAS server on the local network.
        
        Args:
            sensor_name: Human-readable name for the sensor
            
        Returns:
            True if advertising started successfully
        """
        logger.info(f"Starting mDNS advertisement for: {sensor_name}")
        
        # Check if Avahi services directory exists
        if not os.path.isdir(self.AVAHI_SERVICES_DIR):
            logger.warning(f"Avahi services directory not found: {self.AVAHI_SERVICES_DIR}")
            logger.warning("mDNS advertisement will be skipped")
            logger.warning("Install Avahi with: sudo apt install avahi-daemon")
            return False
        
        # Generate service file content
        content = self._create_service_file_content(sensor_name)
        
        # Write the service file
        try:
            with open(self.service_file_path, 'w') as f:
                f.write(content)
            
            self.is_advertising = True
            logger.info(f"mDNS service file created: {self.service_file_path}")
            logger.info(f"Service advertised as: {self.edge_id}-{sensor_name.lower()}")
            
            # Log discovery information
            logger.info("Other devices can discover this service using:")
            logger.info(f"  avahi-browse -r _aas._tcp")
            logger.info(f"  dns-sd -B _aas._tcp (on macOS)")
            
            return True
            
        except PermissionError:
            logger.error(f"Permission denied writing to {self.service_file_path}")
            logger.error("Run the agent with sudo, or add write permission to the directory")
            return False
        except Exception as e:
            logger.error(f"Failed to create service file: {e}")
            return False
    
    def stop(self) -> bool:
        """
        Stop advertising the AAS service.
        
        Removes the Avahi service file, which causes Avahi to stop
        advertising our service.
        
        Returns:
            True if advertising was stopped successfully
        """
        if not self.is_advertising:
            return True
        
        logger.info("Stopping mDNS advertisement...")
        
        try:
            if self.service_file_path.exists():
                os.remove(self.service_file_path)
                logger.info(f"Removed service file: {self.service_file_path}")
            
            self.is_advertising = False
            return True
            
        except PermissionError:
            logger.error(f"Permission denied removing {self.service_file_path}")
            return False
        except Exception as e:
            logger.error(f"Failed to remove service file: {e}")
            return False
    
    def is_avahi_available(self) -> bool:
        """
        Check if Avahi is available on this system.
        
        Returns:
            True if Avahi appears to be installed and configured
        """
        return os.path.isdir(self.AVAHI_SERVICES_DIR)


class MDNSAdvertiserFallback:
    """
    Fallback mDNS advertiser using python-zeroconf.
    
    This is used when Avahi is not available (e.g., on non-Linux systems
    or when Avahi is not installed).
    
    Note: This requires the zeroconf package: pip install zeroconf
    """
    
    def __init__(self, host: str, port: int, edge_id: str):
        """Initialize the fallback advertiser."""
        self.host = host
        self.port = port
        self.edge_id = edge_id
        self.zeroconf = None
        self.service_info = None
        
        try:
            from zeroconf import Zeroconf, ServiceInfo
            self._zeroconf_available = True
        except ImportError:
            self._zeroconf_available = False
            logger.warning("zeroconf not installed - mDNS will not be available")
    
    def advertise(self, sensor_name: str) -> bool:
        """Start advertising using zeroconf."""
        if not self._zeroconf_available:
            return False
        
        try:
            from zeroconf import Zeroconf, ServiceInfo
            import socket
            
            service_name = f"{self.edge_id}-{sensor_name}".replace(' ', '-').lower()
            
            # Create service info
            self.service_info = ServiceInfo(
                "_aas._tcp.local.",
                f"{service_name}._aas._tcp.local.",
                addresses=[socket.inet_aton(self.host)],
                port=self.port,
                properties={
                    'id': self.edge_id,
                    'path': '/shell',
                    'sensor': sensor_name,
                    'version': '2.0'
                }
            )
            
            # Register the service
            self.zeroconf = Zeroconf()
            self.zeroconf.register_service(self.service_info)
            
            logger.info(f"mDNS service registered via zeroconf: {service_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to advertise via zeroconf: {e}")
            return False
    
    def stop(self) -> bool:
        """Stop advertising using zeroconf."""
        if self.zeroconf and self.service_info:
            try:
                self.zeroconf.unregister_service(self.service_info)
                self.zeroconf.close()
                logger.info("mDNS service unregistered")
                return True
            except Exception as e:
                logger.error(f"Failed to stop zeroconf: {e}")
                return False
        return True


def create_advertiser(host: str, port: int, edge_id: str):
    """
    Factory function to create the appropriate mDNS advertiser.
    
    Returns an Avahi-based advertiser on Linux if available,
    otherwise falls back to python-zeroconf.
    
    Args:
        host: IP address of the AAS server
        port: Port number of the AAS server
        edge_id: Unique identifier for this edge device
        
    Returns:
        An mDNS advertiser instance
    """
    # Try Avahi first (Linux)
    advertiser = MDNSAdvertiser(host, port, edge_id)
    if advertiser.is_avahi_available():
        logger.info("Using Avahi for mDNS advertisement")
        return advertiser
    
    # Fall back to zeroconf
    logger.info("Avahi not available, trying zeroconf fallback")
    return MDNSAdvertiserFallback(host, port, edge_id)


# =============================================================================
# STANDALONE TESTING
# =============================================================================

if __name__ == '__main__':
    """Test the mDNS advertiser standalone."""
    import time
    
    logging.basicConfig(level=logging.DEBUG)
    
    print("Testing mDNS Advertiser")
    print("=" * 40)
    
    advertiser = create_advertiser("192.168.1.100", 8080, "test-pi")
    
    print("\nStarting advertisement...")
    success = advertiser.advertise("TestCamera")
    
    if success:
        print("\nService is being advertised.")
        print("On another device, try:")
        print("  avahi-browse -r _aas._tcp")
        print("\nPress Ctrl+C to stop...")
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
    
    print("\nStopping advertisement...")
    advertiser.stop()
    
    print("Test complete")
