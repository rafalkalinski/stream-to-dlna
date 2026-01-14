"""Device state management with persistence."""

import json
import logging
import os
from typing import Optional, Dict, Any
from threading import Lock

logger = logging.getLogger(__name__)


class DeviceManager:
    """Manages selected DLNA device with persistence to state.json."""

    def __init__(self, state_file: str = "/app/state.json"):
        self.state_file = state_file
        self.current_device: Optional[Dict[str, Any]] = None
        self.lock = Lock()
        self._load_state()

    def _load_state(self):
        """Load device state from JSON file."""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                    self.current_device = data.get('current_device')
                    if self.current_device:
                        logger.info(f"Loaded saved device: {self.current_device.get('friendly_name', 'Unknown')}")
            else:
                logger.debug(f"State file {self.state_file} does not exist yet")
        except Exception as e:
            logger.warning(f"Failed to load state file: {e}")
            self.current_device = None

    def _save_state(self):
        """Save device state to JSON file."""
        try:
            data = {
                'current_device': self.current_device
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
            return self.current_device.copy() if self.current_device else None

    def get_device_by_id(self, device_id: str) -> Optional[Dict[str, Any]]:
        """
        Get device by ID (currently just returns current if ID matches).

        Args:
            device_id: Device ID to look up

        Returns:
            Device information or None if not found
        """
        with self.lock:
            if self.current_device and self.current_device.get('id') == device_id:
                return self.current_device.copy()
            return None

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
