"""Security middleware for rate limiting and authentication."""

import logging
from functools import wraps

from flask import jsonify, request

logger = logging.getLogger(__name__)


def init_rate_limiter(app, config):
    """
    Initialize rate limiter if enabled in config.

    Args:
        app: Flask application
        config: Application configuration

    Returns:
        Limiter instance or None if not enabled
    """
    if not config.rate_limit_enabled:
        logger.info("Rate limiting is disabled")
        return None

    try:
        from flask_limiter import Limiter
        from flask_limiter.util import get_remote_address

        limiter = Limiter(
            app=app,
            key_func=get_remote_address,
            default_limits=[config.rate_limit_default],
            storage_uri="memory://",
        )
        logger.info(f"Rate limiting enabled: {config.rate_limit_default}")
        return limiter
    except ImportError:
        logger.warning("Flask-Limiter not installed. Rate limiting disabled. Install with: pip install Flask-Limiter")
        return None


def require_api_key(config):
    """
    Decorator to require API key authentication.

    Args:
        config: Application configuration

    Returns:
        Decorator function
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Skip authentication if disabled
            if not config.api_auth_enabled:
                return f(*args, **kwargs)

            # Check for API key in header
            provided_key = request.headers.get('X-API-Key')

            if not provided_key:
                logger.warning(f"API request without key from {request.remote_addr}")
                return jsonify({
                    'error': 'API key required',
                    'message': 'Please provide X-API-Key header'
                }), 401

            if provided_key != config.api_key:
                logger.warning(f"Invalid API key from {request.remote_addr}")
                return jsonify({
                    'error': 'Invalid API key'
                }), 403

            return f(*args, **kwargs)
        return decorated_function
    return decorator
