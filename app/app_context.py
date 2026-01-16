"""Application context for managing shared state in a thread-safe manner."""

import logging
from threading import RLock
from typing import Any

from app.config import Config
from app.device_manager import DeviceManager
from app.dlna_client import DLNAClient
from app.streamer import AudioStreamer, PassthroughStreamer

logger = logging.getLogger(__name__)


class ApplicationContext:
    """
    Thread-safe application context for managing shared state.

    This class encapsulates all application state (config, device manager,
    streamer, DLNA client) and provides thread-safe access to these components.

    Designed for single-worker multi-threaded deployment to avoid the issues
    with multi-process Gunicorn workers having inconsistent state.
    """

    def __init__(self):
        """Initialize application context."""
        self._lock = RLock()  # Reentrant lock for nested access
        self._config: Config | None = None
        self._device_manager: DeviceManager | None = None
        self._streamer: AudioStreamer | PassthroughStreamer | None = None
        self._dlna_client: DLNAClient | None = None
        logger.info("ApplicationContext created")

    @property
    def config(self) -> Config:
        """Get application configuration."""
        with self._lock:
            if self._config is None:
                raise RuntimeError("ApplicationContext not initialized - call initialize() first")
            return self._config

    @property
    def device_manager(self) -> DeviceManager:
        """Get device manager."""
        with self._lock:
            if self._device_manager is None:
                raise RuntimeError("ApplicationContext not initialized - call initialize() first")
            return self._device_manager

    @property
    def streamer(self) -> AudioStreamer | PassthroughStreamer | None:
        """Get current streamer instance."""
        with self._lock:
            return self._streamer

    @streamer.setter
    def streamer(self, value: AudioStreamer | PassthroughStreamer | None):
        """Set streamer instance."""
        with self._lock:
            self._streamer = value

    @property
    def dlna_client(self) -> DLNAClient | None:
        """Get current DLNA client."""
        with self._lock:
            return self._dlna_client

    @dlna_client.setter
    def dlna_client(self, value: DLNAClient | None):
        """Set DLNA client."""
        with self._lock:
            self._dlna_client = value

    def initialize(self, config: Config, device_manager: DeviceManager):
        """
        Initialize the application context with configuration and device manager.

        Args:
            config: Application configuration
            device_manager: Device manager instance
        """
        with self._lock:
            self._config = config
            self._device_manager = device_manager
            logger.info("ApplicationContext initialized")

    def stop_streamer(self):
        """Stop the current streamer if running."""
        with self._lock:
            if self._streamer and self._streamer.is_running():
                logger.info("Stopping existing stream")
                self._streamer.stop()
                self._streamer = None

    def is_streaming(self) -> bool:
        """Check if currently streaming."""
        with self._lock:
            return self._streamer is not None and self._streamer.is_running()
