"""HTTP client with connection pooling and timeout management."""

import logging
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class HTTPClient:
    """
    HTTP client with connection pooling and configurable timeouts.

    This class provides a singleton session with connection pooling to improve
    performance for multiple HTTP requests.
    """

    _instance: 'HTTPClient | None' = None
    _session: requests.Session | None = None

    def __new__(cls):
        """Singleton pattern to ensure only one instance exists."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize HTTP client with connection pooling."""
        if self._session is not None:
            return  # Already initialized

        self._session = requests.Session()

        # Configure retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=0.3,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )

        # Configure HTTP adapter with connection pooling
        adapter = HTTPAdapter(
            pool_connections=10,
            pool_maxsize=20,
            max_retries=retry_strategy
        )

        self._session.mount("http://", adapter)
        self._session.mount("https://", adapter)

        logger.info("HTTP client initialized with connection pooling")

    def configure(self, pool_connections: int = 10, pool_maxsize: int = 20):
        """
        Configure connection pool size.

        Args:
            pool_connections: Number of connection pools to cache
            pool_maxsize: Maximum number of connections per pool
        """
        if self._session is None:
            return

        retry_strategy = Retry(
            total=3,
            backoff_factor=0.3,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )

        adapter = HTTPAdapter(
            pool_connections=pool_connections,
            pool_maxsize=pool_maxsize,
            max_retries=retry_strategy
        )

        self._session.mount("http://", adapter)
        self._session.mount("https://", adapter)

        logger.info(f"HTTP client reconfigured: pool_connections={pool_connections}, pool_maxsize={pool_maxsize}")

    def get(self, url: str, timeout: int = 10, **kwargs) -> requests.Response:
        """
        Send GET request.

        Args:
            url: URL to request
            timeout: Request timeout in seconds
            **kwargs: Additional arguments for requests.get

        Returns:
            Response object
        """
        return self._session.get(url, timeout=timeout, **kwargs)

    def head(self, url: str, timeout: int = 10, **kwargs) -> requests.Response:
        """
        Send HEAD request.

        Args:
            url: URL to request
            timeout: Request timeout in seconds
            **kwargs: Additional arguments for requests.head

        Returns:
            Response object
        """
        return self._session.head(url, timeout=timeout, **kwargs)

    def post(self, url: str, timeout: int = 10, **kwargs) -> requests.Response:
        """
        Send POST request.

        Args:
            url: URL to request
            timeout: Request timeout in seconds
            **kwargs: Additional arguments for requests.post

        Returns:
            Response object
        """
        return self._session.post(url, timeout=timeout, **kwargs)

    def close(self):
        """Close the session and cleanup resources."""
        if self._session:
            self._session.close()
            logger.info("HTTP client session closed")


# Global singleton instance
http_client = HTTPClient()
