"""Unit tests for StreamHandler HTTP server."""

import io
from http.server import BaseHTTPRequestHandler
from unittest.mock import MagicMock, patch
import pytest

from app.streamer import StreamHandler, ReuseAddrHTTPServer


class FakeRequest:
    """Minimal fake socket for BaseHTTPRequestHandler."""
    def __init__(self, raw_request: bytes):
        self._data = io.BytesIO(raw_request)
        self.sent = io.BytesIO()

    def makefile(self, mode, *args, **kwargs):
        if 'r' in mode:
            return io.BufferedReader(self._data)
        return self.sent

    def sendall(self, data):
        self.sent.write(data)


def make_handler(method: str, path: str) -> tuple[StreamHandler, FakeRequest]:
    """Create a StreamHandler for a fake request and return handler + fake socket."""
    raw = f"{method} {path} HTTP/1.1\r\nHost: localhost\r\n\r\n".encode()
    fake_req = FakeRequest(raw)

    # Suppress log output
    with patch.object(StreamHandler, 'log_message', lambda *a: None):
        handler = StreamHandler.__new__(StreamHandler)
        handler.request = fake_req
        handler.client_address = ('127.0.0.1', 12345)
        handler.server = MagicMock()
        handler.rfile = io.BufferedReader(io.BytesIO(raw))
        handler.wfile = fake_req.sent
        handler.ffmpeg_process = None

        BaseHTTPRequestHandler.__init__(handler, fake_req, ('127.0.0.1', 12345), MagicMock())

    return handler, fake_req


class TestStreamHandlerHead:
    """Tests for StreamHandler HEAD request handling."""

    def test_head_stream_returns_200(self):
        handler, sock = make_handler('HEAD', '/stream.mp3')
        response = sock.sent.getvalue().decode()
        assert '200 OK' in response

    def test_head_unknown_path_returns_404(self):
        handler, sock = make_handler('HEAD', '/other')
        response = sock.sent.getvalue().decode()
        assert '404' in response

    def test_head_includes_content_type(self):
        handler, sock = make_handler('HEAD', '/stream.mp3')
        response = sock.sent.getvalue().decode()
        assert 'audio/mpeg' in response

    def test_head_includes_transfer_mode_header(self):
        handler, sock = make_handler('HEAD', '/stream.mp3')
        response = sock.sent.getvalue().decode()
        assert 'transferMode.dlna.org' in response
        assert 'Streaming' in response

    def test_head_includes_content_features_header(self):
        handler, sock = make_handler('HEAD', '/stream.mp3')
        response = sock.sent.getvalue().decode()
        assert 'contentFeatures.dlna.org' in response
        assert 'DLNA.ORG_PN=MP3' in response

    def test_get_stream_includes_dlna_headers(self):
        """GET /stream.mp3 should include the same DLNA headers as HEAD."""
        handler, sock = make_handler('GET', '/stream.mp3')
        response = sock.sent.getvalue().decode()
        assert '200 OK' in response
        assert 'transferMode.dlna.org' in response
        assert 'contentFeatures.dlna.org' in response
