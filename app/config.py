"""Configuration management."""

import os
from typing import Any

import yaml


class Config:
    """Application configuration."""

    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.data: dict[str, Any] = {}
        self.load()

    def load(self):
        """Load configuration from YAML file."""
        if os.path.exists(self.config_path):
            with open(self.config_path) as f:
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
    def default_device_ip(self) -> str:
        """Get default DLNA device IP address."""
        return self.get('dlna.default_device_ip', '')

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

    # Timeout settings
    @property
    def http_request_timeout(self) -> int:
        """Get HTTP request timeout in seconds."""
        return self.get('timeouts.http_request', 10)

    @property
    def stream_detection_timeout(self) -> int:
        """Get stream detection timeout in seconds."""
        return self.get('timeouts.stream_detection', 5)

    @property
    def device_discovery_timeout(self) -> int:
        """Get device discovery timeout in seconds."""
        return self.get('timeouts.device_discovery', 10)

    @property
    def ffmpeg_startup_timeout(self) -> int:
        """Get FFmpeg startup timeout in seconds."""
        return self.get('timeouts.ffmpeg_startup', 10)

    # Security settings
    @property
    def rate_limit_enabled(self) -> bool:
        """Check if rate limiting is enabled."""
        return self.get('security.rate_limit_enabled', False)

    @property
    def rate_limit_default(self) -> str:
        """Get default rate limit."""
        return self.get('security.rate_limit_default', '100 per hour')

    @property
    def api_auth_enabled(self) -> bool:
        """Check if API authentication is enabled."""
        return self.get('security.api_auth_enabled', False)

    @property
    def api_key(self) -> str:
        """Get API key."""
        return self.get('security.api_key', '')

    # Performance settings
    @property
    def gunicorn_workers(self) -> int:
        """Get number of Gunicorn workers."""
        return self.get('performance.gunicorn_workers', 1)

    @property
    def gunicorn_threads(self) -> int:
        """Get number of threads per Gunicorn worker."""
        return self.get('performance.gunicorn_threads', 4)

    @property
    def connection_pool_size(self) -> int:
        """Get HTTP connection pool size."""
        return self.get('performance.connection_pool_size', 10)

    @property
    def connection_pool_maxsize(self) -> int:
        """Get HTTP connection pool max size."""
        return self.get('performance.connection_pool_maxsize', 20)

    # FFmpeg settings
    @property
    def ffmpeg_chunk_size(self) -> int:
        """Get FFmpeg chunk size for streaming."""
        return self.get('ffmpeg.chunk_size', 8192)

    @property
    def ffmpeg_max_stderr_lines(self) -> int:
        """Get max FFmpeg stderr lines to buffer."""
        return self.get('ffmpeg.max_stderr_lines', 1000)

    @property
    def ffmpeg_protocol_whitelist(self) -> str:
        """Get FFmpeg protocol whitelist."""
        return self.get('ffmpeg.protocol_whitelist', 'http,https,tcp,tls')
