"""Unit tests for DLNAClient."""

import pytest
from unittest.mock import Mock, patch, MagicMock

from app.dlna_client import DLNAClient


class TestDLNAClientExceptionHandling:
    """Test exception handling in SOAP requests."""

    @pytest.fixture
    def client(self):
        """Create a DLNAClient instance."""
        return DLNAClient(
            device_host="192.168.1.100",
            device_port=55000
        )

    def test_send_soap_request_handles_timeout(self, client):
        """SOAP request should handle timeout exceptions gracefully."""
        from requests.exceptions import ReadTimeout

        with patch('app.dlna_client.http_client') as mock_http:
            mock_http.post.side_effect = ReadTimeout("Connection timeout")

            result = client._send_soap_request('Play')

            assert result is None

    def test_send_soap_request_handles_connection_error(self, client):
        """SOAP request should handle connection errors gracefully."""
        from requests.exceptions import ConnectionError

        with patch('app.dlna_client.http_client') as mock_http:
            mock_http.post.side_effect = ConnectionError("Connection refused")

            result = client._send_soap_request('Stop')

            assert result is None

    def test_send_soap_request_handles_generic_exception(self, client):
        """SOAP request should handle any exception gracefully."""
        with patch('app.dlna_client.http_client') as mock_http:
            mock_http.post.side_effect = RuntimeError("Unexpected error")

            result = client._send_soap_request('GetTransportInfo')

            assert result is None

    def test_send_soap_request_success(self, client):
        """SOAP request should return response text on success."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '<response>OK</response>'

        with patch('app.dlna_client.http_client') as mock_http:
            mock_http.post.return_value = mock_response

            result = client._send_soap_request('Play')

            assert result == '<response>OK</response>'

    def test_send_soap_request_handles_http_error(self, client):
        """SOAP request should return None on HTTP error status."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = '<error>Internal Server Error</error>'

        with patch('app.dlna_client.http_client') as mock_http:
            mock_http.post.return_value = mock_response

            result = client._send_soap_request('Play')

            assert result is None


class TestCapabilitiesDetection:
    """Test device capabilities detection."""

    @pytest.fixture
    def client(self):
        """Create a DLNAClient instance."""
        return DLNAClient(
            device_host="192.168.1.100",
            device_port=55000
        )

    def test_detect_capabilities_parses_mp3_support(self, client):
        """Should detect MP3 support from protocol info."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '''<?xml version="1.0"?>
        <root>
            <Sink>http-get:*:audio/mpeg:DLNA.ORG_PN=MP3</Sink>
        </root>'''

        with patch('app.dlna_client.http_client') as mock_http:
            mock_http.post.return_value = mock_response

            caps = client.detect_capabilities()

            assert caps['supports_mp3'] is True
            assert caps['supports_aac'] is False

    def test_detect_capabilities_parses_aac_support(self, client):
        """Should detect AAC support from protocol info."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '''<?xml version="1.0"?>
        <root>
            <Sink>http-get:*:audio/mp4:DLNA.ORG_PN=AAC_ISO</Sink>
        </root>'''

        with patch('app.dlna_client.http_client') as mock_http:
            mock_http.post.return_value = mock_response

            caps = client.detect_capabilities()

            assert caps['supports_mp3'] is False
            assert caps['supports_aac'] is True

    def test_can_play_format_mp3(self, client):
        """Should correctly identify MP3 playback capability."""
        client.capabilities = {'supports_mp3': True, 'supports_aac': False}

        assert client.can_play_format('audio/mpeg') is True
        assert client.can_play_format('audio/mp3') is True

    def test_can_play_format_aac(self, client):
        """Should correctly identify AAC playback capability."""
        client.capabilities = {'supports_mp3': False, 'supports_aac': True}

        assert client.can_play_format('audio/aac') is True
        assert client.can_play_format('audio/mp4') is True
        assert client.can_play_format('audio/aacp') is True

    def test_can_play_format_unsupported(self, client):
        """Should return False for unsupported formats."""
        client.capabilities = {'supports_mp3': True, 'supports_aac': False, 'supports_ogg': False}

        assert client.can_play_format('audio/ogg') is False
