"""SSDP/UPnP device discovery for finding DLNA devices on the network."""

import logging
import socket
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

from app.http_client import http_client

logger = logging.getLogger(__name__)


class SSDPDiscovery:
    """SSDP/UPnP discovery for DLNA MediaRenderer devices."""

    SSDP_ADDR = "239.255.255.250"
    SSDP_PORT = 1900
    SSDP_MX = 3  # Maximum wait time for responses

    # Search for DLNA MediaRenderer devices
    SSDP_ST = "urn:schemas-upnp-org:device:MediaRenderer:1"

    @staticmethod
    def discover(timeout: int = 5, device_callback=None) -> list[dict[str, str]]:
        """
        Discover DLNA MediaRenderer devices on the local network.

        Args:
            timeout: How long to wait for responses (seconds)
            device_callback: Optional callback(device_info) called for each found device

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

            # Collect responses - just gather locations first
            response_count = 0
            locations = []
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
                        locations.append(location)
                        logger.info(f"Found device at {location}")

                except socket.timeout:
                    # Expected - no more responses
                    logger.debug(f"Discovery timeout reached. Received {response_count} total responses.")
                    break
                except Exception as e:
                    logger.debug(f"Error receiving SSDP response: {e}")
                    continue

            sock.close()

            # Fetch device descriptions in parallel
            if locations:
                from concurrent.futures import ThreadPoolExecutor, TimeoutError, as_completed
                logger.debug(f"Fetching device info for {len(locations)} locations in parallel")

                with ThreadPoolExecutor(max_workers=min(10, len(locations))) as executor:
                    future_to_location = {
                        executor.submit(SSDPDiscovery._fetch_device_info, loc): loc
                        for loc in locations
                    }

                    # Wait for all futures with a timeout (max 15s for all parallel fetches)
                    for future in as_completed(future_to_location, timeout=15):
                        location = future_to_location[future]
                        try:
                            device_info = future.result(timeout=1)  # Individual result timeout
                            if device_info:
                                devices.append(device_info)
                                logger.info(f"Discovered device: {device_info.get('friendly_name', 'Unknown')}")
                                # Call callback immediately when device is found
                                if device_callback:
                                    try:
                                        device_callback(device_info)
                                    except Exception as e:
                                        logger.error(f"Device callback failed: {e}")
                            else:
                                logger.warning(f"Device at {location} returned no info (filtered out or failed parsing)")
                        except TimeoutError:
                            logger.warning(f"Timeout fetching device info from {location}")
                        except Exception as e:
                            logger.warning(f"Failed to fetch device info from {location}: {e}")

        except Exception as e:
            logger.error(f"SSDP discovery failed: {e}", exc_info=True)

        logger.info(f"Discovery complete. Found {len(devices)} device(s)")
        return devices

    @staticmethod
    def try_direct_connection(host: str, timeout: int = 5) -> dict[str, str] | None:
        """
        Try to connect directly to a device by IP/hostname.
        Attempts common device description XML paths.

        Args:
            host: IP address or hostname
            timeout: Timeout for each attempt (default: 5s)

        Returns:
            Device information dictionary or None if not found
        """
        # Common device description paths (most likely first)
        common_paths = [
            '/description.xml',
            '/rootDesc.xml',
            '/dmr',
            '/upnpd/description.xml',
            '/AVTransport/ctrl'
        ]

        # Common ports for DLNA devices (most common first)
        common_ports = [8080, 49152, 9197, 49153, 49154, 80]

        logger.info(f"Attempting direct connection to {host}")

        for port in common_ports:
            for path in common_paths:
                location = f"http://{host}:{port}{path}"
                try:
                    response = http_client.get(location, timeout=timeout)
                    if response.status_code == 200 and 'xml' in response.headers.get('Content-Type', '').lower():
                        logger.info(f"Found device at {location}")
                        device_info = SSDPDiscovery._fetch_device_info(location)
                        if device_info:
                            return device_info
                except Exception as e:
                    logger.debug(f"Failed to connect to {location}: {e}")
                    continue

        logger.warning(f"Could not connect to device at {host}")
        return None

    @staticmethod
    def _parse_ssdp_response(response: str) -> dict[str, str]:
        """Parse SSDP response headers."""
        headers = {}
        lines = response.split('\r\n')

        for line in lines[1:]:  # Skip first line (HTTP status)
            if ':' in line:
                key, value = line.split(':', 1)
                headers[key.strip().upper()] = value.strip()

        return headers

    @staticmethod
    def _fetch_device_info(location: str) -> dict[str, str] | None:
        """
        Fetch device description XML and extract relevant information.

        Args:
            location: URL to device description XML

        Returns:
            Dictionary with device information or None if failed
        """
        try:
            response = http_client.get(location, timeout=5)
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

            # Filter out devices without AVTransport (MediaServers, not MediaRenderers)
            # Only keep devices that can actually play media
            if not control_url or control_url.endswith('/AVTransport/ctrl'):
                # If control_url is the fallback default, verify AVTransport actually exists
                services = device.findall('.//upnp:service', ns) or device.findall('.//service')
                has_av_transport = False
                for service in services:
                    service_type = service.find('.//upnp:serviceType', ns)
                    if service_type is None:
                        service_type = service.find('.//serviceType')
                    if service_type is not None and 'AVTransport' in service_type.text:
                        has_av_transport = True
                        break

                if not has_av_transport:
                    logger.debug(f"Skipping device {friendly_name} - no AVTransport service (likely MediaServer)")
                    return None

            # Find ConnectionManager service control URL (for GetProtocolInfo)
            connection_manager_url = SSDPDiscovery._find_connection_manager_control_url(device, ns, parsed_url.scheme, host, port)

            device_id = udn.replace('uuid:', '') if udn else None

            return {
                'id': device_id,
                'friendly_name': friendly_name,
                'manufacturer': manufacturer,
                'model_name': model_name,
                'ip': host,
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
    def _find_av_transport_control_url(device, ns, scheme, host, port) -> str | None:
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
    def _find_connection_manager_control_url(device, ns, scheme, host, port) -> str | None:
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
