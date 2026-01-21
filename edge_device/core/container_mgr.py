#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Container Manager — FINAL VERSION
Fully compatible with new BootstrapAgent + DriverCommand model

Supports:
  ✓ device_path (from DriverCommand.device)
  ✓ environment variables (DriverCommand.env)
  ✓ host network
  ✓ privileged mode
"""

import logging
import time
from typing import Optional, Dict, Any

try:
    import docker
    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False
    print("WARNING: docker library missing. Install: pip install docker")

logger = logging.getLogger("Docker")

class ContainerManager:
    """
    Manages docker driver containers for Plug-and-Play sensors.
    """

    def __init__(self, container_name: str = "active-driver-container"):
        if not DOCKER_AVAILABLE:
            raise RuntimeError("docker python library not installed.")

        self.container_name = container_name
        self.client = docker.from_env()

        logger.info(f"ContainerManager ready (container = {container_name})")

    # ------------------------------------------------------------------
    # Cleanup previous container
    # ------------------------------------------------------------------
    def cleanup(self):
        try:
            container = self.client.containers.get(self.container_name)

            if container.status == "running":
                logger.info("Stopping old driver container…")
                container.stop(timeout=5)

            logger.info("Removing old driver container…")
            container.remove(force=True)
        except docker.errors.NotFound:
            pass
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

    # ------------------------------------------------------------------
    # Pull image if missing
    # ------------------------------------------------------------------
    def _pull_image(self, image: str) -> bool:
        logger.info(f"Checking image: {image}")

        try:
            self.client.images.get(image)
            logger.info("✓ Image already exists locally")
            return True
        except docker.errors.ImageNotFound:
            pass

        logger.info("Pulling image from registry…")
        try:
            for line in self.client.api.pull(image, stream=True, decode=True):
                status = line.get("status")
                if status:
                    logger.debug(status)
            logger.info("✓ Image pulled successfully")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to pull image: {e}")
            return False

    # ------------------------------------------------------------------
    # Start driver container (NEW SIGNATURE)
    # ------------------------------------------------------------------
    def start_driver(
        self,
        image: str,
        device_path: Optional[str] = None,
        environment: Optional[Dict[str, str]] = None
    ) -> bool:
        """
        Start driver container.

        Args:
            image: Docker image name
            device_path: e.g. /dev/video0 /dev/ttyACM0
            environment: dict of env vars from DriverCommand.env
        """
        logger.info(f"Starting driver container (image: {image})")

        self.cleanup()

        if not self._pull_image(image):
            return False

        container_cfg = {
            "name": self.container_name,
            "image": image,
            "detach": True,
            "privileged": True,
            "network_mode": "host",
            "restart_policy": {"Name": "no"},
        }

        # Append environment variables
        if environment:
            container_cfg["environment"] = environment
            logger.info(f"  Injecting env vars: {environment}")

        # Append device mapping
        import os
        if device_path and os.path.exists(device_path):
            container_cfg["devices"] = [f"{device_path}:{device_path}:rwm"]
            logger.info(f"  Mapping device: {device_path}")

        try:
            container = self.client.containers.run(**container_cfg)
            time.sleep(1)
            container.reload()

            if container.status == "running":
                logger.info("✓ Driver container running")
                return True

            logger.error(f"❌ Driver container exited. Logs:")
            logger.error(container.logs().decode())
            return False

        except Exception as e:
            logger.error(f"❌ Failed to start driver: {e}")
            return False

    # ------------------------------------------------------------------
    # Stop driver
    # ------------------------------------------------------------------
    def stop_driver(self):
        try:
            container = self.client.containers.get(self.container_name)
            container.kill()
            container.remove(force=True)
            logger.info("✓ Driver container stopped & removed")
        except docker.errors.NotFound:
            return False
        except Exception as e:
            logger.error(f"Stop error: {e}")
            return False


    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------
    def get_status(self) -> Dict[str, Any]:
        try:
            container = self.client.containers.get(self.container_name)
            return {
                "exists": True,
                "status": container.status,
                "image": container.image.tags,
            }
        except docker.errors.NotFound:
            return {"exists": False}
        except Exception as e:
            return {"exists": False, "error": str(e)}

