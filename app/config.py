"""Configuration management."""

import yaml
import os
from typing import Dict, Any


class Config:
    """Application configuration."""

    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.data: Dict[str, Any] = {}
        self.load()

    def load(self):
        """Load configuration from YAML file."""
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                self.data = yaml.safe_load(f) or {}
        else:
            self.data = {}

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        keys = key.split('.')
        value = self.data
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
            if value is None:
                return default
        return value

    @property
    def default_stream_url(self) -> str:
        """Get default radio stream URL."""
        return self.get('radio.default_url', '')

    @property
    def server_host(self) -> str:
        """Get Flask server host."""
        return self.get('server.host', '0.0.0.0')

    @property
    def server_port(self) -> int:
        """Get Flask server port."""
        return self.get('server.port', 5000)

    @property
    def stream_port(self) -> int:
        """Get streaming server port."""
        return self.get('streaming.port', 8080)

    @property
    def mp3_bitrate(self) -> str:
        """Get MP3 encoding bitrate."""
        return self.get('streaming.mp3_bitrate', '128k')

    @property
    def stream_public_url(self) -> str:
        """Get public URL for stream (optional, overrides auto-detection)."""
        return self.get('streaming.public_url', '')
