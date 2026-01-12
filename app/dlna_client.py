"""DLNA/UPnP client for controlling media renderers."""

import requests
import logging
from typing import Optional
from xml.etree import ElementTree as ET

logger = logging.getLogger(__name__)


class DLNAClient:
    """Simple DLNA/UPnP AVTransport client."""

    def __init__(self, device_ip: str, device_port: int = 55000):
        self.device_ip = device_ip
        self.device_port = device_port
        self.control_url = f"http://{device_ip}:{device_port}/DMR/control/AVTransport1"
        self.instance_id = "0"

    def _send_soap_request(self, action: str, arguments: dict = None) -> Optional[str]:
        """Send SOAP request to DLNA device."""
        arguments = arguments or {}

        # Build SOAP envelope
        envelope = f'''<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"
            s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
    <s:Body>
        <u:{action} xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">
            <InstanceID>{self.instance_id}</InstanceID>
'''

        for key, value in arguments.items():
            envelope += f"            <{key}>{value}</{key}>\n"

        envelope += f'''        </u:{action}>
    </s:Body>
</s:Envelope>'''

        headers = {
            'Content-Type': 'text/xml; charset="utf-8"',
            'SOAPAction': f'"urn:schemas-upnp-org:service:AVTransport:1#{action}"',
        }

        try:
            response = requests.post(
                self.control_url,
                data=envelope.encode('utf-8'),
                headers=headers,
                timeout=10
            )

            if response.status_code == 200:
                logger.debug(f"SOAP action {action} succeeded")
                return response.text
            else:
                logger.error(f"SOAP action {action} failed: {response.status_code} - {response.text}")
                return None

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send SOAP request {action}: {e}")
            return None

    def set_av_transport_uri(self, uri: str, metadata: str = "") -> bool:
        """Set the URI of the media to play."""
        logger.info(f"Setting AV Transport URI to {uri}")

        # Escape XML entities in URI
        uri_escaped = uri.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

        arguments = {
            'CurrentURI': uri_escaped,
            'CurrentURIMetaData': metadata
        }

        response = self._send_soap_request('SetAVTransportURI', arguments)
        return response is not None

    def play(self, speed: str = "1") -> bool:
        """Start playback."""
        logger.info("Sending Play command")

        arguments = {
            'Speed': speed
        }

        response = self._send_soap_request('Play', arguments)
        return response is not None

    def stop(self) -> bool:
        """Stop playback."""
        logger.info("Sending Stop command")

        response = self._send_soap_request('Stop')
        return response is not None

    def pause(self) -> bool:
        """Pause playback."""
        logger.info("Sending Pause command")

        response = self._send_soap_request('Pause')
        return response is not None

    def get_transport_info(self) -> Optional[dict]:
        """Get current transport state."""
        response = self._send_soap_request('GetTransportInfo')

        if not response:
            return None

        try:
            root = ET.fromstring(response)
            ns = {'s': 'http://schemas.xmlsoap.org/soap/envelope/'}

            state_elem = root.find('.//CurrentTransportState')
            status_elem = root.find('.//CurrentTransportStatus')

            return {
                'state': state_elem.text if state_elem is not None else 'UNKNOWN',
                'status': status_elem.text if status_elem is not None else 'UNKNOWN'
            }
        except ET.ParseError as e:
            logger.error(f"Failed to parse transport info: {e}")
            return None

    def play_url(self, url: str) -> bool:
        """Set URI and start playback in one call."""
        if not self.set_av_transport_uri(url):
            return False

        # Small delay to let the device process the URI
        import time
        time.sleep(0.5)

        return self.play()
