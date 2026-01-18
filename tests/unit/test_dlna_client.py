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


class TestDIDLMetadata:
    """Test DIDL-Lite metadata generation."""

    @pytest.fixture
    def client(self):
        """Create a DLNAClient instance with mock capabilities."""
        client = DLNAClient(
            device_host="192.168.1.100",
            device_port=55000
        )
        client.capabilities = {
            'supports_mp3': True,
            'supports_aac': True,
            'supports_flac': False,
            'raw_protocol_info': 'http-get:*:audio/mpeg:DLNA.ORG_PN=MP3;DLNA.ORG_OP=01,http-get:*:audio/mp4:DLNA.ORG_PN=AAC_ISO;DLNA.ORG_OP=01'
        }
        return client

    def test_build_didl_metadata_basic(self, client):
        """DIDL metadata should contain all required elements."""
        metadata = client._build_didl_metadata(
            url="http://example.com/stream.mp3",
            title="Test Stream",
            mime_type="audio/mpeg"
        )

        # Check for required namespaces
        assert 'xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/"' in metadata
        assert 'xmlns:dc="http://purl.org/dc/elements/1.1/"' in metadata
        assert 'xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/"' in metadata
        assert 'xmlns:dlna="urn:schemas-upnp-org:metadata-1-0/dlna/"' in metadata

        # Check for required elements
        assert '<dc:title>Test Stream</dc:title>' in metadata
        assert '<upnp:class>object.item.audioItem.musicTrack</upnp:class>' in metadata
        assert 'http://example.com/stream.mp3' in metadata

    def test_build_didl_metadata_escapes_xml_entities(self, client):
        """DIDL metadata should escape XML entities in title and URL."""
        metadata = client._build_didl_metadata(
            url="http://example.com/stream?a=1&b=2",
            title="Rock & Roll",
            mime_type="audio/mpeg"
        )

        # Check XML escaping
        assert 'Rock &amp; Roll' in metadata
        assert 'a=1&amp;b=2' in metadata
        assert '&' not in metadata.replace('&amp;', '').replace('&lt;', '').replace('&gt;', '').replace('&quot;', '').replace('&apos;', '')

    def test_build_didl_metadata_uses_device_protocol_info(self, client):
        """DIDL metadata should use exact protocolInfo from device capabilities."""
        metadata = client._build_didl_metadata(
            url="http://example.com/stream.mp3",
            title="Test",
            mime_type="audio/mpeg"
        )

        # Should contain the exact protocolInfo from capabilities
        assert 'http-get:*:audio/mpeg:DLNA.ORG_PN=MP3;DLNA.ORG_OP=01' in metadata

    def test_build_didl_metadata_fallback_for_unsupported_mime(self, client):
        """DIDL metadata should build manual protocolInfo for unsupported MIME types."""
        # Clear capabilities to force fallback
        client.capabilities = None

        metadata = client._build_didl_metadata(
            url="http://example.com/stream.mp3",
            title="Test",
            mime_type="audio/mpeg"
        )

        # Should still contain valid protocolInfo (manually built)
        assert 'DLNA.ORG_PN=MP3' in metadata
        assert 'DLNA.ORG_OP=01' in metadata
        assert 'DLNA.ORG_CI=0' in metadata
        assert 'DLNA.ORG_FLAGS=01700000000000000000000000000000' in metadata


class TestProtocolInfoLookup:
    """Test protocolInfo lookup from device capabilities."""

    @pytest.fixture
    def client(self):
        """Create a DLNAClient instance with mock capabilities."""
        client = DLNAClient(
            device_host="192.168.1.100",
            device_port=55000
        )
        client.capabilities = {
            'raw_protocol_info': (
                'http-get:*:audio/mpeg:DLNA.ORG_PN=MP3;DLNA.ORG_OP=01;DLNA.ORG_FLAGS=01700000000000000000000000000000,'
                'http-get:*:audio/mp4:DLNA.ORG_PN=AAC_ISO;DLNA.ORG_OP=01;DLNA.ORG_FLAGS=01700000000000000000000000000000,'
                'http-get:*:audio/flac:DLNA.ORG_PN=FLAC;DLNA.ORG_OP=01;DLNA.ORG_FLAGS=01700000000000000000000000000000'
            )
        }
        return client

    def test_get_protocol_info_for_mp3(self, client):
        """Should find exact protocolInfo for MP3."""
        info = client._get_protocol_info_for_mime('audio/mpeg')

        assert info is not None
        assert 'audio/mpeg' in info
        assert 'DLNA.ORG_PN=MP3' in info

    def test_get_protocol_info_for_aac_fallback(self, client):
        """Should fallback to audio/mp4 for AAC requests."""
        info = client._get_protocol_info_for_mime('audio/aac')

        assert info is not None
        assert 'audio/mp4' in info
        assert 'DLNA.ORG_PN=AAC_ISO' in info

    def test_get_protocol_info_for_unsupported_format(self, client):
        """Should return None for unsupported MIME types."""
        info = client._get_protocol_info_for_mime('audio/ogg')

        assert info is None

    def test_get_protocol_info_without_capabilities(self):
        """Should return None when capabilities are not available."""
        client = DLNAClient(
            device_host="192.168.1.100",
            device_port=55000
        )

        info = client._get_protocol_info_for_mime('audio/mpeg')

        assert info is None


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
