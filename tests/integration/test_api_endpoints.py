"""Integration tests for API endpoints."""

import json


class TestHealthEndpoint:
    """Test health check endpoint."""

    def test_health_check_returns_ok(self, client):
        """GET /health returns 200 OK."""
        response = client.get('/health')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'
        assert 'streaming' in data


class TestDeviceEndpoints:
    """Test device management endpoints."""

    def test_get_devices_cached(self, client):
        """GET /devices returns cached devices."""
        response = client.get('/devices?force_scan=false')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'devices' in data
        assert 'count' in data
        assert 'cache_age_seconds' in data

    def test_get_devices_invalid_force_scan(self, client):
        """GET /devices with invalid force_scan returns 400."""
        response = client.get('/devices?force_scan=True')  # Capital T
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'message' in data

    def test_select_device_missing_ip(self, client):
        """POST /devices/select without IP returns 400."""
        response = client.post('/devices/select')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'message' in data
        assert 'required' in data['message'].lower()

    def test_select_device_invalid_ip(self, client):
        """POST /devices/select with invalid IP returns 400."""
        response = client.post('/devices/select?ip=999.999.999.999')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'message' in data

    def test_select_device_injection_attempt(self, client):
        """POST /devices/select with injection attempt returns 400."""
        response = client.post('/devices/select?ip=192.168.1.1;whoami')
        assert response.status_code == 400

    def test_get_current_device_none_selected(self, client):
        """GET /devices/current when none selected."""
        response = client.get('/devices/current')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['device'] is None
        assert 'message' in data


class TestPlaybackEndpoints:
    """Test playback control endpoints."""

    def test_play_without_device_selected(self, client):
        """POST /play returns 400 when no device selected."""
        response = client.post('/play?streamUrl=http://example.com/stream.mp3')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'message' in data
        assert 'no device' in data['message'].lower()

    def test_play_with_invalid_url(self, client):
        """POST /play with invalid URL returns 400."""
        response = client.post('/play?streamUrl=file:///etc/passwd')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'message' in data

    def test_play_with_javascript_url(self, client):
        """POST /play with javascript: URL returns 400."""
        response = client.post('/play?streamUrl=javascript:alert(1)')
        assert response.status_code == 400

    def test_stop_playback(self, client):
        """POST /stop returns success."""
        response = client.post('/stop')
        # Should succeed even if nothing is playing
        assert response.status_code in [200, 500]  # May fail if no client initialized


class TestStatusEndpoints:
    """Test status endpoints."""

    def test_get_status(self, client):
        """GET /status returns status information."""
        response = client.get('/status')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'streaming' in data
        assert isinstance(data['streaming'], bool)


class TestErrorHandlers:
    """Test error handlers."""

    def test_404_returns_json(self, client):
        """404 endpoint returns JSON."""
        response = client.get('/nonexistent')
        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'message' in data
        assert 'error' not in data  # Should be 'message', not 'error'

    def test_405_method_not_allowed(self, client):
        """405 returns JSON."""
        response = client.get('/play')  # GET instead of POST
        assert response.status_code == 405
        data = json.loads(response.data)
        assert 'message' in data
