#!/usr/bin/env python3
"""
AAS Plug-and-Play Bootstrap Agent (Evaluation Ready & Filtered)
===============================================================
Orchestrates USB detection, Cloud AAS lookup, and Docker driver deployment.
Integrates system resource monitoring via metrics.py.
Includes filtering for internal Raspberry Pi system devices.
"""

import logging
import os
import signal
import socket
import sys
import threading
import time
import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

import socket
import fcntl
import struct

import yaml

# Add local folder for module imports
sys.path.insert(0, str(Path(__file__).parent))

# --- Local Imports ---
try:
    from core.hw_detector import HardwareDetector
    from core.cloud_client import CloudClient
    from core.container_mgr import ContainerManager
    from core.aas_processor import AASProcessor
    from live_server.aas_server import AASServer
    from live_server.mdns_advertiser import create_advertiser
except ImportError as e:
    sys.exit(f"Critical Error: Missing required modules. {e}")


# =============================================================================
# METRICS HELPER (NO-OP PATTERN)
# =============================================================================

class NoOpMetricsCollector:
    """
    A dummy collector that does nothing when --evaluate is not used.
    Matches the interface of metrics.MetricsCollector.
    """
    def start_run(self, *args, **kwargs): return "noop_run"
    def mark(self, *args, **kwargs): pass
    def set_info(self, *args, **kwargs): pass  # Added to prevent AttributeError
    def end_run(self, *args, **kwargs): pass
    def abort_run(self, *args, **kwargs): pass


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class AppConfig:
    """Strongly typed configuration settings."""
    cloud_url: str = 'http://192.168.137.1:5000'
    edge_id: str = 'pi-01'
    aas_port: int = 8080
    log_level: str = 'INFO'
    driver_container_name: str = 'active-driver-container'
    single_sensor_mode: bool = True
    metrics_dir: str = "/home/pi/evaluation_results"  # Default output dir
    evaluate_mode: bool = False

    @classmethod
    def load(cls, evaluate_flag: bool = False) -> 'AppConfig':
        """Loads config from yaml and overrides with environment variables."""
        config_path = Path(__file__).parent / 'config.yaml'
        defaults = {}
        
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    data = yaml.safe_load(f) or {}
                    defaults.update({
                        'cloud_url': data.get('cloud', {}).get('url'),
                        'edge_id': data.get('edge', {}).get('id'),
                        'aas_port': data.get('edge', {}).get('aas_port'),
                        'log_level': data.get('logging', {}).get('level'),
                    })
            except Exception as e:
                print(f"Warning: Failed to parse config.yaml: {e}")

        # Instantiate with YAML defaults (filtering None)
        cfg = cls(**{k: v for k, v in defaults.items() if v is not None})

        # Environment variable overrides
        cfg.cloud_url = os.getenv('CLOUD_REPO_URL', cfg.cloud_url)
        cfg.edge_id = os.getenv('EDGE_ID', cfg.edge_id)
        cfg.aas_port = int(os.getenv('AAS_SERVER_PORT', cfg.aas_port))
        cfg.log_level = os.getenv('LOG_LEVEL', cfg.log_level)
        
        # Set evaluation mode
        cfg.evaluate_mode = evaluate_flag
        
        return cfg


# =============================================================================
# LOGGING
# =============================================================================

def setup_logger(level_name: str) -> logging.Logger:
    level = getattr(logging, level_name.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
        datefmt='%H:%M:%S'
    )
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('docker').setLevel(logging.WARNING)
    return logging.getLogger("BootstrapAgent")


# =============================================================================
# MAIN AGENT
# =============================================================================

class BootstrapAgent:
    """
    Main orchestrator for the Plug-and-Play lifecycle.
    """

    def __init__(self, config: AppConfig):
        self.cfg = config
        self.logger = logging.getLogger("BootstrapAgent")
        
        # Concurrency control
        self._lock = threading.Lock()
        self._shutdown_event = threading.Event()
        self.active_signature: Optional[str] = None

        self.local_ip = self._resolve_local_ip()

        self.logger.info("Initializing subsystems...")
        self.hw_detector = HardwareDetector()
        self.cloud_client = CloudClient(self.cfg.cloud_url)
        self.container_mgr = ContainerManager(self.cfg.driver_container_name)
        self.aas_processor = AASProcessor()
        self.aas_server = AASServer(self.local_ip, self.cfg.aas_port)
        self.mdns_advertiser = create_advertiser(self.local_ip, self.cfg.aas_port, self.cfg.edge_id)

        # --- EVALUATION / METRICS INIT ---
        if self.cfg.evaluate_mode:
            try:
                # Import the enhanced metrics.py we defined earlier
                from metrics import MetricsCollector
                self.metrics = MetricsCollector(output_dir=self.cfg.metrics_dir)
                self.logger.info(f"Evaluation Mode: ENABLED. Logging to {self.cfg.metrics_dir}")
                self.logger.info("Resource monitoring (CPU/RAM/Temp) is ACTIVE.")
            except ImportError:
                self.logger.error("Evaluation mode requested but 'metrics.py' not found.")
                self.logger.error("Please place metrics.py in the same directory.")
                sys.exit(1)
        else:
            self.metrics = NoOpMetricsCollector()
            self.logger.info("Evaluation Mode: DISABLED")
        # ---------------------------------

        self.logger.info(f"Agent initialized on {self.local_ip}")

    def _resolve_local_ip(self, iface: str = "eth0") -> str:
        """
        Deterministically get IPv4 address of a given interface (default: eth0).
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            ip = socket.inet_ntoa(
                fcntl.ioctl(
                    sock.fileno(),
                    0x8915,  # SIOCGIFADDR
                    struct.pack('256s', iface[:15].encode('utf-8'))
                )[20:24]
            )
            return ip
        except OSError as e:
            self.logger.error(
                f"Failed to resolve IP for interface '{iface}': {e}"
            )
            return "127.0.0.1"


    def _print_banner(self):
        print("\n" + "=" * 60)
        print(f"  AAS PLUG-AND-PLAY AGENT | ID: {self.cfg.edge_id}")
        print("=" * 60)
        print(f"  Cloud: {self.cfg.cloud_url}")
        print(f"  IP:    {self.local_ip}:{self.cfg.aas_port}")
        print(f"  Mode:  {'Single-Sensor' if self.cfg.single_sensor_mode else 'Multi-Sensor'}")
        print(f"  Eval:  {'ON' if self.cfg.evaluate_mode else 'OFF'}")
        print("=" * 60 + "\n")

    # -------------------------------------------------------------------------
    # LIFECYCLE HANDLERS
    # -------------------------------------------------------------------------

    def on_device_added(self, signature: str):
        """Callback for udev add event."""
        
        # --- SYSTEM DEVICE FILTERING ---
        # Define Vendor IDs (VIDs) to ignore:
        # vid_1d6b: Linux Foundation (Root Hubs)
        # vid_2109: VIA Labs (Raspberry Pi 4 Internal USB 3.0 Hub)
        # vid_0424: Standard Microsystems (Pi 3 Internal Hub/Ethernet)
        SYSTEM_DEVICE_VIDS = ["vid_1d6b", "vid_2109", "vid_0424"]

        if any(sys_id in signature for sys_id in SYSTEM_DEVICE_VIDS):
            self.logger.debug(f"Ignoring system device: {signature}")
            return
        # -------------------------------

        if not self._lock.acquire(blocking=False):
            self.logger.debug(f"Ignored {signature} momentarily: Agent lock busy.")
            return

        try:
            if self.active_signature:
                if self.active_signature != signature:
                    self.logger.warning(f"System busy. Ignoring {signature} because {self.active_signature} is active.")
                return

            self._process_new_device(signature)
            
        except Exception as e:
            self.logger.error(f"Error processing device {signature}: {e}")
            self.metrics.abort_run(f"Exception: {e}")
        finally:
            self._lock.release()

    def _process_new_device(self, signature: str):
        self.logger.info(f" >>> STARTING INTEGRATION: {signature}")
        
        # 1. Start Metrics Run (Take baseline resource snapshot)
        self.metrics.start_run(signature, edge_id=self.cfg.edge_id)
        
        # 2. Hardware Detect (Mark detected timestamp)
        self.metrics.mark("detected")

        # 3. Cloud Lookup
        self.metrics.mark("lookup_start")
        aas_data = self.cloud_client.lookup(signature)
        self.metrics.mark("aas_received") # Resource snapshot after network I/O

        if not aas_data:
            self._abort("No AAS found in cloud", signature)
            return

        # 4. Parse Metadata
        driver_info = self.aas_processor.extract_driver_info(aas_data)
        self.metrics.mark("parse_complete")
        
        if not driver_info:
            self._abort("Invalid driver info in AAS", signature)
            return
            
        # Optional: Record extra info in metrics
        self.metrics.set_info(
            sensor_name=driver_info.get("sensor_type", "Unknown"),
            container_image=driver_info.get("driver_image", "")
        )

        # 5. Deploy Driver (This is the heavy CPU/RAM phase)
        if not self._deploy_driver(driver_info, aas_data):
            self._abort("Driver deployment failed", signature)
            return

        # 6. Start Live Services (AAS Server / mDNS)
        self._start_live_services(aas_data, signature)

        # 7. Finalize
        self.active_signature = signature
        self.metrics.end_run(success=True, sensor_name=driver_info.get("sensor_type", "Sensor"))
        self.logger.info(f" >>> DEVICE READY: {driver_info.get('sensor_type')}")

    def _deploy_driver(self, driver_info: Dict, aas_data: Dict) -> bool:
        image = driver_info["driver_image"]
        cmd_config = driver_info["driver_command"]
        
        env_vars = cmd_config.get("env", {}).copy()
        env_vars.update({
            "AAS_ID": aas_data["id"],
            "AAS_SERVER": self.cfg.cloud_url.replace("5000", "8081"),
            "DRIVER_API_PORT": str(cmd_config.get("api_port", 8000))
        })

        device_path = (cmd_config.get("device") or 
                       driver_info.get("port") or 
                       "/dev/video0")

        self.logger.info(f"Deploying driver: {image}")
        
        # --- Metrics: Pull Start ---
        # Marks the start of the most resource-intensive phase
        self.metrics.mark("pull_start")
        
        # Note: container_mgr.start_driver is usually blocking.
        # It performs 'docker pull' AND 'docker run'.
        success = self.container_mgr.start_driver(
            image=image,
            device_path=device_path,
            environment=env_vars
        )
        
        # --- Metrics: Pull Complete / Container Started ---
        # Since start_driver is blocking, we mark both here to close the duration windows
        self.metrics.mark("pull_complete")
        
        if success:
            self.metrics.mark("container_started") # Container is officially Up
            self.metrics.mark("container_ready")   # Driver logic assumed ready
            
        return success

    def _start_live_services(self, aas_data: Dict, signature: str):
        instance_data = self.aas_processor.create_instance(
            aas_data,
            signature=signature,
            edge_id=self.cfg.edge_id,
            local_ip=self.local_ip
        )
        
        self.aas_server.set_aas_data(instance_data)
        self.aas_server.start()
        self.metrics.mark("aas_server_ready")

        short_id = aas_data.get("idShort", "sensor")
        self.mdns_advertiser.advertise(short_id)
        self.metrics.mark("mdns_advertised")

    def _abort(self, reason: str, signature: str):
        self.logger.error(f"Abort: {reason} ({signature})")
        self.metrics.abort_run(reason)

    def on_device_removed(self, signature: str):
        """Callback for udev remove event."""
        with self._lock:
            if self.active_signature != signature:
                 return
            
            self.logger.info(f" <<< DEVICE REMOVED: {signature}")
            self.mdns_advertiser.stop()
            self.aas_server.stop()
            self.container_mgr.stop_driver()
            
            self.active_signature = None
            self.logger.info("System reset and waiting for device.")

        self.hw_detector.resync_devices()

    def run(self):
        self._print_banner()
        self.container_mgr.cleanup()
        
        self.logger.info("Starting hardware monitor...")
        self.hw_detector.start_monitoring(
            on_add=self.on_device_added,
            on_remove=self.on_device_removed
        )

        self.logger.info("Scanning for existing devices...")
        self.hw_detector.scan_connected(trigger_callbacks=True)

        try:
            while not self._shutdown_event.is_set():
                time.sleep(1.0)
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        self.logger.info("Stopping agent...")
        self._shutdown_event.set()
        self.mdns_advertiser.stop()
        self.aas_server.stop()
        self.container_mgr.stop_driver()
        self.hw_detector.stop_monitoring()
        self.logger.info("Agent stopped.")


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == '__main__':
    # 1. Parse Arguments for --evaluate
    parser = argparse.ArgumentParser(description="AAS Bootstrap Agent")
    parser.add_argument('--evaluate', action='store_true', help="Enable metrics and resource collection")
    args = parser.parse_args()

    # 2. Pass flag to config
    config = AppConfig.load(evaluate_flag=args.evaluate)
    setup_logger(config.log_level)

    agent = BootstrapAgent(config)
    
    def handle_signal(signum, frame):
        agent.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    agent.run()