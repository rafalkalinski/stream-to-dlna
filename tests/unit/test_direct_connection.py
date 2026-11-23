"""Tests for SSDPDiscovery.try_direct_connection (add speaker by IP)."""

import time
from contextlib import nullcontext
from unittest.mock import Mock

import app.discovery as discovery
from app.discovery import SSDPDiscovery


def test_unreachable_host_fails_fast_without_http(monkeypatch):
    def refuse(addr, timeout):
        raise OSError("unreachable")

    get = Mock()
    monkeypatch.setattr(discovery.socket, "create_connection", refuse)
    monkeypatch.setattr(discovery.requests, "get", get)

    start = time.monotonic()
    assert SSDPDiscovery.try_direct_connection("10.0.0.1") is None
    assert time.monotonic() - start < 1
    get.assert_not_called()


def test_only_open_ports_are_queried(monkeypatch):
    def connect(addr, timeout):
        if addr[1] == 9197:
            return nullcontext()
        raise OSError("closed")

    def fake_get(url, timeout):
        response = Mock(status_code=404, headers={})
        if url.endswith(":9197/dmr"):
            response.status_code = 200
            response.headers = {"Content-Type": "text/xml"}
        return response

    get = Mock(side_effect=fake_get)
    monkeypatch.setattr(discovery.socket, "create_connection", connect)
    monkeypatch.setattr(discovery.requests, "get", get)
    monkeypatch.setattr(
        SSDPDiscovery, "_fetch_device_info", staticmethod(lambda loc: {"ip": "1.2.3.4", "loc": loc})
    )

    device = SSDPDiscovery.try_direct_connection("1.2.3.4")
    assert device == {"ip": "1.2.3.4", "loc": "http://1.2.3.4:9197/dmr"}
    assert all(":9197/" in call.args[0] for call in get.call_args_list)


def test_total_time_is_bounded(monkeypatch):
    monkeypatch.setattr(discovery.socket, "create_connection", lambda addr, timeout: nullcontext())
    get = Mock()
    monkeypatch.setattr(discovery.requests, "get", get)

    assert SSDPDiscovery.try_direct_connection("1.2.3.4", max_total=0) is None
    get.assert_not_called()
