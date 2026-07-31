import time
from collections import deque
from threading import (
    Condition,
    RLock,
)

from backend.events.state_event import (
    StateEvent,
)


class StateEventBusError(Exception):
    """State event bus operation failed."""


class StateEventHistoryGapError(
    StateEventBusError
):
    """
    Requested events are no longer available.

    The consumer should reload the complete state
    through the REST API and start a new subscription.
    """

    def __init__(
        self,
        requested_event_id,
        oldest_event_id,
    ):
        self.requested_event_id = (
            requested_event_id
        )
        self.oldest_event_id = (
            oldest_event_id
        )

        super().__init__(
            "state event history gap: "
            "requested_after=%d oldest_available=%d"
            % (
                requested_event_id,
                oldest_event_id,
            )
        )


class PublishedStateEvent:
    """
    StateEvent with an event-bus sequence number.

    event_id is independent from the DROP matching
    engine sequence contained in StateEvent.sequence.
    """

    __slots__ = (
        "_event_id",
        "_event",
    )

    def __init__(
        self,
        event_id,
        event,
    ):
        if (
            not isinstance(event_id, int)
            or isinstance(event_id, bool)
        ):
            raise TypeError(
                "event ID must be an integer"
            )

        if event_id < 1:
            raise ValueError(
                "event ID must be at least 1"
            )

        if not isinstance(event, StateEvent):
            raise TypeError(
                "event must be a StateEvent"
            )

        self._event_id = event_id
        self._event = event

    @property
    def event_id(self):
        return self._event_id

    @property
    def event(self):
        return self._event

    def to_dict(self):
        result = {
            "event_id": self.event_id,
        }

        result.update(
            self.event.to_dict()
        )

        return result

    def __repr__(self):
        return (
            "PublishedStateEvent("
            "event_id=%r, "
            "event=%r"
            ")"
            % (
                self.event_id,
                self.event,
            )
        )


class StateEventSubscription:
    """
    Cursor-based subscription to StateEventBus.

    Each subscription remembers the last event it
    delivered. It does not create a worker thread.
    """

    def __init__(
        self,
        event_bus,
        after_event_id,
    ):
        if not isinstance(
            event_bus,
            StateEventBus,
        ):
            raise TypeError(
                "event bus must be a StateEventBus"
            )

        self._event_bus = event_bus
        self._after_event_id = (
            self._validate_event_id(
                after_event_id
            )
        )
        self._closed = False
        self._lock = RLock()

    @property
    def after_event_id(self):
        with self._lock:
            return self._after_event_id

    @property
    def closed(self):
        with self._lock:
            return self._closed

    def next_events(
        self,
        timeout_seconds=None,
        limit=None,
    ):
        """
        Wait for and return newly published events.

        The cursor advances to the final returned
        event ID.
        """

        with self._lock:
            if self._closed:
                return []

            after_event_id = (
                self._after_event_id
            )

        events = (
            self._event_bus.wait_for_events(
                after_event_id=after_event_id,
                timeout_seconds=timeout_seconds,
                limit=limit,
            )
        )

        if not events:
            return []

        with self._lock:
            if self._closed:
                return []

            self._after_event_id = (
                events[-1].event_id
            )

        return events

    def close(self):
        with self._lock:
            self._closed = True

    @staticmethod
    def _validate_event_id(
        event_id,
    ):
        if (
            not isinstance(event_id, int)
            or isinstance(event_id, bool)
        ):
            raise TypeError(
                "event ID must be an integer"
            )

        if event_id < 0:
            raise ValueError(
                "event ID cannot be negative"
            )

        return event_id


class StateEventBus:
    """
    Thread-safe state event publisher.

    A bounded history allows REST/SSE consumers to
    retrieve events published after a known event ID.
    """

    def __init__(
        self,
        history_size=1000,
    ):
        history_size = int(
            history_size
        )

        if history_size < 1:
            raise ValueError(
                "history size must be at least 1"
            )

        self._history_size = history_size
        self._history = deque(
            maxlen=history_size
        )

        self._lock = RLock()
        self._condition = Condition(
            self._lock
        )

        self._latest_event_id = 0
        self._closed = False

    @property
    def history_size(self):
        return self._history_size

    @property
    def latest_event_id(self):
        with self._lock:
            return self._latest_event_id

    @property
    def oldest_event_id(self):
        with self._lock:
            if not self._history:
                return None

            return self._history[0].event_id

    @property
    def closed(self):
        with self._lock:
            return self._closed

    def publish(self, event):
        """
        Publish one StateEvent.

        Returns the PublishedStateEvent containing
        the event bus ID.
        """

        if not isinstance(event, StateEvent):
            raise TypeError(
                "event must be a StateEvent"
            )

        with self._condition:
            if self._closed:
                raise StateEventBusError(
                    "state event bus is closed"
                )

            self._latest_event_id += 1

            published_event = (
                PublishedStateEvent(
                    event_id=(
                        self._latest_event_id
                    ),
                    event=event,
                )
            )

            self._history.append(
                published_event
            )

            self._condition.notify_all()

            return published_event

    def subscribe(
        self,
        after_event_id=None,
    ):
        """
        Create a cursor-based subscription.

        When after_event_id is omitted, the
        subscription starts after the newest event
        and receives only future events.
        """

        with self._lock:
            if after_event_id is None:
                after_event_id = (
                    self._latest_event_id
                )

            else:
                after_event_id = (
                    self._validate_event_id(
                        after_event_id
                    )
                )

        return StateEventSubscription(
            event_bus=self,
            after_event_id=after_event_id,
        )

    def get_events(
        self,
        after_event_id=0,
        limit=None,
    ):
        """Return available events after an event ID."""

        after_event_id = (
            self._validate_event_id(
                after_event_id
            )
        )
        limit = self._validate_limit(
            limit
        )

        with self._lock:
            return self._get_events_locked(
                after_event_id=after_event_id,
                limit=limit,
            )

    def wait_for_events(
        self,
        after_event_id=0,
        timeout_seconds=None,
        limit=None,
    ):
        """
        Block until events are available or timeout.

        Returns an empty list when the timeout expires
        or when the bus closes without newer events.
        """

        after_event_id = (
            self._validate_event_id(
                after_event_id
            )
        )
        limit = self._validate_limit(
            limit
        )
        timeout_seconds = (
            self._validate_timeout(
                timeout_seconds
            )
        )

        deadline = None

        if timeout_seconds is not None:
            deadline = (
                time.monotonic()
                + timeout_seconds
            )

        with self._condition:
            while True:
                events = (
                    self._get_events_locked(
                        after_event_id=(
                            after_event_id
                        ),
                        limit=limit,
                    )
                )

                if events:
                    return events

                if self._closed:
                    return []

                if deadline is None:
                    self._condition.wait()
                    continue

                remaining = (
                    deadline
                    - time.monotonic()
                )

                if remaining <= 0:
                    return []

                self._condition.wait(
                    remaining
                )

    def clear(self):
        """
        Clear retained history.

        Event IDs remain monotonic and are not reset.
        """

        with self._condition:
            self._history.clear()
            self._condition.notify_all()

    def close(self):
        """Close the bus and wake waiting consumers."""

        with self._condition:
            if self._closed:
                return

            self._closed = True
            self._condition.notify_all()

    def _get_events_locked(
        self,
        after_event_id,
        limit,
    ):
        if self._history:
            oldest_event_id = (
                self._history[0].event_id
            )

            if (
                after_event_id
                < oldest_event_id - 1
            ):
                raise StateEventHistoryGapError(
                    requested_event_id=(
                        after_event_id
                    ),
                    oldest_event_id=(
                        oldest_event_id
                    ),
                )

        events = [
            event
            for event in self._history
            if event.event_id
            > after_event_id
        ]

        if limit is not None:
            events = events[:limit]

        return events

    @staticmethod
    def _validate_event_id(
        event_id,
    ):
        if (
            not isinstance(event_id, int)
            or isinstance(event_id, bool)
        ):
            raise TypeError(
                "event ID must be an integer"
            )

        if event_id < 0:
            raise ValueError(
                "event ID cannot be negative"
            )

        return event_id

    @staticmethod
    def _validate_limit(limit):
        if limit is None:
            return None

        if (
            not isinstance(limit, int)
            or isinstance(limit, bool)
        ):
            raise TypeError(
                "limit must be an integer"
            )

        if limit < 1:
            raise ValueError(
                "limit must be at least 1"
            )

        return limit

    @staticmethod
    def _validate_timeout(
        timeout_seconds,
    ):
        if timeout_seconds is None:
            return None

        timeout_seconds = float(
            timeout_seconds
        )

        if timeout_seconds < 0:
            raise ValueError(
                "timeout cannot be negative"
            )

        return timeout_seconds
