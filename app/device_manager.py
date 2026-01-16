"""Device state management with persistence."""

import json
import logging
import os
import time
from threading import Lock
from typing import Any

logger = logging.getLogger(__name__)


class DeviceManager:
    """Manages selected DLNA device with persistence to state.json."""

    def __init__(self, state_file: str = "/app/state.json"):
        self.state_file = state_file
        self.current_device: dict[str, Any] | None = None
        self.cached_devices: list[dict[str, Any]] = []  # Cache of discovered devices
        self.last_scan_time: float | None = None
        self.lock = Lock()
        logger.info(f"DeviceManager initialized with state file: {self.state_file}")
        self._load_state()

    def _load_state(self):
        """Load device state from JSON file."""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file) as f:
                    data = json.load(f)
                    self.current_device = data.get('current_device')
                    self.cached_devices = data.get('cached_devices', [])
                    self.last_scan_time = data.get('last_scan_time')

                    if self.current_device:
                        logger.debug(f"Loaded saved device: {self.current_device.get('friendly_name', 'Unknown')}")

                    if self.cached_devices:
                        logger.debug(f"Loaded {len(self.cached_devices)} cached devices from state file")
                    else:
                        logger.debug("No cached devices in state file")
            else:
                logger.debug(f"State file {self.state_file} does not exist yet")
        except Exception as e:
            logger.warning(f"Failed to load state file {self.state_file}: {e}")
            self.current_device = None
            self.cached_devices = []
            self.last_scan_time = None

    def _save_state(self):
        """Save device state to JSON file."""
        try:
            # Ensure parent directory exists
            state_dir = os.path.dirname(self.state_file)
            if state_dir and not os.path.exists(state_dir):
                os.makedirs(state_dir, exist_ok=True)
                logger.info(f"Created state directory: {state_dir}")

            data = {
                'current_device': self.current_device,
                'cached_devices': self.cached_devices,
                'last_scan_time': self.last_scan_time
            }

            # Write to temporary file first, then rename (atomic operation)
            temp_file = f"{self.state_file}.tmp"
            with open(temp_file, 'w') as f:
                json.dump(data, f, indent=2)

            # Atomic rename
            os.replace(temp_file, self.state_file)

            logger.debug(f"Device state saved to {self.state_file} ({len(self.cached_devices)} cached devices)")
        except Exception as e:
            logger.error(f"Failed to save state file {self.state_file}: {e}", exc_info=True)
            # Don't re-raise - allow operation to continue with in-memory state only

    def select_device(self, device_info: dict[str, Any]):
        """
        Select a device as the current active device.

        Args:
            device_info: Device information dictionary
        """
        with self.lock:
            self.current_device = device_info
            self._save_state()
            logger.info(f"Selected device: {device_info.get('friendly_name', 'Unknown')}")

    def get_current_device(self) -> dict[str, Any] | None:
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

    def update_device_cache(self, devices: list[dict[str, Any]]):
        """
        Update the cache of discovered devices.

        Args:
            devices: List of device information dictionaries
        """
        with self.lock:
            self.cached_devices = devices
            self.last_scan_time = time.time()
            try:
                self._save_state()
                logger.info(f"Device cache updated with {len(devices)} devices, saved to {self.state_file}")
            except Exception as e:
                logger.error(f"Failed to persist device cache to disk: {e}")
                # Don't re-raise - cache is still updated in memory

    def get_cached_devices(self) -> list[dict[str, Any]]:
        """
        Get cached devices.

        Returns:
            List of cached device information
        """
        with self.lock:
            # Always reload from disk to support multi-worker environments (Gunicorn)
            self._load_state()
            return self.cached_devices.copy()

    def get_cache_age(self) -> float | None:
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

    def find_device_in_cache(self, ip: str = None) -> dict[str, Any] | None:
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
