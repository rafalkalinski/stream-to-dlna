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


class TestDIDLMetadata:
    """Tests for DIDL-Lite metadata generation and SOAP encoding."""

    def test_build_didl_metadata_contains_url(self):
        """DIDL-Lite should embed the stream URL in the res element."""
        url = 'http://192.168.0.2:8080/stream.mp3'
        result = DLNAClient._build_didl_metadata(url)
        assert url in result

    def test_build_didl_metadata_mp3_profile(self):
        """DIDL-Lite for audio/mpeg should use MP3 DLNA profile."""
        result = DLNAClient._build_didl_metadata('http://example.com/stream.mp3', 'audio/mpeg')
        assert 'DLNA.ORG_PN=MP3' in result
        assert 'audio/mpeg' in result

    def test_build_didl_metadata_flac_profile(self):
        """DIDL-Lite for audio/flac should use FLAC DLNA profile."""
        result = DLNAClient._build_didl_metadata('http://example.com/stream.flac', 'audio/flac')
        assert 'DLNA.ORG_PN=FLAC' in result

    def test_build_didl_metadata_unknown_mime_uses_wildcard(self):
        """DIDL-Lite for unknown MIME type should use wildcard profile."""
        result = DLNAClient._build_didl_metadata('http://example.com/stream', 'audio/ogg')
        assert 'audio/ogg' in result
        assert 'http-get:*:audio/ogg:*' in result

    def test_build_didl_metadata_contains_audio_broadcast_class(self):
        """DIDL-Lite should use audioBroadcast UPnP class for live streams."""
        result = DLNAClient._build_didl_metadata('http://example.com/stream.mp3')
        assert 'object.item.audioItem.audioBroadcast' in result

    def test_build_didl_metadata_escapes_ampersand_in_url(self):
        """URL with & should be XML-escaped inside DIDL-Lite."""
        url = 'http://example.com/stream?a=1&b=2'
        result = DLNAClient._build_didl_metadata(url)
        assert '&amp;' in result
        assert 'a=1&b=2' not in result

    def test_set_av_transport_uri_soap_contains_escaped_didl(self):
        """SOAP body must contain XML-escaped DIDL-Lite, not raw XML."""
        client = DLNAClient(device_host='192.168.1.100')
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '<response>OK</response>'

        with patch('app.dlna_client.http_client') as mock_http:
            mock_http.post.return_value = mock_response
            client.set_av_transport_uri('http://192.168.0.2:8080/stream.mp3', 'audio/mpeg')

            soap_body = mock_http.post.call_args[1]['data'].decode()
            # DIDL-Lite must be escaped — raw < and > inside the value would be invalid SOAP
            assert '&lt;DIDL-Lite' in soap_body
            assert '&lt;/DIDL-Lite&gt;' in soap_body
            # Raw unescaped DIDL tags must not appear as top-level XML
            assert '<DIDL-Lite' not in soap_body

    def test_set_av_transport_uri_soap_contains_current_uri_metadata(self):
        """SOAP body must include CurrentURIMetaData element."""
        client = DLNAClient(device_host='192.168.1.100')
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '<response>OK</response>'

        with patch('app.dlna_client.http_client') as mock_http:
            mock_http.post.return_value = mock_response
            client.set_av_transport_uri('http://192.168.0.2:8080/stream.mp3')

            soap_body = mock_http.post.call_args[1]['data'].decode()
            assert '<CurrentURIMetaData>' in soap_body
