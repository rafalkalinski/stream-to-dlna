"""Main Flask application for DLNA Radio Streamer."""

import logging
import sys
import socket
import requests
from flask import Flask, request, jsonify, render_template
from app.config import Config
from app.dlna_client import DLNAClient
from app.streamer import AudioStreamer, PassthroughStreamer
from app.discovery import SSDPDiscovery
from app.device_manager import DeviceManager
from typing import Optional, Union

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

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
        'error': 'Not Found',
        'message': 'The requested endpoint does not exist'
    }), 404

@app.errorhandler(405)
def method_not_allowed(error):
    """Return JSON for 405 errors instead of HTML."""
    return jsonify({
        'error': 'Method Not Allowed',
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
config: Optional[Config] = None
streamer: Optional[Union[AudioStreamer, PassthroughStreamer]] = None
dlna_client: Optional[DLNAClient] = None
device_manager: Optional[DeviceManager] = None


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


def _create_dlna_client_from_device(device_info: dict) -> DLNAClient:
    """Create a DLNAClient instance from device info."""
    return DLNAClient(
        device_host=device_info.get('ip', ''),
        device_port=device_info.get('port', 8080),
        protocol='http',  # TODO: detect from control_url if needed
        control_url=device_info.get('control_url'),
        connection_manager_url=device_info.get('connection_manager_url')
    )


def _detect_stream_format(stream_url: str) -> Optional[str]:
    """
    Detect stream content type by making a HEAD request.

    Returns:
        MIME type string or None
    """
    try:
        response = requests.head(stream_url, timeout=5, allow_redirects=True)
        content_type = response.headers.get('Content-Type', '')
        if content_type:
            # Extract just the MIME type (before any semicolon)
            mime_type = content_type.split(';')[0].strip()
            logger.info(f"Detected stream format: {mime_type}")
            return mime_type
    except Exception as e:
        logger.warning(f"Could not detect stream format: {e}")

    return None


def _background_device_scan():
    """Background thread to scan for devices on startup."""
    try:
        logger.info("Starting background device scan")
        devices = SSDPDiscovery.discover(timeout=10)
        device_manager.update_device_cache(devices)
        logger.info(f"Background scan complete. Found {len(devices)} devices")
    except Exception as e:
        logger.error(f"Background device scan failed: {e}", exc_info=True)


def initialize():
    """Initialize application components."""
    global config, dlna_client, device_manager

    config = Config()
    logger.info("Configuration loaded")

    # Initialize device manager
    device_manager = DeviceManager()

    # Restore previously selected device if exists
    saved_device = device_manager.get_current_device()
    if saved_device:
        logger.info(f"Restoring previously selected device: {saved_device.get('friendly_name', 'Unknown')}")
        dlna_client = _create_dlna_client_from_device(saved_device)
    else:
        logger.info("No device selected. Use /devices/select to choose a device.")

    # Start background device scan
    import threading
    scan_thread = threading.Thread(target=_background_device_scan, daemon=True)
    scan_thread.start()


@app.route('/', methods=['GET'])
def index():
    """Development console UI."""
    return render_template('dev.html', default_stream_url=config.default_stream_url)


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
        force_scan = request.args.get('force_scan', default='false', type=str).lower() == 'true'

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
                'error': f'Device {ip} not found'
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

        # Handle device_id override or use current device
        device_id = request.args.get('device_id')
        device_info = None

        if device_id:
            logger.info(f"Using device override: {device_id}")
            # Try to find device info
            device_info = device_manager.get_device_by_id(device_id)

            if not device_info:
                # Scan for device
                logger.info(f"Scanning for device {device_id}")
                devices = SSDPDiscovery.discover(timeout=5)
                for device in devices:
                    if device.get('id') == device_id:
                        device_info = device
                        break

            if not device_info:
                return jsonify({
                    'error': f'Device {device_id} not found'
                }), 404

            # Create temporary client for this device
            active_client = _create_dlna_client_from_device(device_info)
            # Ensure capabilities are detected
            if not device_info.get('capabilities'):
                device_info['capabilities'] = active_client.detect_capabilities()
        else:
            # No device_id override - use current device from device_manager
            device_info = device_manager.get_current_device()

            if not device_info:
                return jsonify({
                    'message': 'No device selected. Please use /device/select first.'
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
        if stream_format and active_client.capabilities:
            can_play_native = active_client.can_play_format(stream_format)
            if can_play_native:
                logger.info(f"Device supports {stream_format} natively - using passthrough mode")
                needs_transcoding = False
            else:
                logger.info(f"Device does not support {stream_format} - transcoding required")
        else:
            logger.info("Could not detect format or capabilities - defaulting to transcoding")

        # Create appropriate streamer
        if needs_transcoding:
            # Use FFmpeg transcoding
            streamer = AudioStreamer(
                stream_url=stream_url,
                port=config.stream_port,
                bitrate=config.mp3_bitrate
            )
            streamer.start()

            # Wait for HTTP server to be ready before sending to DLNA device
            if not streamer.wait_until_ready(timeout=10):
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
            response_data = {
                'status': 'playing',
                'stream_url': stream_url,
                'playback_url': playback_url,
                'transcoding': needs_transcoding,
                'format': stream_format
            }

            if device_id:
                response_data['device_id'] = device_id

            return jsonify(response_data), 200
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
            dlna_info = dlna_client.get_transport_info()

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
