"""Main Flask application for DLNA Radio Streamer."""

import logging
import sys
import socket
from flask import Flask, request, jsonify
from app.config import Config
from app.dlna_client import DLNAClient
from app.streamer import AudioStreamer
from typing import Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Global state
config: Optional[Config] = None
streamer: Optional[AudioStreamer] = None
dlna_client: Optional[DLNAClient] = None


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


def initialize():
    """Initialize application components."""
    global config, dlna_client

    config = Config()
    logger.info("Configuration loaded")

    dlna_client = DLNAClient(
        device_host=config.dlna_host,
        device_port=config.dlna_port,
        protocol=config.dlna_protocol
    )
    logger.info(f"DLNA client initialized for device at {config.dlna_protocol}://{config.dlna_host}:{config.dlna_port}")


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'ok',
        'streaming': streamer is not None and streamer.is_running()
    }), 200


@app.route('/play', methods=['POST'])
def play():
    """Start streaming radio to DLNA device."""
    global streamer

    try:
        # Get stream URL from query parameter or use default
        stream_url = request.args.get('streamUrl', config.default_stream_url)

        if not stream_url:
            return jsonify({
                'error': 'No stream URL provided and no default configured'
            }), 400

        # Stop existing stream if running
        if streamer and streamer.is_running():
            logger.info("Stopping existing stream")
            streamer.stop()

        # Create new streamer
        streamer = AudioStreamer(
            stream_url=stream_url,
            port=config.stream_port,
            bitrate=config.mp3_bitrate
        )

        # Start streaming
        streamer.start()

        # Get local IP and construct stream URL
        local_ip = get_local_ip()
        transcoded_url = streamer.get_stream_url(local_ip)

        logger.info(f"Transcoded stream available at {transcoded_url}")

        # Send to DLNA device
        success = dlna_client.play_url(transcoded_url)

        if success:
            return jsonify({
                'status': 'playing',
                'stream_url': stream_url,
                'transcoded_url': transcoded_url
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
def stop():
    """Stop streaming."""
    global streamer

    try:
        # Stop DLNA playback
        dlna_client.stop()

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

        return jsonify({
            'streaming': is_streaming,
            'dlna': dlna_info
        }), 200

    except Exception as e:
        logger.error(f"Error getting status: {e}", exc_info=True)
        return jsonify({
            'error': str(e)
        }), 500


def main():
    """Main entry point."""
    initialize()

    host = config.server_host
    port = config.server_port

    logger.info(f"Starting DLNA Radio Streamer on {host}:{port}")
    app.run(host=host, port=port, debug=False)


if __name__ == '__main__':
    main()
