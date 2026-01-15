"""Device state management with persistence."""

import json
import logging
import os
import time
from typing import Optional, Dict, Any, List
from threading import Lock

logger = logging.getLogger(__name__)


class DeviceManager:
    """Manages selected DLNA device with persistence to state.json."""

    def __init__(self, state_file: str = "/app/state.json"):
        self.state_file = state_file
        self.current_device: Optional[Dict[str, Any]] = None
        self.cached_devices: List[Dict[str, Any]] = []  # Cache of discovered devices
        self.last_scan_time: Optional[float] = None
        self.lock = Lock()
        self._load_state()

    def _load_state(self):
        """Load device state from JSON file."""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                    self.current_device = data.get('current_device')
                    self.cached_devices = data.get('cached_devices', [])
                    self.last_scan_time = data.get('last_scan_time')
                    if self.current_device:
                        logger.debug(f"Loaded saved device: {self.current_device.get('friendly_name', 'Unknown')}")
            else:
                logger.debug(f"State file {self.state_file} does not exist yet")
        except Exception as e:
            logger.warning(f"Failed to load state file: {e}")
            self.current_device = None
            self.cached_devices = []
            self.last_scan_time = None

    def _save_state(self):
        """Save device state to JSON file."""
        try:
            data = {
                'current_device': self.current_device,
                'cached_devices': self.cached_devices,
                'last_scan_time': self.last_scan_time
            }
            with open(self.state_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.debug("Device state saved to file")
        except Exception as e:
            logger.error(f"Failed to save state file: {e}")

    def select_device(self, device_info: Dict[str, Any]):
        """
        Select a device as the current active device.

        Args:
            device_info: Device information dictionary
        """
        with self.lock:
            self.current_device = device_info
            self._save_state()
            logger.info(f"Selected device: {device_info.get('friendly_name', 'Unknown')}")

    def get_current_device(self) -> Optional[Dict[str, Any]]:
        """
        Get the currently selected device.

        Returns:
            Device information dictionary or None if no device selected
        """
        with self.lock:
            # Always reload from disk to support multi-worker environments (Gunicorn)
            # Each worker process has its own memory, so we must read from shared storage
            self._load_state()
            return self.current_device.copy() if self.current_device else None

    def clear_device(self):
        """Clear the currently selected device."""
        with self.lock:
            self.current_device = None
            self._save_state()
            logger.info("Cleared selected device")

    def has_device(self) -> bool:
        """Check if a device is currently selected."""
        with self.lock:
            return self.current_device is not None

    def update_device_cache(self, devices: List[Dict[str, Any]]):
        """
        Update the cache of discovered devices.

        Args:
            devices: List of device information dictionaries
        """
        with self.lock:
            self.cached_devices = devices
            self.last_scan_time = time.time()
            self._save_state()
            logger.info(f"Device cache updated with {len(devices)} devices")

    def get_cached_devices(self) -> List[Dict[str, Any]]:
        """
        Get cached devices.

        Returns:
            List of cached device information
        """
        with self.lock:
            # Always reload from disk to support multi-worker environments (Gunicorn)
            self._load_state()
            return self.cached_devices.copy()

    def get_cache_age(self) -> Optional[float]:
        """
        Get age of device cache in seconds.

        Returns:
            Age in seconds or None if never scanned
        """
        with self.lock:
            # Always reload from disk to support multi-worker environments (Gunicorn)
            self._load_state()
            if self.last_scan_time is None:
                return None
            return time.time() - self.last_scan_time

    def find_device_in_cache(self, ip: str = None) -> Optional[Dict[str, Any]]:
        """
        Find device in cache by IP address.

        Args:
            ip: IP address to search for

        Returns:
            Device info or None if not found
        """
        with self.lock:
            # Always reload from disk to support multi-worker environments (Gunicorn)
            self._load_state()
            for device in self.cached_devices:
                if ip and device.get('ip') == ip:
                    return device.copy()
            return None
