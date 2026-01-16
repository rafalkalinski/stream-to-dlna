"""DLNA/UPnP client for controlling media renderers."""

import logging
from typing import Any
from xml.etree import ElementTree as ET

from app.http_client import http_client

logger = logging.getLogger(__name__)


class DLNAClient:
    """Simple DLNA/UPnP AVTransport client."""

    def __init__(self, device_host: str, device_port: int = 55000, protocol: str = "http",
                 control_url: str | None = None, connection_manager_url: str | None = None):
        self.device_host = device_host
        self.device_port = device_port
        self.protocol = protocol
        self.control_url = control_url or f"{protocol}://{device_host}:{device_port}/AVTransport/ctrl"
        self.connection_manager_url = connection_manager_url or f"{protocol}://{device_host}:{device_port}/ConnectionManager/ctrl"
        self.instance_id = "0"
        self.capabilities: dict[str, Any] | None = None

    def _send_soap_request(self, action: str, arguments: dict = None) -> str | None:
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
            response = http_client.post(
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

    def stop_if_playing(self) -> bool:
        """Stop playback only if device is currently playing or paused.

        Returns True if stop was sent or device was already stopped, False on error.
        """
        info = self.get_transport_info()
        if not info:
            logger.debug("Could not get transport info, skipping Stop command")
            return True  # Skip stop to avoid unnecessary errors

        state = info.get('state', 'UNKNOWN')

        # Only send stop if device is in a state that can be stopped
        # Note: TRANSITIONING is excluded as device may reject Stop during state transitions
        if state in ['PLAYING', 'PAUSED_PLAYBACK']:
            logger.info(f"Device is {state}, sending Stop command")
            return self.stop()
        else:
            logger.debug(f"Device is {state}, skipping Stop command")
            return True  # Consider this success - device is already stopped or transitioning

    def pause(self) -> bool:
        """Pause playback."""
        logger.info("Sending Pause command")

        response = self._send_soap_request('Pause')
        return response is not None

    def get_transport_info(self, retries: int = 2) -> dict | None:
        """
        Get current transport state with retry logic.

        Args:
            retries: Number of retry attempts on failure (default: 2)

        Returns:
            Dictionary with state and status, or None if all attempts fail
        """
        last_error = None

        for attempt in range(retries + 1):
            try:
                response = self._send_soap_request('GetTransportInfo')

                if not response:
                    last_error = "No response from device"
                    if attempt < retries:
                        logger.debug(f"GetTransportInfo attempt {attempt + 1} failed, retrying...")
                        import time
                        time.sleep(0.3)
                        continue
                    return None

                root = ET.fromstring(response)

                state_elem = root.find('.//CurrentTransportState')
                status_elem = root.find('.//CurrentTransportStatus')

                result = {
                    'state': state_elem.text if state_elem is not None else 'UNKNOWN',
                    'status': status_elem.text if status_elem is not None else 'UNKNOWN'
                }

                # Success - return immediately
                if attempt > 0:
                    logger.debug(f"GetTransportInfo succeeded on attempt {attempt + 1}")
                return result

            except ET.ParseError as e:
                last_error = f"Parse error: {e}"
                if attempt < retries:
                    logger.debug(f"GetTransportInfo parse error on attempt {attempt + 1}, retrying...")
                    import time
                    time.sleep(0.3)
                    continue
            except Exception as e:
                last_error = str(e)
                if attempt < retries:
                    logger.debug(f"GetTransportInfo error on attempt {attempt + 1}: {e}, retrying...")
                    import time
                    time.sleep(0.3)
                    continue

        logger.debug(f"GetTransportInfo failed after {retries + 1} attempts: {last_error}")
        return None

    def play_url(self, url: str) -> bool:
        """Set URI and start playback in one call."""
        if not self.set_av_transport_uri(url):
            return False

        # Small delay to let the device process the URI
        import time
        time.sleep(0.5)

        return self.play()

    def get_protocol_info(self) -> str | None:
        """
        Get supported protocols and formats from the device.
        Uses ConnectionManager:GetProtocolInfo.

        Returns:
            Protocol info string or None if failed
        """
        logger.debug(f"Getting protocol info from {self.connection_manager_url}")

        envelope = '''<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"
            s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
    <s:Body>
        <u:GetProtocolInfo xmlns:u="urn:schemas-upnp-org:service:ConnectionManager:1">
        </u:GetProtocolInfo>
    </s:Body>
</s:Envelope>'''

        headers = {
            'Content-Type': 'text/xml; charset="utf-8"',
            'SOAPAction': '"urn:schemas-upnp-org:service:ConnectionManager:1#GetProtocolInfo"',
        }

        try:
            response = http_client.post(
                self.connection_manager_url,
                data=envelope.encode('utf-8'),
                headers=headers,
                timeout=10
            )

            if response.status_code == 200:
                # Parse response to extract Sink protocols (what device can play)
                root = ET.fromstring(response.text)
                sink_elem = root.find('.//{*}Sink')
                if sink_elem is not None and sink_elem.text:
                    logger.debug(f"Device supports protocols: {sink_elem.text[:200]}...")
                    return sink_elem.text
                else:
                    logger.warning("Could not find Sink element in GetProtocolInfo response")
                    return None
            else:
                logger.warning(f"GetProtocolInfo failed: {response.status_code} - {response.text[:200]}")
                return None

        except Exception as e:
            logger.warning(f"Failed to get protocol info: {e}")
            return None

    def detect_capabilities(self) -> dict[str, Any]:
        """
        Detect device capabilities including supported audio formats.

        Returns:
            Dictionary with capability information
        """
        protocol_info = self.get_protocol_info()

        capabilities = {
            'supports_mp3': False,
            'supports_aac': False,
            'supports_flac': False,
            'supports_wav': False,
            'supports_ogg': False,
            'raw_protocol_info': protocol_info
        }

        if protocol_info:
            # Parse protocol info - format is comma-separated list of:
            # protocol:network:contentFormat:additionalInfo
            # e.g., http-get:*:audio/mpeg:*
            protocols = protocol_info.split(',')

            for proto in protocols:
                proto_lower = proto.lower()
                if 'audio/mpeg' in proto_lower or 'audio/mp3' in proto_lower:
                    capabilities['supports_mp3'] = True
                if 'audio/aac' in proto_lower or 'audio/x-aac' in proto_lower or 'audio/mp4' in proto_lower:
                    capabilities['supports_aac'] = True
                if 'audio/flac' in proto_lower or 'audio/x-flac' in proto_lower:
                    capabilities['supports_flac'] = True
                if 'audio/wav' in proto_lower or 'audio/x-wav' in proto_lower:
                    capabilities['supports_wav'] = True
                if 'audio/ogg' in proto_lower or 'audio/x-ogg' in proto_lower:
                    capabilities['supports_ogg'] = True

        self.capabilities = capabilities
        logger.info(f"Device capabilities: MP3={capabilities['supports_mp3']}, "
                   f"AAC={capabilities['supports_aac']}, "
                   f"FLAC={capabilities['supports_flac']}")

        return capabilities

    def can_play_format(self, mime_type: str) -> bool:
        """
        Check if device can play a specific MIME type.

        Args:
            mime_type: MIME type to check (e.g., 'audio/mpeg', 'audio/aac')

        Returns:
            True if device supports the format
        """
        if not self.capabilities:
            self.detect_capabilities()

        if not self.capabilities:
            # If we can't detect capabilities, assume transcoding is needed
            return False

        mime_lower = mime_type.lower()

        if 'mpeg' in mime_lower or 'mp3' in mime_lower:
            return self.capabilities.get('supports_mp3', False)
        elif 'aac' in mime_lower or 'mp4' in mime_lower:
            return self.capabilities.get('supports_aac', False)
        elif 'flac' in mime_lower:
            return self.capabilities.get('supports_flac', False)
        elif 'wav' in mime_lower:
            return self.capabilities.get('supports_wav', False)
        elif 'ogg' in mime_lower:
            return self.capabilities.get('supports_ogg', False)

        return False
