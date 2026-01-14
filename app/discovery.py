"""SSDP/UPnP device discovery for finding DLNA devices on the network."""

import socket
import logging
import requests
from typing import List, Dict, Optional
from xml.etree import ElementTree as ET
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class SSDPDiscovery:
    """SSDP/UPnP discovery for DLNA MediaRenderer devices."""

    SSDP_ADDR = "239.255.255.250"
    SSDP_PORT = 1900
    SSDP_MX = 3  # Maximum wait time for responses

    # Search for DLNA MediaRenderer devices
    SSDP_ST = "urn:schemas-upnp-org:device:MediaRenderer:1"

    @staticmethod
    def discover(timeout: int = 5) -> List[Dict[str, str]]:
        """
        Discover DLNA MediaRenderer devices on the local network.

        Args:
            timeout: How long to wait for responses (seconds)

        Returns:
            List of discovered devices with their information
        """
        logger.info(f"Starting SSDP discovery (timeout: {timeout}s)")

        # Build M-SEARCH request
        msg = (
            f'M-SEARCH * HTTP/1.1\r\n'
            f'HOST: {SSDPDiscovery.SSDP_ADDR}:{SSDPDiscovery.SSDP_PORT}\r\n'
            f'MAN: "ssdp:discover"\r\n'
            f'MX: {SSDPDiscovery.SSDP_MX}\r\n'
            f'ST: {SSDPDiscovery.SSDP_ST}\r\n'
            f'\r\n'
        )

        devices = []
        seen_locations = set()

        try:
            # Create UDP socket for multicast
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            # Enable broadcasting - helps with multicast in Docker
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

            # Set multicast TTL (time-to-live)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)

            # Join multicast group - CRITICAL for Docker environments
            # This tells the kernel to accept packets sent to the multicast group
            import struct
            mreq = struct.pack('4sL', socket.inet_aton(SSDPDiscovery.SSDP_ADDR), socket.INADDR_ANY)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

            # Bind to SSDP multicast port to receive responses
            sock.bind(('', SSDPDiscovery.SSDP_PORT))

            sock.settimeout(timeout)

            logger.debug(f"Socket bound to port {SSDPDiscovery.SSDP_PORT}, joined multicast group {SSDPDiscovery.SSDP_ADDR}")

            # Send M-SEARCH request (send twice for reliability)
            msg_encoded = msg.encode('utf-8')
            for i in range(2):
                sock.sendto(msg_encoded, (SSDPDiscovery.SSDP_ADDR, SSDPDiscovery.SSDP_PORT))
                logger.debug(f"M-SEARCH request sent (attempt {i+1})")
                if i == 0:
                    import time
                    time.sleep(0.1)  # Small delay between sends

            # Collect responses
            response_count = 0
            while True:
                try:
                    data, addr = sock.recvfrom(65507)
                    response = data.decode('utf-8', errors='ignore')
                    response_count += 1

                    logger.debug(f"Received response #{response_count} from {addr[0]}")

                    # Parse response headers
                    headers = SSDPDiscovery._parse_ssdp_response(response)
                    location = headers.get('LOCATION')

                    if location and location not in seen_locations:
                        seen_locations.add(location)
                        logger.info(f"Found device at {location}")

                        # Fetch device description
                        device_info = SSDPDiscovery._fetch_device_info(location)
                        if device_info:
                            devices.append(device_info)
                            logger.info(f"Discovered device: {device_info.get('friendly_name', 'Unknown')}")

                except socket.timeout:
                    # Expected - no more responses
                    logger.debug(f"Discovery timeout reached. Received {response_count} total responses.")
                    break
                except Exception as e:
                    logger.debug(f"Error receiving SSDP response: {e}")
                    continue

            sock.close()

        except Exception as e:
            logger.error(f"SSDP discovery failed: {e}", exc_info=True)

        logger.info(f"Discovery complete. Found {len(devices)} device(s)")
        return devices

    @staticmethod
    def _parse_ssdp_response(response: str) -> Dict[str, str]:
        """Parse SSDP response headers."""
        headers = {}
        lines = response.split('\r\n')

        for line in lines[1:]:  # Skip first line (HTTP status)
            if ':' in line:
                key, value = line.split(':', 1)
                headers[key.strip().upper()] = value.strip()

        return headers

    @staticmethod
    def _fetch_device_info(location: str) -> Optional[Dict[str, str]]:
        """
        Fetch device description XML and extract relevant information.

        Args:
            location: URL to device description XML

        Returns:
            Dictionary with device information or None if failed
        """
        try:
            response = requests.get(location, timeout=5)
            if response.status_code != 200:
                logger.warning(f"Failed to fetch device description from {location}")
                return None

            # Parse XML
            root = ET.fromstring(response.content)

            # Define namespaces
            ns = {'upnp': 'urn:schemas-upnp-org:device-1-0'}

            # Extract device information
            device = root.find('.//upnp:device', ns)
            if device is None:
                # Try without namespace
                device = root.find('.//device')

            if device is None:
                logger.warning(f"Could not find device element in {location}")
                return None

            def get_text(element, tag, namespaces=None):
                """Helper to safely extract text from XML element."""
                if namespaces:
                    elem = element.find(f'.//{namespaces[0]}:{tag}', {namespaces[0]: namespaces[1]})
                else:
                    elem = element.find(f'.//{tag}')
                return elem.text if elem is not None else ''

            # Extract basic info
            friendly_name = get_text(device, 'friendlyName', ('upnp', ns['upnp'])) or get_text(device, 'friendlyName')
            manufacturer = get_text(device, 'manufacturer', ('upnp', ns['upnp'])) or get_text(device, 'manufacturer')
            model_name = get_text(device, 'modelName', ('upnp', ns['upnp'])) or get_text(device, 'modelName')
            udn = get_text(device, 'UDN', ('upnp', ns['upnp'])) or get_text(device, 'UDN')

            # Extract host from location URL
            parsed_url = urlparse(location)
            host = parsed_url.hostname or ''
            port = parsed_url.port or 80

            # Find AVTransport service control URL
            control_url = SSDPDiscovery._find_av_transport_control_url(device, ns, parsed_url.scheme, host, port)

            # Find ConnectionManager service control URL (for GetProtocolInfo)
            connection_manager_url = SSDPDiscovery._find_connection_manager_control_url(device, ns, parsed_url.scheme, host, port)

            device_id = udn.replace('uuid:', '') if udn else None

            return {
                'id': device_id,
                'friendly_name': friendly_name,
                'manufacturer': manufacturer,
                'model_name': model_name,
                'host': host,
                'port': port,
                'location': location,
                'control_url': control_url,
                'connection_manager_url': connection_manager_url,
                'udn': udn
            }

        except Exception as e:
            logger.error(f"Error fetching device info from {location}: {e}")
            return None

    @staticmethod
    def _find_av_transport_control_url(device, ns, scheme, host, port) -> Optional[str]:
        """Find AVTransport service control URL."""
        try:
            # Look for AVTransport service
            services = device.findall('.//upnp:service', ns)
            if not services:
                services = device.findall('.//service')

            for service in services:
                service_type = service.find('.//upnp:serviceType', ns)
                if service_type is None:
                    service_type = service.find('.//serviceType')

                if service_type is not None and 'AVTransport' in service_type.text:
                    control_url_elem = service.find('.//upnp:controlURL', ns)
                    if control_url_elem is None:
                        control_url_elem = service.find('.//controlURL')

                    if control_url_elem is not None:
                        control_path = control_url_elem.text
                        # Build full URL
                        if control_path.startswith('http'):
                            return control_path
                        else:
                            # Relative path - build full URL
                            if not control_path.startswith('/'):
                                control_path = '/' + control_path
                            return f"{scheme}://{host}:{port}{control_path}"

            # Fallback to common default
            return f"{scheme}://{host}:{port}/AVTransport/ctrl"

        except Exception as e:
            logger.debug(f"Error finding AVTransport control URL: {e}")
            return f"{scheme}://{host}:{port}/AVTransport/ctrl"

    @staticmethod
    def _find_connection_manager_control_url(device, ns, scheme, host, port) -> Optional[str]:
        """Find ConnectionManager service control URL."""
        try:
            # Look for ConnectionManager service
            services = device.findall('.//upnp:service', ns)
            if not services:
                services = device.findall('.//service')

            for service in services:
                service_type = service.find('.//upnp:serviceType', ns)
                if service_type is None:
                    service_type = service.find('.//serviceType')

                if service_type is not None and 'ConnectionManager' in service_type.text:
                    control_url_elem = service.find('.//upnp:controlURL', ns)
                    if control_url_elem is None:
                        control_url_elem = service.find('.//controlURL')

                    if control_url_elem is not None:
                        control_path = control_url_elem.text
                        # Build full URL
                        if control_path.startswith('http'):
                            return control_path
                        else:
                            # Relative path - build full URL
                            if not control_path.startswith('/'):
                                control_path = '/' + control_path
                            return f"{scheme}://{host}:{port}{control_path}"

            # Fallback to common default
            return f"{scheme}://{host}:{port}/ConnectionManager/ctrl"

        except Exception as e:
            logger.debug(f"Error finding ConnectionManager control URL: {e}")
            return f"{scheme}://{host}:{port}/ConnectionManager/ctrl"
