#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
sensor_monitor.py - PnP Sensor Monitor for UGV
===============================================

This node monitors the Raspberry Pi (Intelligent Sensor Hub) for available
sensors and automatically starts the appropriate Application container.

The flow:
1. Poll Pi's AAS endpoint to check for active sensors
2. When sensor detected, extract Application info from AAS
3. Pull and run the Application container on UGV
4. When sensor disconnects, stop the Application container

This is the UGV-side complement to the Edge Agent running on the Pi.

Usage:
    roslaunch pnp_sensor_monitor monitor.launch
    rosrun pnp_sensor_monitor sensor_monitor.py
"""

import rospy
import yaml
import os
import time
import signal
import sys

# Import our modules
from pnp_sensor_monitor.aas_client import AASClient
from pnp_sensor_monitor.container_manager import ContainerManager


class SensorMonitor:
    """
    Main monitor class that polls the Pi and manages Application containers.
    
    This is intentionally simple - the complexity lives in the Application
    container that the student has developed.
    """
    
    def __init__(self):
        # Load configuration
        config_path = rospy.get_param('~config_file', '')
        if not config_path:
            # Default to package config
            pkg_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(pkg_path, 'config', 'config.yaml')
        
        self.config = self._load_config(config_path)
        
        # Initialize components
        self.aas_client = AASClient(
            pi_address=self.config['pi_address'],
            aas_port=self.config['aas_port']
        )
        
        self.container_mgr = ContainerManager(
            container_prefix=self.config.get('container_prefix', 'pnp-app')
        )
        
        # State
        self.current_sensor = None
        self.current_app_container = None
        self.running = True
        
        # Metrics for evaluation
        self.metrics = {
            'discovery_time_ms': 0,
            'app_start_time_ms': 0,
            'total_integration_time_ms': 0
        }
        
        rospy.loginfo("=" * 50)
        rospy.loginfo("PnP Sensor Monitor initialized")
        rospy.loginfo(f"  Pi Address: {self.config['pi_address']}")
        rospy.loginfo(f"  AAS Port:   {self.config['aas_port']}")
        rospy.loginfo(f"  Poll Rate:  {self.config['poll_interval_sec']}s")
        rospy.loginfo("=" * 50)
    
    def _load_config(self, config_path):
        """Load configuration from YAML file."""
        default_config = {
            'pi_address': '192.168.1.50',
            'aas_port': 8080,
            'poll_interval_sec': 2.0,
            'container_prefix': 'pnp-app'
        }
        
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                loaded = yaml.safe_load(f) or {}
                default_config.update(loaded)
                rospy.loginfo(f"Loaded config from: {config_path}")
        else:
            rospy.logwarn(f"Config not found at {config_path}, using defaults")
        
        return default_config
    
    def check_for_sensor(self):
        """
        Poll the Pi to check if a sensor is available.
        Returns sensor info dict if found, None otherwise.
        """
        t_start = time.time()
        
        # First, quick health check
        health = self.aas_client.get_health()
        
        if health is None:
            # Pi not reachable
            return None
        
        if not health.get('sensor_active', False):
            # No sensor active
            return None
        
        # Sensor is active, fetch full AAS
        aas = self.aas_client.get_aas()
        
        if aas is None:
            return None
        
        # Extract relevant info
        sensor_info = self.aas_client.extract_sensor_info(aas)
        app_info = self.aas_client.extract_application_info(aas)
        driver_info = self.aas_client.extract_driver_info(aas)
        
        if not sensor_info:
            return None
        
        t_end = time.time()
        self.metrics['discovery_time_ms'] = (t_end - t_start) * 1000
        
        return {
            'sensor': sensor_info,
            'application': app_info,
            'driver': driver_info,
            'aas': aas
        }
    
    def start_application(self, sensor_data):
        """
        Start the Application container for the detected sensor.
        
        The Application container (student's code) will:
        - Connect to the driver on Pi
        - Process sensor data (object detection, etc.)
        - Optionally publish to ROS topics or Kuksa
        """
        app_info = sensor_data.get('application', {})
        driver_info = sensor_data.get('driver', {})
        sensor_info = sensor_data.get('sensor', {})
        
        app_image = app_info.get('image', '')
        
        if not app_image:
            rospy.logwarn("No Application image specified in AAS")
            return False
        
        rospy.loginfo(f"Starting Application: {app_image}")
        
        t_start = time.time()
        
        # Build environment variables for the Application container
        # This tells the Application where to find the driver
        environment = {
            'DRIVER_HOST': self.config['pi_address'],
            'DRIVER_PORT': str(driver_info.get('api_port', 8080)),
            'SENSOR_TYPE': sensor_info.get('type', 'unknown'),
            'SENSOR_NAME': sensor_info.get('name', 'unknown'),
        }
        
        # Add any additional env from AAS
        if app_info.get('environment'):
            environment.update(app_info['environment'])
        
        # Start container
        container_name = f"{self.config['container_prefix']}-{sensor_info.get('type', 'sensor')}"
        
        success = self.container_mgr.start_container(
            image=app_image,
            name=container_name,
            environment=environment,
            network_mode='host'  # So it can access Pi and ROS
        )
        
        t_end = time.time()
        self.metrics['app_start_time_ms'] = (t_end - t_start) * 1000
        self.metrics['total_integration_time_ms'] = (
            self.metrics['discovery_time_ms'] + self.metrics['app_start_time_ms']
        )
        
        if success:
            self.current_app_container = container_name
            rospy.loginfo("=" * 50)
            rospy.loginfo("APPLICATION STARTED SUCCESSFULLY")
            rospy.loginfo(f"  Container: {container_name}")
            rospy.loginfo(f"  Discovery Time: {self.metrics['discovery_time_ms']:.1f} ms")
            rospy.loginfo(f"  App Start Time: {self.metrics['app_start_time_ms']:.1f} ms")
            rospy.loginfo(f"  Total Time:     {self.metrics['total_integration_time_ms']:.1f} ms")
            rospy.loginfo("=" * 50)
            return True
        else:
            rospy.logerr(f"Failed to start Application container: {app_image}")
            return False
    
    def stop_application(self):
        """Stop the current Application container."""
        if self.current_app_container:
            rospy.loginfo(f"Stopping Application: {self.current_app_container}")
            self.container_mgr.stop_container(self.current_app_container)
            self.current_app_container = None
    
    def run(self):
        """Main monitoring loop."""
        rate = rospy.Rate(1.0 / self.config['poll_interval_sec'])
        
        rospy.loginfo("Sensor Monitor running. Polling for sensors...")
        
        while not rospy.is_shutdown() and self.running:
            try:
                sensor_data = self.check_for_sensor()
                
                if sensor_data and not self.current_sensor:
                    # New sensor detected
                    sensor_name = sensor_data['sensor'].get('name', 'Unknown')
                    rospy.loginfo(f"Sensor detected: {sensor_name}")
                    
                    self.current_sensor = sensor_data
                    self.start_application(sensor_data)
                
                elif not sensor_data and self.current_sensor:
                    # Sensor disconnected
                    rospy.loginfo("Sensor disconnected")
                    self.stop_application()
                    self.current_sensor = None
                
                rate.sleep()
                
            except Exception as e:
                rospy.logerr(f"Error in monitor loop: {e}")
                rate.sleep()
    
    def shutdown(self):
        """Clean shutdown."""
        rospy.loginfo("Shutting down Sensor Monitor...")
        self.running = False
        self.stop_application()
        self.container_mgr.cleanup()
        rospy.loginfo("Sensor Monitor stopped")


def main():
    rospy.init_node('pnp_sensor_monitor', anonymous=False)
    
    monitor = SensorMonitor()
    
    # Handle shutdown
    def signal_handler(sig, frame):
        monitor.shutdown()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    rospy.on_shutdown(monitor.shutdown)
    
    try:
        monitor.run()
    except rospy.ROSInterruptException:
        pass


if __name__ == '__main__':
    main()
