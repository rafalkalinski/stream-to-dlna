"""Server-Sent Events: push playback/device state changes to connected web clients."""

import json
import logging
import queue
import threading
from collections.abc import Callable, Iterator

logger = logging.getLogger(__name__)


class EventBroker:
    """
    Fan-out of events to SSE subscribers.

    Each subscriber gets its own bounded queue. A subscriber that stops reading
    (e.g. a dead connection) has events dropped instead of blocking publishers.
    """

    def __init__(self, max_subscribers: int = 10, queue_size: int = 20):
        self.max_subscribers = max_subscribers
        self.queue_size = queue_size
        self._subscribers: list[queue.Queue] = []
        self._lock = threading.Lock()
        self._last: dict[str, str] = {}  # event name -> last published payload (JSON)

    @property
    def subscriber_count(self) -> int:
        with self._lock:
            return len(self._subscribers)

    def subscribe(self) -> queue.Queue | None:
        """Register a subscriber. Returns None when the subscriber limit is reached."""
        with self._lock:
            if len(self._subscribers) >= self.max_subscribers:
                return None
            q: queue.Queue = queue.Queue(maxsize=self.queue_size)
            self._subscribers.append(q)
            return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)

    def publish(self, event: str, data, only_if_changed: bool = False) -> bool:
        """
        Send an event to all subscribers.

        Args:
            event: SSE event name (e.g. "status", "devices")
            data: JSON-serialisable payload
            only_if_changed: skip publishing when the payload equals the last one sent

        Returns:
            True if the event was published
        """
        payload = json.dumps(data, sort_keys=True)
        with self._lock:
            if only_if_changed and self._last.get(event) == payload:
                return False
            self._last[event] = payload
            subscribers = list(self._subscribers)
        message = format_sse(event, payload)
        for q in subscribers:
            try:
                q.put_nowait(message)
            except queue.Full:
                logger.debug("SSE subscriber queue full - dropping event")
        return True


def format_sse(event: str, payload: str) -> str:
    """Format one SSE message (payload must not contain newlines - json.dumps guarantees that)."""
    return f"event: {event}\ndata: {payload}\n\n"


def sse_stream(
    broker: EventBroker,
    q: queue.Queue,
    initial: list[tuple[str, object]],
    keepalive_seconds: float = 15.0,
) -> Iterator[str]:
    """
    Generator for an SSE response.

    Sends the initial snapshot, then forwards published events. A comment line is
    sent every `keepalive_seconds` so proxies keep the connection open and dead
    clients are detected (the write fails and the generator is closed).
    """
    try:
        yield "retry: 3000\n\n"
        for event, data in initial:
            yield format_sse(event, json.dumps(data, sort_keys=True))
        while True:
            try:
                yield q.get(timeout=keepalive_seconds)
            except queue.Empty:
                yield ": keepalive\n\n"
    finally:
        broker.unsubscribe(q)


class StateMonitor:
    """
    Background thread that periodically builds the current state and publishes
    it when it changes. Runs only while there are SSE subscribers, so the DLNA
    device is queried once per interval regardless of how many clients are open.
    """

    def __init__(
        self,
        broker: EventBroker,
        build_status: Callable[[], dict],
        interval: float = 3.0,
    ):
        self.broker = broker
        self.build_status = build_status
        self.interval = interval
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._wake = threading.Event()

    def ensure_running(self) -> None:
        """Start the monitor thread if it is not running (call after subscribing)."""
        with self._lock:
            if self._thread is not None:
                return
            self._thread = threading.Thread(target=self._run, name="sse-state-monitor", daemon=True)
            self._thread.start()

    def poke(self) -> None:
        """Re-check state now instead of waiting for the next interval."""
        self._wake.set()

    def _run(self) -> None:
        logger.info("SSE state monitor started")
        while True:
            # Exit decision and _thread reset happen under the same lock as
            # ensure_running(), so a subscriber arriving concurrently either keeps
            # this thread alive or starts a new one - never neither.
            with self._lock:
                if self.broker.subscriber_count == 0:
                    self._thread = None
                    logger.info("SSE state monitor stopped (no subscribers)")
                    return
            try:
                self.broker.publish("status", self.build_status(), only_if_changed=True)
            except Exception as e:
                logger.debug(f"State monitor error: {e}")
            self._wake.wait(self.interval)
            self._wake.clear()
