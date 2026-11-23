"""Tests for Server-Sent Events broker and state monitor."""

import json
import time

from app.events import EventBroker, StateMonitor, format_sse, sse_stream


def _parse(message: str) -> tuple[str, dict]:
    lines = dict(line.split(": ", 1) for line in message.strip().split("\n"))
    return lines["event"], json.loads(lines["data"])


class TestEventBroker:
    def test_publish_reaches_all_subscribers(self):
        broker = EventBroker()
        q1, q2 = broker.subscribe(), broker.subscribe()
        assert broker.publish("status", {"a": 1})
        assert _parse(q1.get_nowait()) == ("status", {"a": 1})
        assert _parse(q2.get_nowait()) == ("status", {"a": 1})

    def test_only_if_changed_skips_duplicates(self):
        broker = EventBroker()
        q = broker.subscribe()
        assert broker.publish("status", {"a": 1}, only_if_changed=True)
        assert not broker.publish("status", {"a": 1}, only_if_changed=True)
        assert broker.publish("status", {"a": 2}, only_if_changed=True)
        assert q.qsize() == 2

    def test_subscriber_limit(self):
        broker = EventBroker(max_subscribers=2)
        assert broker.subscribe() is not None
        assert broker.subscribe() is not None
        assert broker.subscribe() is None

    def test_full_queue_drops_events_without_blocking(self):
        broker = EventBroker(queue_size=1)
        q = broker.subscribe()
        broker.publish("status", {"n": 1})
        broker.publish("status", {"n": 2})  # must not block or raise
        assert q.qsize() == 1

    def test_unsubscribe(self):
        broker = EventBroker()
        q = broker.subscribe()
        broker.unsubscribe(q)
        assert broker.subscriber_count == 0


class TestSseStream:
    def test_initial_snapshot_then_events_and_cleanup(self):
        broker = EventBroker()
        q = broker.subscribe()
        gen = sse_stream(broker, q, [("status", {"s": 0})], keepalive_seconds=0.01)
        assert next(gen).startswith("retry:")
        assert _parse(next(gen)) == ("status", {"s": 0})
        assert next(gen) == ": keepalive\n\n"
        broker.publish("status", {"s": 1})
        assert _parse(next(gen)) == ("status", {"s": 1})
        gen.close()
        assert broker.subscriber_count == 0

    def test_format_sse(self):
        assert format_sse("x", "{}") == "event: x\ndata: {}\n\n"


class TestStateMonitor:
    def test_publishes_changes_and_stops_without_subscribers(self):
        broker = EventBroker()
        q = broker.subscribe()
        value = {"n": 0}
        monitor = StateMonitor(broker, lambda: dict(value), interval=0.01)
        monitor.ensure_running()
        thread = monitor._thread
        assert _parse(q.get(timeout=1)) == ("status", {"n": 0})
        value["n"] = 1
        assert _parse(q.get(timeout=1)) == ("status", {"n": 1})

        broker.unsubscribe(q)
        thread.join(timeout=1)
        assert not thread.is_alive()
        assert monitor._thread is None

    def test_restarts_for_new_subscriber(self):
        broker = EventBroker()
        monitor = StateMonitor(broker, lambda: {"x": 1}, interval=0.01)
        q = broker.subscribe()
        monitor.ensure_running()
        q.get(timeout=1)
        broker.unsubscribe(q)
        time.sleep(0.1)
        q2 = broker.subscribe()
        broker._last.clear()  # force re-publish of the unchanged state
        monitor.ensure_running()
        assert _parse(q2.get(timeout=1)) == ("status", {"x": 1})
        broker.unsubscribe(q2)
