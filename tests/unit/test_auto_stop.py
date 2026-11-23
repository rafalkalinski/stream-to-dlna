"""Tests for the playback watchdog (auto-stop when nobody listens)."""

import threading
from unittest.mock import Mock

import pytest

import app.main as main
from app.events import EventBroker


class FakeStreamer:
    def __init__(self, active_clients=0, transcoding=True):
        if transcoding:
            self.active_clients = active_clients
        self.running = True
        self.stop = Mock(side_effect=self._stop)

    def _stop(self):
        self.running = False

    def is_running(self):
        return self.running


@pytest.mark.parametrize(
    "listeners, state, idle",
    [
        (0, "NO_MEDIA_PRESENT", True),
        (0, "STOPPED", True),
        (0, None, True),  # device powered off / unreachable
        (0, "PLAYING", False),
        (0, "TRANSITIONING", False),
        (1, "STOPPED", False),  # someone still pulls the stream
    ],
)
def test_idle_transcoding(listeners, state, idle):
    assert main._playback_idle(FakeStreamer(active_clients=listeners), state) is idle


@pytest.mark.parametrize(
    "state, idle",
    [("STOPPED", True), ("NO_MEDIA_PRESENT", True), ("PLAYING", False), (None, False)],
)
def test_idle_passthrough(state, idle):
    assert main._playback_idle(FakeStreamer(transcoding=False), state) is idle


@pytest.fixture
def fast_watchdog(monkeypatch):
    broker = EventBroker()
    monkeypatch.setattr(main, "event_broker", broker)
    monkeypatch.setattr(main, "WATCHDOG_INTERVAL", 0.01)
    monkeypatch.setattr(main, "AUTO_STOP_AFTER", 0.05)
    monkeypatch.setattr(main, "_watchdog_thread", None)
    monkeypatch.setattr(main, "playback_info", {"url": "http://x"})
    return broker


def _run_watchdog(timeout=2.0):
    t = threading.Thread(target=main._playback_watchdog, daemon=True)
    t.start()
    t.join(timeout)
    return t


def test_auto_stops_when_speaker_is_off(monkeypatch, fast_watchdog):
    fake = FakeStreamer(active_clients=0)
    monkeypatch.setattr(main, "streamer", fake)
    client = Mock()
    client.get_transport_info.return_value = {"state": "NO_MEDIA_PRESENT"}
    monkeypatch.setattr(main, "dlna_client", client)

    t = _run_watchdog()
    assert not t.is_alive()
    fake.stop.assert_called_once()
    assert main.streamer is None and main.playback_info is None
    client.stop.assert_not_called()  # never stop the device itself
    (activity,) = fast_watchdog.activity_history()
    assert activity["action"] == "auto-stop" and activity["client"] == "server"


def test_keeps_playing_while_someone_listens(monkeypatch, fast_watchdog):
    fake = FakeStreamer(active_clients=1)
    monkeypatch.setattr(main, "streamer", fake)
    client = Mock()
    client.get_transport_info.return_value = {"state": "STOPPED"}
    monkeypatch.setattr(main, "dlna_client", client)

    t = threading.Thread(target=main._playback_watchdog, daemon=True)
    t.start()
    t.join(0.3)
    assert t.is_alive()  # still watching
    fake.stop.assert_not_called()
    fake.running = False  # user stopped playback -> watchdog exits
    t.join(1)
    assert not t.is_alive()
    assert fast_watchdog.activity_history() == []


def test_audio_streamer_counts_listeners():
    from app.streamer import AudioStreamer

    s = AudioStreamer(stream_url="http://x", port=0)
    assert s.active_clients == 0
    s.client_connected()
    s.client_connected()
    s.client_disconnected()
    assert s.active_clients == 1
    s.client_disconnected()
    s.client_disconnected()  # never below zero
    assert s.active_clients == 0
