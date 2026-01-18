"""Stream format detection cache with persistent storage."""

import hashlib
import json
import logging
import os
import time
from pathlib import Path

logger = logging.getLogger(__name__)


class StreamFormatCache:
    """
    Persistent cache for stream format detection results.

    Caches Content-Type and codec information to avoid repeated
    HEAD requests and FFprobe analysis for the same streams.
    """

    def __init__(self, data_dir: str, ttl: int = 86400):
        """
        Initialize stream format cache.

        Args:
            data_dir: Directory for cache storage
            ttl: Time-to-live for cache entries in seconds (default: 24h)
        """
        self.data_dir = Path(data_dir)
        self.ttl = ttl
        self.cache_file = self.data_dir / 'stream_format_cache.json'
        self.cache = {}
        self._ensure_data_dir()
        self._load_cache()

    def _ensure_data_dir(self):
        """Create data directory if it doesn't exist."""
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Data directory ready: {self.data_dir}")
        except Exception as e:
            logger.error(f"Failed to create data directory {self.data_dir}: {e}")

    def _load_cache(self):
        """Load cache from disk."""
        if not self.cache_file.exists():
            logger.debug("No cache file found, starting with empty cache")
            return

        try:
            with open(self.cache_file, 'r') as f:
                self.cache = json.load(f)
            logger.info(f"Loaded stream format cache with {len(self.cache)} entries")
        except Exception as e:
            logger.warning(f"Failed to load cache file: {e}")
            self.cache = {}

    def _save_cache(self):
        """Save cache to disk."""
        try:
            # Clean expired entries before saving
            self._cleanup_expired()

            with open(self.cache_file, 'w') as f:
                json.dump(self.cache, f, indent=2)
            logger.debug(f"Saved stream format cache ({len(self.cache)} entries)")
        except Exception as e:
            logger.error(f"Failed to save cache file: {e}")

    def _cleanup_expired(self):
        """Remove expired cache entries."""
        now = time.time()
        expired_keys = [
            key for key, entry in self.cache.items()
            if now - entry.get('timestamp', 0) > self.ttl
        ]

        for key in expired_keys:
            del self.cache[key]

        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")

    def _get_cache_key(self, url: str) -> str:
        """
        Generate cache key from URL.

        Uses SHA256 hash to handle long URLs and special characters.

        Args:
            url: Stream URL

        Returns:
            Cache key string
        """
        return hashlib.sha256(url.encode('utf-8')).hexdigest()[:16]

    def get(self, url: str) -> dict | None:
        """
        Get cached stream format information.

        Args:
            url: Stream URL

        Returns:
            Cached data dict or None if not found/expired
        """
        key = self._get_cache_key(url)
        entry = self.cache.get(key)

        if not entry:
            return None

        # Check if expired
        now = time.time()
        if now - entry.get('timestamp', 0) > self.ttl:
            logger.debug(f"Cache entry expired for URL hash {key}")
            del self.cache[key]
            return None

        logger.info(f"Cache HIT for stream format: {entry.get('mime_type')} (age: {int(now - entry.get('timestamp', 0))}s)")
        return entry

    def set(self, url: str, mime_type: str, detection_method: str = 'head'):
        """
        Cache stream format information.

        Args:
            url: Stream URL
            mime_type: Detected MIME type
            detection_method: How it was detected ('head', 'ffprobe', etc.)
        """
        key = self._get_cache_key(url)

        entry = {
            'url': url,  # Store full URL for debugging (consider privacy!)
            'mime_type': mime_type,
            'detection_method': detection_method,
            'timestamp': time.time()
        }

        self.cache[key] = entry
        self._save_cache()

        logger.info(f"Cached stream format: {mime_type} via {detection_method}")

    def clear(self):
        """Clear entire cache."""
        self.cache = {}
        self._save_cache()
        logger.info("Stream format cache cleared")
