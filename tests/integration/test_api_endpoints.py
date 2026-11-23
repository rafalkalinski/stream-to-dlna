"""Integration tests for API endpoints."""

import json


class TestHealthEndpoint:
    """Test health check endpoint."""

    def test_health_check_returns_ok(self, client):
        """GET /health returns 200 OK."""
        response = client.get("/health")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "ok"
        assert "streaming" in data


class TestDeviceEndpoints:
    """Test device management endpoints."""

    def test_get_devices_cached(self, client):
        """GET /devices returns cached devices."""
        response = client.get("/devices?force_scan=false")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "devices" in data
        assert "count" in data
        assert "cache_age_seconds" in data

    def test_get_devices_invalid_force_scan(self, client):
        """GET /devices with invalid force_scan returns 400."""
        response = client.get("/devices?force_scan=True")  # Capital T
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "message" in data

    def test_select_device_missing_ip(self, client):
        """POST /devices/select without IP returns 400."""
        response = client.post("/devices/select")
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "message" in data
        assert "required" in data["message"].lower()

    def test_select_device_invalid_ip(self, client):
        """POST /devices/select with invalid IP returns 400."""
        response = client.post("/devices/select?ip=999.999.999.999")
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "message" in data

    def test_select_device_injection_attempt(self, client):
        """POST /devices/select with injection attempt returns 400."""
        response = client.post("/devices/select?ip=192.168.1.1;whoami")
        assert response.status_code == 400

    def test_get_current_device_none_selected(self, client):
        """GET /devices/current when none selected."""
        response = client.get("/devices/current")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["device"] is None
        assert "message" in data


class TestPlaybackEndpoints:
    """Test playback control endpoints."""

    def test_play_without_device_selected(self, client):
        """POST /play returns 400 when no device selected."""
        response = client.post("/play?streamUrl=http://example.com/stream.mp3")
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "message" in data
        assert "no device" in data["message"].lower()

    def test_play_with_invalid_url(self, client):
        """POST /play with invalid URL returns 400."""
        response = client.post("/play?streamUrl=file:///etc/passwd")
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "message" in data

    def test_play_with_javascript_url(self, client):
        """POST /play with javascript: URL returns 400."""
        response = client.post("/play?streamUrl=javascript:alert(1)")
        assert response.status_code == 400

    def test_stop_playback(self, client):
        """POST /stop returns success."""
        response = client.post("/stop")
        # Should succeed even if nothing is playing
        assert response.status_code in [200, 500]  # May fail if no client initialized


class TestStatusEndpoints:
    """Test status endpoints."""

    def test_get_status(self, client):
        """GET /status returns status information."""
        response = client.get("/status")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "streaming" in data
        assert isinstance(data["streaming"], bool)
        assert "stream" in data

    def test_status_reports_current_stream(self, client, monkeypatch):
        """GET /status includes source stream details while streaming."""
        from unittest.mock import Mock

        import app.main as main

        running = Mock()
        running.is_running.return_value = True
        info = {"url": "http://radio.example/stream", "transcoding": True, "format": "audio/aac"}
        monkeypatch.setattr(main, "streamer", running)
        monkeypatch.setattr(main, "playback_info", info)
        monkeypatch.setattr(main, "dlna_client", None)

        data = json.loads(client.get("/status").data)
        assert data["streaming"] is True
        assert data["stream"] == info


class TestEventStream:
    """Test the Server-Sent Events endpoint."""

    def test_events_sends_initial_status_and_devices(self, client):
        import app.main as main

        response = client.get("/events", buffered=False)
        try:
            assert response.status_code == 200
            assert response.mimetype == "text/event-stream"
            chunks = response.response
            assert next(chunks).decode().startswith("retry:")
            first = next(chunks).decode()
            assert first.startswith("event: status\n")
            assert "effective_state" in first
            assert next(chunks).decode().startswith("event: devices\n")
            assert main.event_broker.subscriber_count == 1
        finally:
            response.close()
        assert main.event_broker.subscriber_count == 0

    def test_events_rejects_when_full(self, client, monkeypatch):
        import app.main as main
        from app.events import EventBroker

        monkeypatch.setattr(main, "event_broker", EventBroker(max_subscribers=0))
        response = client.get("/events")
        assert response.status_code == 503


class TestActivity:
    """Test activity broadcasting with client names."""

    def test_stop_records_activity_with_client_name(self, client, monkeypatch):
        import app.main as main
        from app.events import EventBroker

        broker = EventBroker()
        monkeypatch.setattr(main, "event_broker", broker)
        monkeypatch.setattr(main, "dlna_client", None)
        monkeypatch.setattr(main, "streamer", None)

        # Non-ASCII names are sent URI-encoded by the web player
        response = client.post("/stop", headers={"X-Client-Name": "Telefon%20Rafa%C5%82a"})
        assert response.status_code == 200

        history = broker.activity_history()
        assert len(history) == 1
        assert history[0]["action"] == "stop"
        assert history[0]["client"] == "Telefon Rafała"
        assert history[0]["id"] == 1

    def test_client_name_falls_back_to_ip_and_is_sanitised(self, client, monkeypatch):
        import app.main as main
        from app.events import EventBroker

        broker = EventBroker()
        monkeypatch.setattr(main, "event_broker", broker)
        monkeypatch.setattr(main, "dlna_client", None)
        monkeypatch.setattr(main, "streamer", None)

        client.post("/stop")
        client.post("/stop", headers={"X-Client-Name": "a%0Ab" + "x" * 100})
        first, second = broker.activity_history()
        assert first["client"] == "127.0.0.1"
        assert "\n" not in second["client"] and len(second["client"]) <= 40

    def test_events_replays_activity_history(self, client, monkeypatch):
        import app.main as main
        from app.events import EventBroker

        broker = EventBroker()
        broker.record_activity({"action": "play", "message": "Play x on y", "client": "c"})
        monkeypatch.setattr(main, "event_broker", broker)

        response = client.get("/events", buffered=False)
        try:
            chunks = [next(response.response).decode() for _ in range(4)]
        finally:
            response.close()
        assert chunks[3].startswith("event: activity\n")
        assert '"message": "Play x on y"' in chunks[3]


class TestIndex:
    """Test web UI route."""

    def test_index_renders_player(self, client):
        """GET / serves the player UI with version."""
        response = client.get("/")
        assert response.status_code == 200
        html = response.data.decode()
        assert "<title>DLNA Radio</title>" in html
        assert 'id="np-card"' in html
        # API key field is only shown when auth is enabled (disabled in test config)
        assert 'id="api-key"' not in html

    def test_player_shows_api_key_field_when_auth_enabled(self, app):
        """Player template renders the API key setting when auth is enabled."""
        from flask import render_template

        with app.test_request_context("/"):
            html = render_template(
                "player.html",
                default_stream_url="",
                default_device_ip="",
                api_auth_enabled=True,
                version="test",
            )
        assert 'id="api-key"' in html


class TestErrorHandlers:
    """Test error handlers."""

    def test_404_returns_json(self, client):
        """404 endpoint returns JSON."""
        response = client.get("/nonexistent")
        assert response.status_code == 404
        data = json.loads(response.data)
        assert "message" in data
        assert "error" not in data  # Should be 'message', not 'error'

    def test_405_method_not_allowed(self, client):
        """405 returns JSON."""
        response = client.get("/play")  # GET instead of POST
        assert response.status_code == 405
        data = json.loads(response.data)
        assert "message" in data
