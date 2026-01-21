#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
aas_client.py - AAS Client for fetching sensor info from Pi
============================================================

This module handles communication with the Raspberry Pi's AAS server.
It fetches the AAS and extracts relevant information for the UGV.

The AAS structure expected (from your project):
- TechnicalData: VendorID, ProductID, SensorType, etc.
- AssetInterface: Port, VSSPath, FrameURL, StreamURL
- EdgeDriver: DriverImage, DriverVersion, DriverCommand
- Application: AppImage, AppVersion, AppCommand
"""

import json
import rospy
import requests
from typing import Dict, Optional


class AASClient:
    """
    Client for fetching and parsing AAS from the Raspberry Pi.
    """
    
    def __init__(self, pi_address: str, aas_port: int = 8080):
        """
        Initialize the AAS client.
        
        Args:
            pi_address: IP address of the Raspberry Pi
            aas_port: Port where AAS server runs (default 8080)
        """
        self.pi_address = pi_address
        self.aas_port = aas_port
        self.base_url = f"http://{pi_address}:{aas_port}"
        self._last_aas = None
    
    def get_aas(self) -> Optional[Dict]:
        """
        Fetch the current AAS from the Pi.
        
        Returns:
            AAS dict if available, None if Pi is unreachable or no sensor active
        """
        try:
            url = f"{self.base_url}/shell"
            response = requests.get(url, timeout=2.0)
            
            if response.status_code == 200:
                self._last_aas = response.json()
                return self._last_aas
            elif response.status_code == 503:
                # No sensor active (student's code returns 503)
                return None
            elif response.status_code == 404:
                # No sensor active (alternative)
                return None
            else:
                rospy.logwarn_throttle(10, f"AAS server returned: {response.status_code}")
                return None
                
        except requests.exceptions.ConnectionError:
            rospy.logdebug_throttle(10, f"Cannot connect to Pi at {self.base_url}")
            return None
        except requests.exceptions.Timeout:
            rospy.logdebug_throttle(10, f"Timeout connecting to Pi")
            return None
        except json.JSONDecodeError as e:
            rospy.logwarn(f"Invalid JSON from AAS server: {e}")
            return None
        except Exception as e:
            rospy.logwarn_throttle(10, f"Error fetching AAS: {e}")
            return None
    
    def get_health(self) -> Optional[Dict]:
        """
        Fetch health status from the Pi's AAS server.
        
        Returns:
            {
                'status': 'healthy',
                'sensor_active': True/False,
                'aas_id': '...',
                'aas_idshort': '...'
            }
        """
        try:
            url = f"{self.base_url}/health"
            response = requests.get(url, timeout=2.0)
            
            if response.status_code == 200:
                return response.json()
            return None
            
        except Exception:
            return None
    
    def is_sensor_available(self) -> bool:
        """Quick check if a sensor is available using health endpoint."""
        health = self.get_health()
        if health:
            return health.get('sensor_active', False)
        # Fallback to trying /shell
        return self.get_aas() is not None
    
    def extract_sensor_info(self, aas: Dict) -> Dict:
        """
        Extract sensor information from TechnicalData submodel.
        
        Returns:
            {
                'vendor_id': '05a3',
                'product_id': '9331',
                'type': 'camera',
                'name': 'HD_Web_Camera',
                'category': 'VisionSensor'
            }
        """
        result = {}
        
        submodels = aas.get('submodels', [])
        
        for sm in submodels:
            if sm.get('idShort') == 'TechnicalData':
                for elem in sm.get('submodelElements', []):
                    id_short = elem.get('idShort', '')
                    
                    if id_short == 'DeviceSignature':
                        for prop in elem.get('value', []):
                            prop_id = prop.get('idShort', '')
                            prop_val = prop.get('value', '')
                            
                            if prop_id == 'VendorID':
                                result['vendor_id'] = prop_val
                            elif prop_id == 'ProductID':
                                result['product_id'] = prop_val
                    
                    elif id_short == 'StaticCharacteristics':
                        for prop in elem.get('value', []):
                            prop_id = prop.get('idShort', '')
                            prop_val = prop.get('value', '')
                            
                            if prop_id == 'SensorType':
                                result['type'] = prop_val
                            elif prop_id == 'Manufacturer':
                                result['manufacturer'] = prop_val
                            elif prop_id == 'Model':
                                result['name'] = prop_val
                            elif prop_id == 'Category':
                                result['category'] = prop_val
                break
        
        # Fallback name
        if 'name' not in result:
            result['name'] = aas.get('idShort', 'Unknown Sensor')
        
        return result
    
    def extract_driver_info(self, aas: Dict) -> Dict:
        """
        Extract driver information from EdgeDriver submodel.
        
        Returns:
            {
                'image': 'st186635/camera-driver:v1',
                'version': '1.0.0',
                'device': '/dev/video0',
                'api_port': 8000,
                'environment': {...}
            }
        """
        result = {
            'image': '',
            'version': '',
            'device': '',
            'api_port': 8080,
            'environment': {}
        }
        
        submodels = aas.get('submodels', [])
        
        for sm in submodels:
            if sm.get('idShort') == 'EdgeDriver':
                for elem in sm.get('submodelElements', []):
                    id_short = elem.get('idShort', '')
                    value = elem.get('value', '')
                    
                    if id_short == 'DriverImage':
                        result['image'] = value
                    elif id_short == 'DriverVersion':
                        result['version'] = value
                    elif id_short == 'DriverCommand':
                        # Parse JSON command
                        try:
                            cmd = json.loads(value) if value else {}
                            result['device'] = cmd.get('device', '')
                            result['api_port'] = cmd.get('api_port', 8080)
                            result['environment'] = cmd.get('env', {})
                        except json.JSONDecodeError:
                            pass
                break
        
        return result
    
    def extract_application_info(self, aas: Dict) -> Dict:
        """
        Extract application information from Application submodel.
        
        Returns:
            {
                'image': 'st186635/object-detector:v1',
                'version': '1.0.0',
                'command': '',
                'environment': {}
            }
        """
        result = {
            'image': '',
            'version': '',
            'command': '',
            'environment': {}
        }
        
        submodels = aas.get('submodels', [])
        
        for sm in submodels:
            if sm.get('idShort') == 'Application':
                for elem in sm.get('submodelElements', []):
                    id_short = elem.get('idShort', '')
                    value = elem.get('value', '')
                    
                    if id_short == 'AppImage':
                        result['image'] = value
                    elif id_short == 'AppVersion':
                        result['version'] = value
                    elif id_short == 'AppCommand':
                        # Parse JSON command if present
                        if value:
                            try:
                                cmd = json.loads(value)
                                result['command'] = cmd.get('command', '')
                                result['environment'] = cmd.get('env', {})
                            except json.JSONDecodeError:
                                result['command'] = value
                break
        
        return result
    
    def extract_asset_interface(self, aas: Dict) -> Dict:
        """
        Extract asset interface information from AssetInterface submodel.
        
        Returns:
            {
                'port': '/dev/video0',
                'vss_path': 'Vehicle.Cabin.Camera.Front',
                'frame_url': 'http://...:8000/frame',
                'stream_url': 'http://...:8000/video'
            }
        """
        result = {}
        
        submodels = aas.get('submodels', [])
        
        for sm in submodels:
            if sm.get('idShort') == 'AssetInterface':
                for elem in sm.get('submodelElements', []):
                    id_short = elem.get('idShort', '')
                    value = elem.get('value', '')
                    
                    if id_short == 'Port':
                        result['port'] = value
                    elif id_short == 'VSSPath':
                        result['vss_path'] = value
                    elif id_short == 'FrameURL':
                        result['frame_url'] = value
                    elif id_short == 'StreamURL':
                        result['stream_url'] = value
                    elif id_short == 'Value':
                        result['value'] = value
                break
        
        return result
