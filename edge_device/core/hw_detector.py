import logging
import threading
import time
from typing import Callable, Dict, Optional, List

try:
    import pyudev
except ImportError:
    raise RuntimeError("pyudev not installed. pip install pyudev")

logger = logging.getLogger("HW")

class HardwareDetector:
    """
    HardwareDetector (Enhanced)
    ---------------------------
    Thread-safe wrapper around pyudev with state synchronization capabilities.
    """

    def __init__(self):
        self.context = pyudev.Context()
        self.monitor = None
        self.observer = None
        
        # Thread lock for shared resources
        self._lock = threading.RLock()

        # Callbacks
        self.on_add_callback: Optional[Callable[[str], None]] = None
        self.on_remove_callback: Optional[Callable[[str], None]] = None

        # State: Signature -> Device Path
        self.known_devices: Dict[str, str] = {}

        logger.info("Hardware detector initialized")

    def _get_signature(self, dev: pyudev.Device) -> Optional[str]:
        """Extracts VID:PID signature safely."""
        vid = dev.get("ID_VENDOR_ID")
        pid = dev.get("ID_MODEL_ID")

        if not vid:
            try:
                vid = dev.attributes.get("idVendor").decode('utf-8')
                pid = dev.attributes.get("idProduct").decode('utf-8')
            except (AttributeError, Exception):
                pass

        if vid and pid:
            return f"usb_vid_{vid.lower()}_pid_{pid.lower()}"
        return None

    def scan_connected(self, trigger_callbacks=False) -> List[Dict]:
        """
        Scans currently connected devices.
        
        Args:
            trigger_callbacks (bool): If True, fires on_add_callback for found devices.
                                      Useful for initial startup or re-sync.
        """
        devices = []
        # Use a set to track devices found in the current scan for cache reconciliation
        current_scan_sigs = set()

        with self._lock:
            # Enumerate only top-level USB devices
            for dev in self.context.list_devices(subsystem="usb", DEVTYPE="usb_device"):
                sig = self._get_signature(dev)
                if not sig:
                    continue

                current_scan_sigs.add(sig)
                
                # If this is a newly discovered device, update the cache
                if sig not in self.known_devices:
                    self.known_devices[sig] = dev.device_path
                    if trigger_callbacks and self.on_add_callback:
                        logger.info(f"[Scan] Found new device: {sig}")
                        try:
                            self.on_add_callback(sig)
                        except Exception as e:
                            logger.error(f"Error in on_add callback during scan: {e}")
                
                devices.append({
                    "signature": sig,
                    "name": dev.get("ID_MODEL", "Unknown Device"),
                    "path": dev.device_path
                })
            
            # (Optional) Prune devices from cache that no longer exist.
            # Note: Use caution during frequent hot-plugging, but to maintain state consistency,
            # we remove entries that are in known_devices but not in the current scan results.
            for existing_sig in list(self.known_devices.keys()):
                if existing_sig not in current_scan_sigs:
                    logger.debug(f"[Scan] Removing stale device from cache: {existing_sig}")
                    del self.known_devices[existing_sig]

        logger.info(f"Scan complete: {len(devices)} devices active.")
        return devices

    def resync_devices(self):
        """
        [Critical Fix]
        Force re-trigger 'add' events for all currently connected devices.
        Call this method when the Agent resets from 'Busy' to 'Idle'.
        """
        logger.info("Resyncing hardware state...")
        with self._lock:
            # Create a copy to iterate safely
            current_sigs = list(self.known_devices.keys())
        
        for sig in current_sigs:
            logger.info(f"[Resync] Re-triggering detection for: {sig}")
            if self.on_add_callback:
                try:
                    self.on_add_callback(sig)
                except Exception as e:
                    logger.error(f"Error triggering callback for {sig}: {e}")

    def _event_handler(self, device: pyudev.Device):
        """
        Internal handler running in the Observer thread.
        """
        # Catch all exceptions to prevent the monitor thread from crashing due to a callback error
        try:
            action = device.action
            
            if device.get("DEVTYPE") != "usb_device":
                return

            with self._lock:
                if action == "add":
                    self._handle_add(device)
                elif action == "remove":
                    self._handle_remove(device)
        except Exception as e:
            logger.error(f"Unhandled exception in HW monitor thread: {e}")

    def _handle_add(self, dev: pyudev.Device):
        sig = self._get_signature(dev)
        if not sig:
            return

        # Debounce: If we already know this device, don't fire again
        if sig in self.known_devices:
            return

        logger.info(f"[+] USB ADD: {sig}")
        self.known_devices[sig] = dev.device_path
        
        if self.on_add_callback:
            try:
                self.on_add_callback(sig)
            except Exception as e:
                logger.error(f"Error in on_add callback: {e}")

    def _handle_remove(self, dev: pyudev.Device):
        removed_path = dev.device_path
        target_sig = None

        # Reverse lookup
        for sig, path in self.known_devices.items():
            if path == removed_path:
                target_sig = sig
                break
        
        if target_sig:
            logger.info(f"[-] USB REMOVE: {target_sig}")
            del self.known_devices[target_sig]
            
            if self.on_remove_callback:
                try:
                    self.on_remove_callback(target_sig)
                except Exception as e:
                    logger.error(f"Error in on_remove callback: {e}")
        else:
            # This is a common scenario (e.g., removing a non-monitored device); 
            # no error log needed, debug level is sufficient.
            logger.debug(f"Ignored removal of unknown path: {removed_path}")

    def start_monitoring(self, on_add: Callable, on_remove: Callable):
        if self.observer:
            logger.warning("Monitoring already active.")
            return

        self.on_add_callback = on_add
        self.on_remove_callback = on_remove

        self.monitor = pyudev.Monitor.from_netlink(self.context)
        self.monitor.filter_by(subsystem="usb")
        
        self.observer = pyudev.MonitorObserver(
            self.monitor,
            callback=self._event_handler,
            name="USBObserver"
        )
        self.observer.start()
        logger.info("USB Monitoring started (Background Thread)")

    def stop_monitoring(self):
        if self.observer:
            self.observer.stop()
            self.observer = None
            logger.info("USB Monitoring stopped")