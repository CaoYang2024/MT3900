#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
container_manager.py - Docker Container Manager for Applications
================================================================

This module handles running Application containers on the UGV.
It uses the Docker SDK to pull images and manage container lifecycle.

The Application container is the student's code that:
- Connects to the driver REST API on the Pi
- Processes sensor data (object detection, distance warnings, etc.)
- Optionally publishes to ROS or Kuksa
"""

import rospy
import docker
from typing import Dict, Optional, List


class ContainerManager:
    """
    Manages Application containers on the UGV.
    
    This is simpler than the Edge Agent's container manager because:
    - We only run Application containers (not drivers)
    - Containers don't need device passthrough
    - We use host networking for ROS/Kuksa access
    """
    
    def __init__(self, container_prefix: str = 'pnp-app'):
        """
        Initialize the container manager.
        
        Args:
            container_prefix: Prefix for container names (for easy identification)
        """
        self.prefix = container_prefix
        self.client = None
        self.active_containers: Dict[str, str] = {}  # name -> container_id
        
        self._connect_docker()
    
    def _connect_docker(self):
        """Connect to Docker daemon."""
        try:
            self.client = docker.from_env()
            self.client.ping()
            rospy.loginfo("Connected to Docker daemon")
        except docker.errors.DockerException as e:
            rospy.logerr(f"Cannot connect to Docker: {e}")
            rospy.logerr("Make sure Docker is running and user has permissions")
            self.client = None
    
    def is_available(self) -> bool:
        """Check if Docker is available."""
        return self.client is not None
    
    def pull_image(self, image: str) -> bool:
        """
        Pull a Docker image if not present locally.
        
        Args:
            image: Image name with tag (e.g., 'st186635/object-detector:v1')
            
        Returns:
            True if image is available (pulled or already present)
        """
        if not self.client:
            return False
        
        try:
            # Check if image exists locally
            try:
                self.client.images.get(image)
                rospy.loginfo(f"Image already present: {image}")
                return True
            except docker.errors.ImageNotFound:
                pass
            
            # Pull the image
            rospy.loginfo(f"Pulling image: {image}")
            self.client.images.pull(image)
            rospy.loginfo(f"Image pulled successfully: {image}")
            return True
            
        except docker.errors.APIError as e:
            rospy.logerr(f"Failed to pull image {image}: {e}")
            return False
    
    def start_container(self, image: str, name: str, 
                        environment: Dict[str, str] = None,
                        network_mode: str = 'host',
                        volumes: Dict[str, Dict] = None,
                        command: str = None) -> bool:
        """
        Start an Application container.
        
        Args:
            image: Docker image name
            name: Container name
            environment: Environment variables dict
            network_mode: Docker network mode ('host' recommended for ROS)
            volumes: Volume mounts
            command: Override command (optional)
            
        Returns:
            True if container started successfully
        """
        if not self.client:
            rospy.logerr("Docker not available")
            return False
        
        # Pull image first
        if not self.pull_image(image):
            return False
        
        # Stop existing container with same name
        self.stop_container(name)
        
        try:
            rospy.loginfo(f"Starting container: {name}")
            rospy.loginfo(f"  Image: {image}")
            rospy.loginfo(f"  Network: {network_mode}")
            if environment:
                for k, v in environment.items():
                    rospy.loginfo(f"  Env: {k}={v}")
            
            # Prepare container config
            config = {
                'image': image,
                'name': name,
                'detach': True,
                'network_mode': network_mode,
                'environment': environment or {},
                'restart_policy': {'Name': 'unless-stopped'}
            }
            
            if volumes:
                config['volumes'] = volumes
            
            if command:
                config['command'] = command
            
            # Run container
            container = self.client.containers.run(**config)
            
            self.active_containers[name] = container.id
            rospy.loginfo(f"Container started: {name} ({container.short_id})")
            return True
            
        except docker.errors.APIError as e:
            rospy.logerr(f"Failed to start container: {e}")
            return False
    
    def stop_container(self, name: str) -> bool:
        """
        Stop and remove a container by name.
        
        Args:
            name: Container name
            
        Returns:
            True if stopped successfully (or didn't exist)
        """
        if not self.client:
            return False
        
        try:
            container = self.client.containers.get(name)
            rospy.loginfo(f"Stopping container: {name}")
            container.stop(timeout=10)
            container.remove()
            
            if name in self.active_containers:
                del self.active_containers[name]
            
            rospy.loginfo(f"Container stopped: {name}")
            return True
            
        except docker.errors.NotFound:
            # Container doesn't exist, that's fine
            return True
        except docker.errors.APIError as e:
            rospy.logwarn(f"Error stopping container {name}: {e}")
            return False
    
    def is_running(self, name: str) -> bool:
        """Check if a container is running."""
        if not self.client:
            return False
        
        try:
            container = self.client.containers.get(name)
            return container.status == 'running'
        except docker.errors.NotFound:
            return False
    
    def get_container_logs(self, name: str, tail: int = 50) -> str:
        """Get recent logs from a container."""
        if not self.client:
            return ""
        
        try:
            container = self.client.containers.get(name)
            return container.logs(tail=tail).decode('utf-8')
        except docker.errors.NotFound:
            return ""
        except Exception as e:
            return f"Error getting logs: {e}"
    
    def cleanup(self):
        """Stop all containers managed by this instance."""
        rospy.loginfo("Cleaning up containers...")
        
        for name in list(self.active_containers.keys()):
            self.stop_container(name)
        
        # Also clean up any orphaned containers with our prefix
        if self.client:
            try:
                containers = self.client.containers.list(all=True)
                for container in containers:
                    if container.name.startswith(self.prefix):
                        rospy.loginfo(f"Cleaning up orphaned container: {container.name}")
                        try:
                            container.stop(timeout=5)
                            container.remove()
                        except:
                            pass
            except:
                pass
    
    def list_running(self) -> List[str]:
        """List all running containers with our prefix."""
        if not self.client:
            return []
        
        result = []
        try:
            containers = self.client.containers.list()
            for container in containers:
                if container.name.startswith(self.prefix):
                    result.append(container.name)
        except:
            pass
        
        return result
