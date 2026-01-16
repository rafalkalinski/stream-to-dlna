"""Unit tests for input validation functions."""

import pytest

from app.main import validate_boolean_string, validate_ip_address, validate_stream_url


class TestValidateIPAddress:
    """Test IP address validation."""

    @pytest.mark.parametrize("valid_ip", [
        "192.168.1.1",
        "10.0.0.1",
        "172.16.0.1",
        "255.255.255.255",
        "0.0.0.0",
        "127.0.0.1",
    ])
    def test_valid_ip_addresses(self, valid_ip):
        """Valid IPv4 addresses should pass validation."""
        assert validate_ip_address(valid_ip) is True

    @pytest.mark.parametrize("invalid_ip", [
        "999.999.999.999",  # Out of range
        "256.1.1.1",  # Octet > 255
        "192.168.1",  # Too few octets
        "192.168.1.1.1",  # Too many octets
        "abc.def.ghi.jkl",  # Letters
        "192.168.1.1;whoami",  # Command injection
        "192.168.1.1' OR '1'='1",  # SQL injection attempt
        "192.168.1.1`whoami`",  # Command substitution
        "192.168.1.1\x00",  # Null byte
        "../192.168.1.1",  # Path traversal
        "192.168.1.1/24",  # CIDR notation
        "",  # Empty string
        "   ",  # Whitespace only
        "192.168.1.1 ",  # Trailing space
        " 192.168.1.1",  # Leading space
    ])
    def test_invalid_ip_addresses(self, invalid_ip):
        """Invalid IP addresses should fail validation."""
        assert validate_ip_address(invalid_ip) is False


class TestValidateBooleanString:
    """Test boolean string validation."""

    @pytest.mark.parametrize("valid_bool", ["true", "false"])
    def test_valid_boolean_strings(self, valid_bool):
        """Only exact 'true' and 'false' should pass."""
        assert validate_boolean_string(valid_bool) is True

    @pytest.mark.parametrize("invalid_bool", [
        "True",  # Capital T
        "False",  # Capital F
        "TRUE",  # All caps
        "FALSE",  # All caps
        "1",  # Number as string
        "0",  # Number as string
        "yes",  # Boolean word
        "no",  # Boolean word
        "on",  # Boolean word
        "off",  # Boolean word
        "",  # Empty string
        "true ",  # Trailing space
        " true",  # Leading space
        "True",  # Wrong case
    ])
    def test_invalid_boolean_strings(self, invalid_bool):
        """Non-exact boolean strings should fail."""
        assert validate_boolean_string(invalid_bool) is False


class TestValidateStreamURL:
    """Test stream URL validation."""

    @pytest.mark.parametrize("valid_url", [
        "http://stream.example.com/radio",
        "https://secure.example.com/stream",
        "http://192.168.1.100:8080/stream.mp3",
        "https://subdomain.domain.tld/path/to/stream",
        "http://example.com/stream?token=abc123",
        "https://stream.radio357.pl/u/2AD8E6/test",
    ])
    def test_valid_stream_urls(self, valid_url):
        """Valid HTTP/HTTPS URLs should pass."""
        assert validate_stream_url(valid_url) is True

    @pytest.mark.parametrize("invalid_url", [
        "file:///etc/passwd",  # File scheme
        "ftp://example.com/file",  # FTP scheme
        "javascript:alert(1)",  # JavaScript scheme
        "data:text/html,<script>alert(1)</script>",  # Data URI
        "http://",  # Missing netloc
        "://example.com",  # Missing scheme
        "example.com/stream",  # No scheme
        "",  # Empty string
        "http://localhost:22",  # Localhost (potential SSRF)
        "http://127.0.0.1/admin",  # Loopback (potential SSRF)
        "http://169.254.169.254/metadata",  # Cloud metadata SSRF
        "http://[::1]/admin",  # IPv6 loopback
        "gopher://example.com",  # Gopher scheme
        "dict://example.com:2628/",  # DICT protocol
    ])
    def test_invalid_stream_urls(self, invalid_url):
        """Invalid schemes or formats should fail."""
        assert validate_stream_url(invalid_url) is False
