"""Pytest configuration and shared fixtures."""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, MagicMock
from app.main import app as flask_app
from app.device_manager import DeviceManager


@pytest.fixture
def app():
    """Create Flask app for testing."""
    flask_app.config.update({
        "TESTING": True,
    })
    yield flask_app


@pytest.fixture
def client(app):
    """Create Flask test client."""
    return app.test_client()


@pytest.fixture
def tmp_state_file(tmp_path):
    """Create temporary state file path."""
    state_file = tmp_path / "state.json"
    return str(state_file)


@pytest.fixture
def device_manager(tmp_state_file):
    """Create DeviceManager with temporary state file."""
    return DeviceManager(state_file=tmp_state_file)


@pytest.fixture
def sample_device():
    """Sample device data."""
    return {
        'id': 'uuid:12345678-1234-1234-1234-123456789abc',
        'friendly_name': 'Test Device',
        'manufacturer': 'Test Manufacturer',
        'model_name': 'Test Model',
        'ip': '192.168.1.100',
        'port': 8080,
        'control_url': 'http://192.168.1.100:8080/AVTransport/ctrl',
        'connection_manager_url': 'http://192.168.1.100:8080/ConnectionManager/ctrl',
        'capabilities': {
            'supports_mp3': True,
            'supports_aac': False,
            'supports_flac': False,
            'supports_wav': False,
            'supports_ogg': False,
        }
    }


@pytest.fixture
def mock_ssdp_response():
    """Mock SSDP discovery response."""
    return b"""HTTP/1.1 200 OK
CACHE-CONTROL: max-age=1800
EXT:
LOCATION: http://192.168.1.100:8080/description.xml
SERVER: Linux/5.10 UPnP/1.0 Test/1.0
ST: urn:schemas-upnp-org:device:MediaRenderer:1
USN: uuid:12345678-1234-1234-1234-123456789abc::urn:schemas-upnp-org:device:MediaRenderer:1

"""


@pytest.fixture
def mock_device_description_xml():
    """Mock UPnP device description XML."""
    return """<?xml version="1.0"?>
<root xmlns="urn:schemas-upnp-org:device-1-0">
    <device>
        <deviceType>urn:schemas-upnp-org:device:MediaRenderer:1</deviceType>
        <friendlyName>Test Device</friendlyName>
        <manufacturer>Test Manufacturer</manufacturer>
        <modelName>Test Model</modelName>
        <UDN>uuid:12345678-1234-1234-1234-123456789abc</UDN>
        <serviceList>
            <service>
                <serviceType>urn:schemas-upnp-org:service:AVTransport:1</serviceType>
                <serviceId>urn:upnp-org:serviceId:AVTransport</serviceId>
                <controlURL>/AVTransport/ctrl</controlURL>
                <eventSubURL>/AVTransport/event</eventSubURL>
                <SCPDURL>/AVTransport/scpd.xml</SCPDURL>
            </service>
            <service>
                <serviceType>urn:schemas-upnp-org:service:ConnectionManager:1</serviceType>
                <serviceId>urn:upnp-org:serviceId:ConnectionManager</serviceId>
                <controlURL>/ConnectionManager/ctrl</controlURL>
                <eventSubURL>/ConnectionManager/event</eventSubURL>
                <SCPDURL>/ConnectionManager/scpd.xml</SCPDURL>
            </service>
        </serviceList>
    </device>
</root>"""


@pytest.fixture
def mock_protocol_info():
    """Mock GetProtocolInfo response."""
    return """<?xml version="1.0"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
    <s:Body>
        <u:GetProtocolInfoResponse xmlns:u="urn:schemas-upnp-org:service:ConnectionManager:1">
            <Source></Source>
            <Sink>http-get:*:audio/mpeg:*,http-get:*:audio/mp3:*,http-get:*:audio/wav:*</Sink>
        </u:GetProtocolInfoResponse>
    </s:Body>
</s:Envelope>"""
