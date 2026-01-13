"""FFmpeg-based audio streaming with AAC to MP3 transcoding."""

import subprocess
import threading
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from typing import Optional
import time
import socket

logger = logging.getLogger(__name__)


class ReuseAddrHTTPServer(ThreadingMixIn, HTTPServer):
    """HTTPServer with SO_REUSEADDR to prevent 'Address already in use' errors."""
    allow_reuse_address = True
    daemon_threads = True


class StreamHandler(BaseHTTPRequestHandler):
    """HTTP handler for serving transcoded audio stream."""

    ffmpeg_process: Optional[subprocess.Popen] = None

    def do_GET(self):
        """Handle GET request for audio stream."""
        if self.path == '/stream.mp3':
            self.send_response(200)
            self.send_header('Content-Type', 'audio/mpeg')
            self.send_header('Connection', 'close')
            self.send_header('Accept-Ranges', 'none')
            self.end_headers()

            try:
                while self.ffmpeg_process and self.ffmpeg_process.poll() is None:
                    chunk = self.ffmpeg_process.stdout.read(8192)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
            except (BrokenPipeError, ConnectionResetError):
                logger.info("Client disconnected from stream")
            except Exception as e:
                logger.error(f"Error streaming data: {e}")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        """Override to use custom logger."""
        logger.debug(f"{self.address_string()} - {format % args}")


class AudioStreamer:
    """Manages FFmpeg transcoding and HTTP streaming."""

    def __init__(self, stream_url: str, port: int, bitrate: str = "128k"):
        self.stream_url = stream_url
        self.port = port
        self.bitrate = bitrate
        self.ffmpeg_process: Optional[subprocess.Popen] = None
        self.http_server: Optional[HTTPServer] = None
        self.server_thread: Optional[threading.Thread] = None
        self.running = False

    def start(self):
        """Start FFmpeg transcoding and HTTP server."""
        if self.running:
            logger.warning("Streamer already running")
            return

        logger.info(f"Starting transcoding from {self.stream_url}")

        # Start FFmpeg process
        ffmpeg_cmd = [
            'ffmpeg',
            '-i', self.stream_url,
            '-vn',  # No video
            '-acodec', 'libmp3lame',
            '-b:a', self.bitrate,
            '-ar', '44100',
            '-ac', '2',
            '-f', 'mp3',
            '-',  # Output to stdout
        ]

        try:
            self.ffmpeg_process = subprocess.Popen(
                ffmpeg_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=8192
            )

            # Assign ffmpeg process to handler class
            StreamHandler.ffmpeg_process = self.ffmpeg_process

            # Start HTTP server in separate thread with address reuse enabled
            self.http_server = ReuseAddrHTTPServer(('0.0.0.0', self.port), StreamHandler)
            self.server_thread = threading.Thread(
                target=self.http_server.serve_forever,
                daemon=True
            )
            self.server_thread.start()

            self.running = True
            logger.info(f"Streaming server started on port {self.port}")

            # Start FFmpeg error logger thread
            threading.Thread(
                target=self._log_ffmpeg_errors,
                daemon=True
            ).start()

        except Exception as e:
            logger.error(f"Failed to start streamer: {e}")
            self.stop()
            raise

    def _log_ffmpeg_errors(self):
        """Log FFmpeg stderr output."""
        if self.ffmpeg_process and self.ffmpeg_process.stderr:
            for line in iter(self.ffmpeg_process.stderr.readline, b''):
                if line:
                    logger.debug(f"FFmpeg: {line.decode('utf-8').strip()}")

    def stop(self):
        """Stop FFmpeg and HTTP server."""
        if not self.running:
            return

        logger.info("Stopping streamer")

        # Stop HTTP server
        if self.http_server:
            try:
                self.http_server.shutdown()
                self.http_server.server_close()  # Close socket to free port
            except Exception as e:
                logger.debug(f"Error stopping HTTP server: {e}")
            finally:
                self.http_server = None

        # Stop FFmpeg
        if self.ffmpeg_process:
            self.ffmpeg_process.terminate()
            try:
                self.ffmpeg_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.ffmpeg_process.kill()
            self.ffmpeg_process = None

        StreamHandler.ffmpeg_process = None
        self.running = False
        logger.info("Streamer stopped")

    def is_running(self) -> bool:
        """Check if streamer is running."""
        # Check if FFmpeg process is actually running
        if self.ffmpeg_process and self.ffmpeg_process.poll() is None:
            return True

        # FFmpeg stopped - cleanup if needed
        if self.running:
            logger.warning("FFmpeg process ended unexpectedly, cleaning up")
            self.running = False
            if self.http_server:
                try:
                    self.http_server.shutdown()
                    self.http_server.server_close()
                except Exception as e:
                    logger.debug(f"Error during auto-cleanup: {e}")
                finally:
                    self.http_server = None

        return False

    def get_stream_url(self, host: str) -> str:
        """Get the URL to access the transcoded stream."""
        return f"http://{host}:{self.port}/stream.mp3"
