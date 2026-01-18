"""Main Flask application for DLNA Radio Streamer."""

import json
import logging
import os
import re
import socket
import subprocess
import sys
from urllib.parse import urlparse

from flask import Flask, jsonify, render_template, request

from app import __version__
from app.config import Config
from app.device_manager import DeviceManager
from app.discovery import SSDPDiscovery
from app.dlna_client import DLNAClient
from app.http_client import http_client
from app.security import init_rate_limiter, require_api_key
from app.stream_cache import StreamFormatCache
from app.streamer import AudioStreamer, PassthroughStreamer

# Configure logging
log_level_name = os.environ.get('LOG_LEVEL', 'INFO').upper()
log_level = getattr(logging, log_level_name, logging.INFO)

logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)
logger.info(f"Log level set to {log_level_name}")

# Suppress werkzeug logging for /health endpoint
werkzeug_logger = logging.getLogger('werkzeug')

class HealthCheckFilter(logging.Filter):
    def filter(self, record):
        # Don't log /health requests
        return '/health' not in record.getMessage()

werkzeug_logger.addFilter(HealthCheckFilter())

# Initialize Flask app
app = Flask(__name__)

# JSON error handlers
@app.errorhandler(404)
def not_found(error):
    """Return JSON for 404 errors instead of HTML."""
    return jsonify({
        'message': 'The requested endpoint does not exist'
    }), 404

@app.errorhandler(405)
def method_not_allowed(error):
    """Return JSON for 405 errors instead of HTML."""
    return jsonify({
        'message': 'The method is not allowed for the requested endpoint'
    }), 405

@app.errorhandler(500)
def internal_error(error):
    """Return JSON for 500 errors instead of HTML."""
    return jsonify({
        'error': 'Internal Server Error',
        'message': 'An unexpected error occurred'
    }), 500

# Global state
config: Config | None = None
streamer: AudioStreamer | PassthroughStreamer | None = None
dlna_client: DLNAClient | None = None
device_manager: DeviceManager | None = None
stream_cache: StreamFormatCache | None = None
rate_limiter = None  # Will be initialized after config is loaded

# Build info from Docker environment variables
BUILD_HASH = os.environ.get('BUILD_HASH', 'dev')
BUILD_DATE = os.environ.get('BUILD_DATE', 'unknown')


def get_local_ip() -> str:
    """Get local IP address of the server."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return "127.0.0.1"


def validate_ip_address(ip: str) -> bool:
    """
    Validate IP address format - only digits and dots.

    Args:
        ip: IP address string to validate

    Returns:
        True if valid IPv4 format, False otherwise
    """
    # Strict regex: only digits and dots, 4 octets
    ip_pattern = re.compile(r'^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$')
    if not ip_pattern.match(ip):
        return False

    # Additional check: each octet must be 0-255
    try:
        octets = ip.split('.')
        for octet in octets:
            if int(octet) > 255:
                return False
        return True
    except ValueError:
        return False


def validate_boolean_string(value: str) -> bool:
    """
    Validate that string is exactly 'true' or 'false'.

    Args:
        value: String to validate

    Returns:
        True if exactly 'true' or 'false', False otherwise
    """
    return value in ('true', 'false')


def validate_stream_url(url: str) -> bool:
    """
    Validate stream URL - must be valid http or https URL.
    Blocks SSRF attempts to localhost, private IPs, and cloud metadata.

    Args:
        url: URL string to validate

    Returns:
        True if valid http/https URL, False otherwise
    """
    try:
        parsed = urlparse(url)
        # Must have scheme and netloc (domain)
        if not parsed.scheme or not parsed.netloc:
            return False
        # Only allow http and https schemes (no file://, ftp://, etc.)
        if parsed.scheme not in ('http', 'https'):
            return False

        # Extract hostname (remove port if present)
        hostname = parsed.hostname
        if not hostname:
            return False

        # Block localhost and loopback addresses (SSRF protection)
        blocked_hosts = {
            'localhost',
            '127.0.0.1',
            '0.0.0.0',
            '::1',  # IPv6 loopback
            '0:0:0:0:0:0:0:1',  # IPv6 loopback expanded
        }
        if hostname.lower() in blocked_hosts:
            return False

        # Block cloud metadata endpoints (AWS, Azure, GCP)
        if hostname.startswith('169.254.'):  # AWS metadata
            return False
        if hostname.startswith('fd00:'):  # IPv6 private
            return False

        # Block private IP ranges (optional - can be relaxed for local streams)
        # For now, we allow private IPs since users may stream from local servers
        # Uncomment to block:
        # if hostname.startswith('10.'):
        #     return False
        # if hostname.startswith('172.') and 16 <= int(hostname.split('.')[1]) <= 31:
        #     return False
        # if hostname.startswith('192.168.'):
        #     return False

        return True
    except Exception:
        return False


def _create_dlna_client_from_device(device_info: dict) -> DLNAClient:
    """Create a DLNAClient instance from device info."""
    return DLNAClient(
        device_host=device_info.get('ip', ''),
        device_port=device_info.get('port', 8080),
        protocol='http',  # TODO: detect from control_url if needed
        control_url=device_info.get('control_url'),
        connection_manager_url=device_info.get('connection_manager_url')
    )


def _detect_format_with_ffprobe(stream_url: str) -> str | None:
    """
    Detect stream format using ffprobe as fallback.

    Args:
        stream_url: URL of the stream

    Returns:
        MIME type string or None
    """
    try:
        logger.info("Attempting format detection with ffprobe")

        # Use ffprobe to analyze stream
        # -analyzeduration and -probesize limit how much data is downloaded
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            '-analyzeduration', '2000000',  # 2 seconds
            '-probesize', '1000000',  # 1MB
            stream_url
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=20
        )

        if result.returncode != 0:
            logger.warning(f"ffprobe failed: {result.stderr}")
            return None

        data = json.loads(result.stdout)

        # Extract codec information
        streams = data.get('streams', [])
        if not streams:
            logger.warning("ffprobe found no streams")
            return None

        # Get audio codec from first audio stream
        audio_stream = next((s for s in streams if s.get('codec_type') == 'audio'), None)
        if not audio_stream:
            logger.warning("ffprobe found no audio streams")
            return None

        codec_name = audio_stream.get('codec_name', '').lower()
        logger.info(f"ffprobe detected codec: {codec_name}")

        # Map codec to MIME type
        codec_to_mime = {
            'aac': 'audio/aac',
            'mp3': 'audio/mpeg',
            'flac': 'audio/flac',
            'vorbis': 'audio/ogg',
            'opus': 'audio/ogg',
            'pcm_s16le': 'audio/wav',
            'pcm_s24le': 'audio/wav',
        }

        mime_type = codec_to_mime.get(codec_name)
        if mime_type:
            logger.info(f"ffprobe mapped codec '{codec_name}' to MIME type: {mime_type}")
            return mime_type
        else:
            logger.warning(f"Unknown codec '{codec_name}', cannot map to MIME type")
            return None

    except subprocess.TimeoutExpired:
        logger.warning("ffprobe timed out")
        return None
    except Exception as e:
        logger.warning(f"ffprobe detection failed: {e}")
        return None


def _detect_stream_format(stream_url: str) -> str | None:
    """
    Detect stream content type using cache, HEAD request, and ffprobe fallback.

    Returns:
        MIME type string or None
    """
    # Check cache first
    if stream_cache:
        cached = stream_cache.get(stream_url)
        if cached:
            return cached.get('mime_type')

    # Try HEAD request
    try:
        timeout = config.stream_detection_timeout if config else 5
        logger.info(f"Detecting stream format for: {stream_url}")
        response = http_client.head(stream_url, timeout=timeout, allow_redirects=True)

        # Log redirect information
        if response.history:
            logger.info(f"Stream redirected {len(response.history)} time(s)")
            for i, resp in enumerate(response.history):
                logger.debug(f"  Redirect {i+1}: {resp.status_code} -> {resp.headers.get('Location', 'unknown')}")
            logger.info(f"Final URL: {response.url}")

        content_type = response.headers.get('Content-Type', '')
        if content_type:
            # Extract just the MIME type (before any semicolon)
            # Add length limit for security
            mime_type = content_type.split(';')[0].strip()[:100]
            logger.info(f"Detected stream Content-Type via HEAD: {mime_type}")

            # Cache the result
            if stream_cache:
                stream_cache.set(stream_url, mime_type, 'head')

            return mime_type
        else:
            logger.warning("Stream did not return Content-Type header in HEAD response")

    except Exception as e:
        logger.warning(f"HEAD request failed: {e}")

    # Fallback to ffprobe
    logger.info("Falling back to ffprobe for format detection")
    mime_type = _detect_format_with_ffprobe(stream_url)

    if mime_type and stream_cache:
        stream_cache.set(stream_url, mime_type, 'ffprobe')

    return mime_type


def _try_auto_select_default_device():
    """
    Try to auto-select default device if configured.

    Called both on startup and after background scan.
    """
    global dlna_client

    if not config or not config.default_device_ip:
        return

    default_ip = config.default_device_ip

    # Check if already selected with correct IP
    current = device_manager.get_current_device()
    if current and current.get('ip') == default_ip:
        logger.info(f"Default device already selected: {current.get('friendly_name', 'Unknown')} ({default_ip})")
        return

    logger.info(f"Auto-selecting default device: {default_ip}")

    # Try to find device in cache
    device_info = device_manager.find_device_in_cache(ip=default_ip)

    # If not in cache, try direct connection
    if not device_info:
        logger.info(f"Default device {default_ip} not in cache, trying direct connection")
        try:
            device_info = SSDPDiscovery.try_direct_connection(default_ip)
        except Exception as e:
            logger.warning(f"Direct connection to {default_ip} failed: {e}")

    if not device_info:
        logger.warning(f"Could not connect to default device {default_ip}")
        return

    # Select the device
    try:
        logger.info(f"Selecting default device: {device_info.get('friendly_name', 'Unknown')} ({default_ip})")

        # Create DLNA client and detect capabilities
        client = _create_dlna_client_from_device(device_info)
        capabilities = client.detect_capabilities()

        # Save device with capabilities
        device_info['capabilities'] = capabilities
        device_manager.select_device(device_info)

        # Update global DLNA client
        dlna_client = client

        logger.info(f"Successfully auto-selected default device: {device_info.get('friendly_name', 'Unknown')}")
    except Exception as e:
        logger.error(f"Failed to auto-select default device: {e}", exc_info=True)


def _precache_default_stream():
    """Pre-cache default stream format if configured."""
    if not config or not config.default_stream_url:
        return

    stream_url = config.default_stream_url
    logger.info(f"Pre-caching stream format for: {stream_url}")

    try:
        # This will cache the result for future /play calls
        stream_format = _detect_stream_format(stream_url)
        if stream_format:
            logger.info(f"Successfully pre-cached stream format: {stream_format}")
        else:
            logger.warning("Could not detect stream format for pre-caching")
    except Exception as e:
        logger.error(f"Failed to pre-cache stream format: {e}")


def _background_device_scan():
    """Background thread to scan for devices on startup."""
    global device_manager

    devices_found_via_callback = []

    def on_device_found(device_info):
        """Callback to add device to cache immediately when found."""
        try:
            logger.info(f"Background scan found device: {device_info.get('friendly_name', 'Unknown')} at {device_info.get('ip')}")

            # Get current cache
            cached = device_manager.get_cached_devices()

            # Add new device if not already in cache
            device_exists = any(d.get('id') == device_info.get('id') for d in cached)
            if not device_exists:
                cached.append(device_info)
                device_manager.update_device_cache(cached)
                devices_found_via_callback.append(device_info)
                logger.info(f"Added device to cache via callback: {device_info.get('friendly_name', 'Unknown')}")
            else:
                logger.debug(f"Device {device_info.get('friendly_name', 'Unknown')} already in cache")
        except Exception as e:
            logger.error(f"Failed to add device to cache in callback: {e}", exc_info=True)

    try:
        timeout = config.device_discovery_timeout if config else 10
        logger.info(f"Starting background device scan ({timeout}s timeout)")
        devices = SSDPDiscovery.discover(timeout=timeout, device_callback=on_device_found)

        logger.info(f"Background scan discovery returned {len(devices)} devices")
        logger.info(f"Callback was invoked for {len(devices_found_via_callback)} devices")

        # Final update with all devices (in case callback failed for some)
        if devices:
            device_manager.update_device_cache(devices)
            logger.info(f"Background scan complete. Final cache update with {len(devices)} devices")

            # Log device names for debugging
            for dev in devices:
                logger.info(f"  - {dev.get('friendly_name', 'Unknown')} ({dev.get('ip')})")
        else:
            logger.warning("Background scan complete. No devices found - this may indicate network issues")

        # Try auto-select default device after scan completes
        _try_auto_select_default_device()

    except Exception as e:
        logger.error(f"Background device scan failed: {e}", exc_info=True)


def initialize():
    """Initialize application components."""
    global config, dlna_client, device_manager, stream_cache, rate_limiter

    config = Config()
    logger.info("Configuration loaded")

    # Configure HTTP client with connection pooling
    http_client.configure(
        pool_connections=config.connection_pool_size,
        pool_maxsize=config.connection_pool_maxsize
    )

    # Initialize rate limiter if enabled
    rate_limiter = init_rate_limiter(app, config)

    # Initialize stream format cache
    stream_cache = StreamFormatCache(
        data_dir=config.data_dir,
        ttl=config.stream_cache_ttl
    )
    logger.info(f"Stream format cache initialized (TTL: {config.stream_cache_ttl}s)")

    # Initialize device manager with data directory
    state_file = os.path.join(config.data_dir, 'state.json')
    device_manager = DeviceManager(state_file=state_file)

    # Restore previously selected device if exists
    saved_device = device_manager.get_current_device()
    if saved_device:
        logger.info(f"Restoring previously selected device: {saved_device.get('friendly_name', 'Unknown')}")
        dlna_client = _create_dlna_client_from_device(saved_device)
    else:
        logger.info("No device selected")

    # Try to auto-select default device if configured (immediate, before background scan)
    _try_auto_select_default_device()

    # Start background tasks (parallel execution for faster startup)
    import threading

    # Background device scan with longer timeout
    scan_thread = threading.Thread(target=_background_device_scan, daemon=True)
    scan_thread.start()

    # Pre-cache default stream format (parallel with device scan)
    if config.default_stream_url:
        precache_thread = threading.Thread(target=_precache_default_stream, daemon=True)
        precache_thread.start()
        logger.info("Started background stream format pre-caching")


@app.route('/', methods=['GET'])
def index():
    """Development console UI."""
    return render_template(
        'dev.html',
        default_stream_url=config.default_stream_url,
        default_device_ip=config.default_device_ip,
        version=__version__,
        build_hash=BUILD_HASH,
        build_date=BUILD_DATE
    )


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'ok',
        'streaming': streamer is not None and streamer.is_running()
    }), 200


@app.route('/devices', methods=['GET'])
def devices():
    """
    Get list of discovered DLNA devices.
    Returns cached results by default, or performs new scan with force_scan=true.

    Query parameters:
    - force_scan: Force new scan (default: false)
    - timeout: Scan timeout in seconds when force_scan=true (default: 5, max: 15)
    """
    try:
        force_scan_param = request.args.get('force_scan', default='false', type=str)

        # Strict validation: only 'true' or 'false' allowed (case-sensitive)
        if not validate_boolean_string(force_scan_param):
            return jsonify({
                'message': f'force_scan must be "true" or "false", got: {force_scan_param}'
            }), 400

        force_scan = force_scan_param == 'true'

        if force_scan:
            timeout = request.args.get('timeout', default=5, type=int)
            timeout = min(timeout, 15)
            logger.info(f"Force scan requested (timeout: {timeout}s)")
            devices_list = SSDPDiscovery.discover(timeout=timeout)
            device_manager.update_device_cache(devices_list)
            cache_age = 0
        else:
            cache_age = device_manager.get_cache_age()
            devices_list = device_manager.get_cached_devices()

        return jsonify({
            'devices': devices_list,
            'count': len(devices_list),
            'cache_age_seconds': cache_age
        }), 200

    except Exception as e:
        logger.error(f"Error getting devices: {e}", exc_info=True)
        return jsonify({
            'error': str(e)
        }), 500


@app.route('/devices/select', methods=['POST'])
@require_api_key(lambda: config)
def device_select():
    """Select a DLNA device by IP address and detect its capabilities."""
    global dlna_client

    try:
        # Get IP from query parameter only
        ip = request.args.get('ip')

        if not ip:
            return jsonify({
                'message': 'ip parameter is required'
            }), 400

        # Strict IP validation: only digits and dots
        if not validate_ip_address(ip):
            return jsonify({
                'message': f'Invalid IP address format: {ip}'
            }), 400

        device_info = None

        # Try to get from current device if IP matches (edge case)
        current = device_manager.get_current_device()
        if current and current.get('ip') == ip:
            device_info = current

        # Try device cache first (fast)
        if not device_info:
            device_info = device_manager.find_device_in_cache(ip=ip)
            if device_info:
                logger.info(f"Found device in cache: {device_info.get('friendly_name', 'Unknown')}")

        if not device_info:
            # Scan for device
            logger.info(f"Scanning for device: {ip}")
            devices = SSDPDiscovery.discover(timeout=5)
            device_manager.update_device_cache(devices)
            for device in devices:
                if device.get('ip') == ip:
                    device_info = device
                    break

            # If still not found, try direct connection
            if not device_info:
                logger.info(f"Device not found in scan, trying direct connection to {ip}")
                device_info = SSDPDiscovery.try_direct_connection(ip)

        if not device_info:
            return jsonify({
                'message': f'Device {ip} not found'
            }), 404

        # Create DLNA client for this device
        client = _create_dlna_client_from_device(device_info)

        # Detect capabilities
        logger.info(f"Detecting capabilities for {device_info.get('friendly_name', 'Unknown')}")
        capabilities = client.detect_capabilities()

        # Save device info with capabilities
        device_info['capabilities'] = capabilities
        device_manager.select_device(device_info)

        # Update global DLNA client
        dlna_client = client

        return jsonify({
            'status': 'selected',
            'device': {
                'id': device_info.get('id'),
                'friendly_name': device_info.get('friendly_name'),
                'manufacturer': device_info.get('manufacturer'),
                'model_name': device_info.get('model_name'),
                'ip': device_info.get('ip'),
                'capabilities': capabilities
            }
        }), 200

    except Exception as e:
        logger.error(f"Error selecting device: {e}", exc_info=True)
        return jsonify({
            'error': str(e)
        }), 500


@app.route('/devices/current', methods=['GET'])
def device_current():
    """Get currently selected device."""
    try:
        device = device_manager.get_current_device()

        if not device:
            return jsonify({
                'device': None,
                'message': 'No device selected'
            }), 200

        return jsonify({
            'device': {
                'id': device.get('id'),
                'friendly_name': device.get('friendly_name'),
                'manufacturer': device.get('manufacturer'),
                'model_name': device.get('model_name'),
                'ip': device.get('ip'),
                'capabilities': device.get('capabilities', {})
            }
        }), 200

    except Exception as e:
        logger.error(f"Error getting current device: {e}", exc_info=True)
        return jsonify({
            'error': str(e)
        }), 500


@app.route('/play', methods=['POST'])
@require_api_key(lambda: config)
def play():
    """Start streaming radio to DLNA device with smart transcoding."""
    global streamer, dlna_client

    try:
        # Get stream URL from query parameter or use default
        stream_url = request.args.get('streamUrl', config.default_stream_url)

        if not stream_url:
            return jsonify({
                'message': 'No stream URL provided and no default configured'
            }), 400

        # Validate stream URL
        if not validate_stream_url(stream_url):
            return jsonify({
                'message': f'Invalid stream URL format: {stream_url}'
            }), 400

        # Use current device from device_manager
        device_info = device_manager.get_current_device()

        if not device_info:
            return jsonify({
                'message': 'No device selected. Please use /devices/select first.'
            }), 400

        # Create client from current device (with capabilities loaded from state)
        active_client = _create_dlna_client_from_device(device_info)
        # Load capabilities from saved device info
        if device_info.get('capabilities'):
            active_client.capabilities = device_info.get('capabilities')

        # Stop existing stream if running
        if streamer and streamer.is_running():
            logger.info("Stopping existing stream")
            streamer.stop()

        # Stop DLNA device to ensure clean state (only if playing)
        active_client.stop_if_playing()

        # Detect stream format
        stream_format = _detect_stream_format(stream_url)
        needs_transcoding = True
        playback_url = stream_url

        # Check if device can play the format natively
        if stream_format:
            logger.info(f"Stream format detected: {stream_format}")
            if active_client.capabilities:
                logger.info(f"Device capabilities available: MP3={active_client.capabilities.get('supports_mp3')}, "
                           f"AAC={active_client.capabilities.get('supports_aac')}, "
                           f"FLAC={active_client.capabilities.get('supports_flac')}")

                can_play_native = active_client.can_play_format(stream_format)

                # Check if stream URL is HTTPS - many DLNA devices don't support HTTPS
                is_https = stream_url.lower().startswith('https://')

                if can_play_native and not is_https:
                    logger.info(f"Device supports {stream_format} natively - using passthrough mode (no transcoding)")
                    needs_transcoding = False
                elif can_play_native and is_https:
                    logger.warning(f"Device supports {stream_format} but stream is HTTPS - transcoding to HTTP for compatibility")
                    logger.warning("Many DLNA devices cannot handle HTTPS streams (no SSL/TLS support)")
                    needs_transcoding = True
                else:
                    logger.warning(f"Device does not support {stream_format} - transcoding to MP3 required")
            else:
                logger.warning("Device capabilities not available - defaulting to transcoding")
        else:
            logger.warning("Could not detect stream format - defaulting to transcoding for compatibility")

        # Create appropriate streamer
        if needs_transcoding:
            # Use FFmpeg transcoding with configured parameters
            streamer = AudioStreamer(
                stream_url=stream_url,
                port=config.stream_port,
                bitrate=config.mp3_bitrate,
                chunk_size=config.ffmpeg_chunk_size,
                max_stderr_lines=config.ffmpeg_max_stderr_lines,
                protocol_whitelist=config.ffmpeg_protocol_whitelist
            )
            streamer.start()

            # Wait for HTTP server to be ready before sending to DLNA device
            if not streamer.wait_until_ready(timeout=config.ffmpeg_startup_timeout):
                streamer.stop()
                return jsonify({
                    'error': 'Streaming server failed to start'
                }), 500

            # Get transcoded stream URL
            if config.stream_public_url:
                playback_url = f"{config.stream_public_url}/stream.mp3"
                logger.info(f"Using configured public URL: {playback_url}")
            else:
                local_ip = get_local_ip()
                playback_url = streamer.get_stream_url(local_ip)
                logger.info(f"Auto-detected stream URL: {playback_url}")
        else:
            # Use passthrough - send original URL directly
            streamer = PassthroughStreamer(stream_url)
            streamer.start()
            playback_url = stream_url

        # Send to DLNA device
        success = active_client.play_url(playback_url)

        if success:
            return jsonify({
                'status': 'playing',
                'stream_url': stream_url,
                'playback_url': playback_url,
                'transcoding': needs_transcoding,
                'format': stream_format
            }), 200
        else:
            streamer.stop()
            return jsonify({
                'error': 'Failed to start playback on DLNA device'
            }), 500

    except Exception as e:
        logger.error(f"Error starting playback: {e}", exc_info=True)
        if streamer:
            streamer.stop()
        return jsonify({
            'error': str(e)
        }), 500


@app.route('/stop', methods=['POST'])
@require_api_key(lambda: config)
def stop():
    """Stop streaming."""
    global streamer

    try:
        # Always stop DLNA playback (force cleanup)
        # This ensures DLNA is stopped even if it's in TRANSITIONING or other states
        try:
            dlna_client.stop()
        except Exception as e:
            logger.debug(f"DLNA stop command failed (may already be stopped): {e}")

        # Stop streamer
        if streamer:
            streamer.stop()
            streamer = None

        return jsonify({
            'status': 'stopped'
        }), 200

    except Exception as e:
        logger.error(f"Error stopping playback: {e}", exc_info=True)
        return jsonify({
            'error': str(e)
        }), 500


@app.route('/status', methods=['GET'])
def status():
    """Get current playback status."""
    try:
        is_streaming = streamer is not None and streamer.is_running()

        dlna_info = None
        if dlna_client:
            dlna_info = dlna_client.get_transport_info(retries=2)

            # If DLNA query failed but streamer is running, provide fallback info
            if dlna_info is None and is_streaming:
                logger.debug("DLNA query failed but streamer is running - using fallback status")
                dlna_info = {
                    'state': 'PLAYING',
                    'status': 'UNKNOWN'
                }

        # Get current device info
        current_device = device_manager.get_current_device()
        device_info = None
        if current_device:
            device_info = {
                'friendly_name': current_device.get('friendly_name'),
                'ip': current_device.get('ip')
            }

        return jsonify({
            'streaming': is_streaming,
            'dlna': dlna_info,
            'current_device': device_info
        }), 200

    except Exception as e:
        logger.error(f"Error getting status: {e}", exc_info=True)
        return jsonify({
            'error': str(e)
        }), 500


@app.route('/streams/cached', methods=['GET'])
def streams_cached():
    """Get cached stream formats for GUI tags."""
    try:
        if not stream_cache:
            return jsonify({'streams': [], 'count': 0}), 200

        streams = []
        for key, entry in stream_cache.cache.items():
            streams.append({
                'url': entry.get('url'),
                'mime_type': entry.get('mime_type'),
                'detection_method': entry.get('detection_method')
            })

        return jsonify({
            'streams': streams,
            'count': len(streams)
        }), 200

    except Exception as e:
        logger.error(f"Error getting cached streams: {e}", exc_info=True)
        return jsonify({
            'error': str(e)
        }), 500


# Initialize application on module import (for gunicorn)
initialize()
logger.info("DLNA Radio Streamer initialized")


def main():
    """Main entry point for direct execution (development only)."""
    host = config.server_host
    port = config.server_port

    logger.info(f"Starting DLNA Radio Streamer on {host}:{port}")
    app.run(host=host, port=port, debug=False)


if __name__ == '__main__':
    main()
