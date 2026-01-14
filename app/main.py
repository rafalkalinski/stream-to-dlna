"""Main Flask application for DLNA Radio Streamer."""

import logging
import sys
import socket
import requests
from flask import Flask, request, jsonify
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
        device_host=device_info.get('host', ''),
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


def initialize():
    """Initialize application components."""
    global config, dlna_client, device_manager

    config = Config()
    logger.info("Configuration loaded")

    # Initialize device manager
    device_manager = DeviceManager()

    # Initialize default DLNA client from config (fallback)
    dlna_client = DLNAClient(
        device_host=config.dlna_host,
        device_port=config.dlna_port,
        protocol=config.dlna_protocol
    )
    logger.info(f"Default DLNA client initialized for device at {config.dlna_protocol}://{config.dlna_host}:{config.dlna_port}")

    # If a device was previously selected, use that instead
    saved_device = device_manager.get_current_device()
    if saved_device:
        logger.info(f"Restoring previously selected device: {saved_device.get('friendly_name', 'Unknown')}")
        dlna_client = _create_dlna_client_from_device(saved_device)


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'ok',
        'streaming': streamer is not None and streamer.is_running()
    }), 200


@app.route('/scan', methods=['GET'])
def scan():
    """Scan network for DLNA devices."""
    try:
        timeout = request.args.get('timeout', default=5, type=int)
        timeout = min(timeout, 15)  # Max 15 seconds

        logger.info(f"Starting DLNA device scan (timeout: {timeout}s)")
        devices = SSDPDiscovery.discover(timeout=timeout)

        return jsonify({
            'devices': devices,
            'count': len(devices)
        }), 200

    except Exception as e:
        logger.error(f"Error during device scan: {e}", exc_info=True)
        return jsonify({
            'error': str(e)
        }), 500


@app.route('/device/select', methods=['POST'])
def device_select():
    """Select a DLNA device and detect its capabilities. Can select by device_id, host, or hostname."""
    global dlna_client

    try:
        # Get device identifier from query parameter or JSON body
        device_id = request.args.get('device_id') or (request.json.get('device_id') if request.is_json else None)
        host = request.args.get('host') or (request.json.get('host') if request.is_json else None)

        if not device_id and not host:
            return jsonify({
                'error': 'Either device_id or host parameter is required'
            }), 400

        # Option 1: If device_id is provided directly as device info (from /scan)
        # First, try to find it in a recent scan or accept full device info in body
        device_info = None

        if request.is_json and 'device_info' in request.json:
            # Full device info provided
            device_info = request.json['device_info']
        else:
            # Try to get from current device if ID or host matches (edge case)
            current = device_manager.get_current_device()
            if current:
                if device_id and current.get('id') == device_id:
                    device_info = current
                elif host and current.get('host') == host:
                    device_info = current

            if not device_info:
                # Need to do a quick scan to find the device
                identifier = device_id or host
                logger.info(f"Scanning for device: {identifier}")
                devices = SSDPDiscovery.discover(timeout=5)
                for device in devices:
                    if device_id and device.get('id') == device_id:
                        device_info = device
                        break
                    elif host and device.get('host') == host:
                        device_info = device
                        break

        if not device_info:
            identifier = device_id or host
            return jsonify({
                'error': f'Device {identifier} not found'
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
                'host': device_info.get('host'),
                'capabilities': capabilities
            }
        }), 200

    except Exception as e:
        logger.error(f"Error selecting device: {e}", exc_info=True)
        return jsonify({
            'error': str(e)
        }), 500


@app.route('/device/current', methods=['GET'])
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
                'host': device.get('host'),
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
                'error': 'No stream URL provided and no default configured'
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
                    'error': 'No device selected. Please use /device/select first.'
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
                'id': current_device.get('id'),
                'friendly_name': current_device.get('friendly_name'),
                'manufacturer': current_device.get('manufacturer'),
                'model_name': current_device.get('model_name'),
                'host': current_device.get('host')
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
