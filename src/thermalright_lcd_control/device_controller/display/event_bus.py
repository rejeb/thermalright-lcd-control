# SPDX-License-Identifier: Apache-2.0
import logging
import threading
from collections.abc import Callable
from typing import Any

log = logging.getLogger(__name__)


class Topic:
    METRICS = "metrics"
    CONFIG_RELOAD = "config.reload"
    DEVICES_CHANGED = "devices.changed"


class EventBus:
    """Thread-safe synchronous pub/sub bus.

    Callbacks run on the thread that calls publish(). Subscribers doing
    heavy work should schedule their own task; this bus only delivers the
    signal.
    """

    def __init__(self) -> None:
        self._subs: dict[str, list[Callable[..., Any]]] = {}
        self._lock = threading.Lock()

    def subscribe(self, topic: str, callback: Callable[..., Any]) -> None:
        with self._lock:
            self._subs.setdefault(topic, []).append(callback)

    def unsubscribe(self, topic: str, callback: Callable[..., Any]) -> None:
        with self._lock:
            if topic in self._subs:
                try:
                    self._subs[topic].remove(callback)
                except ValueError:
                    pass
                if not self._subs[topic]:
                    del self._subs[topic]

    def publish(self, topic: str, *args: Any, **kwargs: Any) -> None:
        with self._lock:
            callbacks = list(self._subs.get(topic, []))
        for cb in callbacks:
            try:
                cb(*args, **kwargs)
            except Exception:
                log.exception("EventBus callback error on topic %r", topic)
