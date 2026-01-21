"""
Cloud Client Module

This module handles communication with the OEM Cloud Proxy.
It provides a simple interface for looking up AAS definitions
based on hardware signatures.

The cloud proxy handles all the complexity of:
- Querying the BaSyx Registry to find AAS IDs
- Fetching AAS shells from the BaSyx Repository
- Hydrating submodel references into full content

This edge client just needs to make one HTTP request and receive
the complete, hydrated AAS JSON ready for processing.
"""

import logging
from typing import Optional, Dict, Any

import requests

logger = logging.getLogger('Cloud')


class CloudClient:
    """
    HTTP client for the OEM Cloud Proxy.
    
    This class provides a simple interface to the cloud proxy's
    lookup endpoint. The proxy handles all BaSyx complexity.
    
    Usage:
        client = CloudClient("http://192.168.137.100:5000")
        
        # Look up AAS for a device
        aas_data = client.lookup("usb_vid_05a3_pid_9331")
        if aas_data:
            print(f"Found: {aas_data['idShort']}")
        else:
            print("Device not supported")
    """
    
    def __init__(self, base_url: str, timeout: int = 10):
        """
        Initialize the cloud client.
        
        Args:
            base_url: Base URL of the cloud proxy (e.g., "http://192.168.137.100:5000")
            timeout: Request timeout in seconds
        """
        # Ensure URL doesn't have trailing slash
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        
        logger.info(f"Cloud client initialized: {self.base_url}")
    
    def lookup(self, signature: str) -> Optional[Dict[str, Any]]:
        """
        Look up an AAS definition for a hardware signature.
        
        This queries the cloud proxy's /lookup endpoint, which:
        1. Searches the BaSyx Registry for matching AAS
        2. Fetches the AAS shell from the Repository
        3. Hydrates all submodel references
        4. Returns the complete AAS JSON
        
        Args:
            signature: Hardware signature (e.g., "usb_vid_05a3_pid_9331")
            
        Returns:
            Complete hydrated AAS dictionary if found, None otherwise
        """
        url = f"{self.base_url}/lookup"
        params = {"signature": signature}
        
        logger.info(f"Querying cloud: {url}?signature={signature}")
        
        try:
            response = requests.get(
                url,
                params=params,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                aas_data = response.json()
                logger.info(f"Found AAS: {aas_data.get('idShort', 'Unknown')}")
                logger.debug(f"AAS ID: {aas_data.get('id')}")
                logger.debug(f"Submodels: {len(aas_data.get('submodels', []))}")
                return aas_data
                
            elif response.status_code == 404:
                logger.warning(f"No AAS found for signature: {signature}")
                return None
                
            else:
                logger.error(f"Cloud returned HTTP {response.status_code}")
                try:
                    detail = response.json().get('detail', response.text)
                    logger.error(f"  Detail: {detail}")
                except:
                    logger.error(f"  Response: {response.text[:200]}")
                return None
                
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Cannot connect to cloud: {self.base_url}")
            logger.error(f"  Error: {e}")
            logger.error("  Check that the cloud proxy is running and reachable.")
            return None
            
        except requests.exceptions.Timeout:
            logger.error(f"Cloud request timed out after {self.timeout}s")
            return None
            
        except Exception as e:
            logger.error(f"Unexpected error during cloud lookup: {e}")
            return None
    
    def check_health(self) -> Dict[str, Any]:
        """
        Check the health of the cloud proxy.
        
        Returns:
            Health status dictionary or error information
        """
        url = f"{self.base_url}/health"
        
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                return response.json()
            else:
                return {"status": "error", "code": response.status_code}
        except Exception as e:
            return {"status": "unreachable", "error": str(e)}
    
    def is_reachable(self) -> bool:
        """
        Quick check if the cloud proxy is reachable.
        
        Returns:
            True if proxy responds to health check, False otherwise
        """
        health = self.check_health()
        return health.get('status') in ['healthy', 'degraded']


# =============================================================================
# STANDALONE TESTING
# =============================================================================

if __name__ == '__main__':
    """Test the cloud client standalone."""
    import sys
    
    logging.basicConfig(level=logging.DEBUG)
    
    # Get URL from command line or use default
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5000"
    sig = sys.argv[2] if len(sys.argv) > 2 else "usb_vid_05a3_pid_9331"
    
    print(f"Testing Cloud Client")
    print(f"=" * 40)
    print(f"URL: {url}")
    print(f"Signature: {sig}")
    print()
    
    client = CloudClient(url)
    
    # Test health check
    print("Checking health...")
    health = client.check_health()
    print(f"  Health: {health}")
    print()
    
    # Test lookup
    print(f"Looking up {sig}...")
    result = client.lookup(sig)
    if result:
        print(f"  Found: {result.get('idShort')}")
        print(f"  ID: {result.get('id')}")
        print(f"  Submodels: {len(result.get('submodels', []))}")
    else:
        print("  Not found")
