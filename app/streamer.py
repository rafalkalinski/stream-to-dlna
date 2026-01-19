"""Audio streaming with optional FFmpeg transcoding or passthrough."""

import logging
import os
import signal
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn

logger = logging.getLogger(__name__)


class PassthroughStreamer:
    """
    Passthrough streamer - returns original stream URL without transcoding.
    Used when DLNA device supports the native stream format.
    """

    def __init__(self, stream_url: str):
        self.stream_url = stream_url
        self.running = False

    def start(self):
        """Mark as running (no actual process to start)."""
        self.running = True
        logger.info(f"Passthrough mode enabled for {self.stream_url}")

    def stop(self):
        """Mark as stopped."""
        self.running = False
        logger.info("Passthrough streamer stopped")

    def is_running(self) -> bool:
        """Check if streamer is active."""
        return self.running

    def get_stream_url(self, host: str = None) -> str:
        """Return the original stream URL."""
        return self.stream_url


class ReuseAddrHTTPServer(ThreadingMixIn, HTTPServer):
    """HTTPServer with SO_REUSEADDR to prevent 'Address already in use' errors."""
    allow_reuse_address = True
    daemon_threads = True


class StreamHandler(BaseHTTPRequestHandler):
    """HTTP handler for serving transcoded audio stream."""

    ffmpeg_process: subprocess.Popen | None = None
    chunk_size: int = 8192  # Default chunk size

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
                    chunk = self.ffmpeg_process.stdout.read(self.chunk_size)
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
    """Manages FFmpeg transcoding and HTTP streaming with PID tracking."""

    PID_FILE = "/tmp/stream-to-dlna-ffmpeg.pid"

    def __init__(self, stream_url: str, port: int, bitrate: str = "128k",
                 chunk_size: int = 8192, max_stderr_lines: int = 1000,
                 protocol_whitelist: str = "http,https,tcp,tls",
                 on_crash_callback: callable = None):
        self.stream_url = stream_url
        self.port = port
        self.bitrate = bitrate
        self.chunk_size = chunk_size
        self.max_stderr_lines = max_stderr_lines
        self.protocol_whitelist = protocol_whitelist
        self.on_crash_callback = on_crash_callback
        self.ffmpeg_process: subprocess.Popen | None = None
        self.http_server: HTTPServer | None = None
        self.server_thread: threading.Thread | None = None
        self.running = False
        self.stderr_line_count = 0  # Track stderr lines to prevent memory leak
        self.last_stderr_lines = []  # Store last N lines for crash debugging
        self.max_stored_stderr = 20  # Keep last 20 lines

    @staticmethod
    def _cleanup_orphaned_ffmpeg():
        """Clean up any orphaned FFmpeg processes from previous runs."""
        if not os.path.exists(AudioStreamer.PID_FILE):
            return

        try:
            with open(AudioStreamer.PID_FILE, 'r') as f:
                old_pid = int(f.read().strip())

            # Check if process is still running
            try:
                os.kill(old_pid, 0)  # Signal 0 just checks if process exists
                logger.warning(f"Found orphaned FFmpeg process (PID {old_pid}), terminating...")
                os.kill(old_pid, signal.SIGTERM)
                # Give it time to terminate gracefully
                import time
                time.sleep(1)
                # Check if still alive and force kill
                try:
                    os.kill(old_pid, 0)
                    logger.warning(f"FFmpeg process {old_pid} didn't terminate, force killing...")
                    os.kill(old_pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass  # Process terminated successfully
            except ProcessLookupError:
                # Process doesn't exist anymore - just cleanup PID file
                logger.debug(f"Old PID {old_pid} in PID file but process doesn't exist")

            os.remove(AudioStreamer.PID_FILE)
        except Exception as e:
            logger.warning(f"Error cleaning up orphaned FFmpeg: {e}")
            # Try to remove PID file anyway
            try:
                os.remove(AudioStreamer.PID_FILE)
            except:
                pass

    @staticmethod
    def _save_pid(pid: int):
        """Save FFmpeg PID to file for tracking."""
        try:
            with open(AudioStreamer.PID_FILE, 'w') as f:
                f.write(str(pid))
            logger.debug(f"Saved FFmpeg PID {pid} to {AudioStreamer.PID_FILE}")
        except Exception as e:
            logger.warning(f"Failed to save FFmpeg PID: {e}")

    @staticmethod
    def _remove_pid_file():
        """Remove PID file."""
        try:
            if os.path.exists(AudioStreamer.PID_FILE):
                os.remove(AudioStreamer.PID_FILE)
                logger.debug(f"Removed PID file {AudioStreamer.PID_FILE}")
        except Exception as e:
            logger.warning(f"Failed to remove PID file: {e}")

    def start(self):
        """Start FFmpeg transcoding and HTTP server."""
        if self.running:
            logger.warning("Streamer already running")
            return

        # Cleanup any orphaned FFmpeg processes from previous crashes
        self._cleanup_orphaned_ffmpeg()

        logger.info(f"Starting transcoding from {self.stream_url}")

        # Start FFmpeg process with protocol whitelist for security
        ffmpeg_cmd = [
            'ffmpeg',
            '-protocol_whitelist', self.protocol_whitelist,
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

            # Save PID for tracking
            self._save_pid(self.ffmpeg_process.pid)

            # Assign ffmpeg process and chunk size to handler class
            StreamHandler.ffmpeg_process = self.ffmpeg_process
            StreamHandler.chunk_size = self.chunk_size

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
        """Log FFmpeg stderr output with buffer limit to prevent memory leak."""
        if self.ffmpeg_process and self.ffmpeg_process.stderr:
            for line in iter(self.ffmpeg_process.stderr.readline, b''):
                if line:
                    line_text = line.decode('utf-8', errors='replace').strip()
                    self.stderr_line_count += 1

                    # Store last N lines for crash debugging
                    self.last_stderr_lines.append(line_text)
                    if len(self.last_stderr_lines) > self.max_stored_stderr:
                        self.last_stderr_lines.pop(0)

                    if self.stderr_line_count <= self.max_stderr_lines:
                        logger.debug(f"FFmpeg: {line_text}")
                    elif self.stderr_line_count == self.max_stderr_lines + 1:
                        logger.warning(f"FFmpeg stderr buffer limit ({self.max_stderr_lines} lines) reached, suppressing further output")
                    # Continue reading to prevent buffer blocking but don't log

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

        # Remove PID file
        self._remove_pid_file()

        self.running = False
        logger.info("Streamer stopped")

    def is_running(self) -> bool:
        """Check if streamer is running."""
        # Check if FFmpeg process is actually running
        if self.ffmpeg_process and self.ffmpeg_process.poll() is None:
            return True

        # FFmpeg stopped - cleanup if needed
        if self.running:
            exit_code = self.ffmpeg_process.returncode if self.ffmpeg_process else None
            logger.warning(f"FFmpeg process ended unexpectedly (exit code: {exit_code}), cleaning up")

            # Log last stderr lines for debugging
            if self.last_stderr_lines:
                logger.warning("Last FFmpeg output:")
                for line in self.last_stderr_lines[-10:]:  # Last 10 lines
                    logger.warning(f"  {line}")

            self.running = False
            if self.http_server:
                try:
                    self.http_server.shutdown()
                    self.http_server.server_close()
                except Exception as e:
                    logger.debug(f"Error during auto-cleanup: {e}")
                finally:
                    self.http_server = None

            # Notify about crash via callback
            if self.on_crash_callback:
                try:
                    self.on_crash_callback()
                except Exception as e:
                    logger.debug(f"Error in crash callback: {e}")

        return False

    def get_stream_url(self, host: str) -> str:
        """Get the URL to access the transcoded stream."""
        return f"http://{host}:{self.port}/stream.mp3"

    def wait_until_ready(self, timeout: int = 10) -> bool:
        """
        Wait until HTTP server is ready to serve requests.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            True if ready, False if timeout
        """
        import socket
        import time

        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # Try to connect to the HTTP server
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                sock.connect(('127.0.0.1', self.port))
                sock.close()
                logger.info("Streaming server is ready")
                return True
            except (OSError, ConnectionRefusedError):
                time.sleep(0.2)

        logger.warning(f"Streaming server not ready after {timeout}s")
        return False
