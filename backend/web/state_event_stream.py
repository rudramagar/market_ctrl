import json

from backend.events.state_event_bus import (
    StateEventBus,
    StateEventHistoryGapError,
)


class StateEventStreamError(Exception):
    """State event stream operation failed."""


class StateEventCursorError(
    StateEventStreamError
):
    """
    The requested event cursor cannot be resumed.

    This commonly happens when the backend restarted
    and its process-local event IDs started again.
    """

    def __init__(
        self,
        requested_event_id,
        latest_event_id,
    ):
        self.requested_event_id = (
            requested_event_id
        )
        self.latest_event_id = (
            latest_event_id
        )

        super().__init__(
            "state event cursor is ahead: "
            "requested_after=%d latest_available=%d"
            % (
                requested_event_id,
                latest_event_id,
            )
        )


class StateEventStream:
    """
    Convert StateEventBus events into Server-Sent Events.

    The browser receives one JSON event for every
    published state change. Keep-alive comments prevent
    idle HTTP connections from being closed.
    """

    def __init__(
        self,
        event_bus,
        heartbeat_seconds=15.0,
        batch_size=100,
    ):
        if not isinstance(
            event_bus,
            StateEventBus,
        ):
            raise TypeError(
                "event bus must be a StateEventBus"
            )

        heartbeat_seconds = float(
            heartbeat_seconds
        )

        if heartbeat_seconds < 0:
            raise ValueError(
                "heartbeat interval cannot be negative"
            )

        if (
            not isinstance(batch_size, int)
            or isinstance(batch_size, bool)
        ):
            raise TypeError(
                "batch size must be an integer"
            )

        if batch_size < 1:
            raise ValueError(
                "batch size must be at least 1"
            )

        self.event_bus = event_bus
        self.heartbeat_seconds = (
            heartbeat_seconds
        )
        self.batch_size = batch_size

    def validate_after_event_id(
        self,
        after_event_id,
    ):
        """
        Validate a browser reconnect cursor.

        None means the stream should begin after the
        newest currently published event.
        """

        if after_event_id is None:
            return None

        after_event_id = (
            self._validate_event_id(
                after_event_id
            )
        )

        latest_event_id = (
            self.event_bus.latest_event_id
        )

        if after_event_id > latest_event_id:
            raise StateEventCursorError(
                requested_event_id=(
                    after_event_id
                ),
                latest_event_id=(
                    latest_event_id
                ),
            )

        # This also detects an event that has already
        # been removed from the bounded history.
        self.event_bus.get_events(
            after_event_id=after_event_id,
            limit=1,
        )

        return after_event_id

    def iter_events(
        self,
        after_event_id=None,
    ):
        """
        Yield SSE-formatted text until the bus closes.

        When no cursor is supplied, only events
        published after subscription are returned.
        """

        after_event_id = (
            self.validate_after_event_id(
                after_event_id
            )
        )

        subscription = (
            self.event_bus.subscribe(
                after_event_id=after_event_id
            )
        )

        try:
            while True:
                events = (
                    subscription.next_events(
                        timeout_seconds=(
                            self.heartbeat_seconds
                        ),
                        limit=self.batch_size,
                    )
                )

                if events:
                    for published_event in events:
                        yield self.format_event(
                            published_event
                        )

                    continue

                if self.event_bus.closed:
                    break

                yield self.format_keep_alive()

        finally:
            subscription.close()

    @staticmethod
    def format_event(
        published_event,
    ):
        """
        Format one published event according to SSE.

        The event ID is used by the browser as its
        Last-Event-ID reconnect cursor.
        """

        payload = json.dumps(
            published_event.to_dict(),
            separators=(
                ",",
                ":",
            ),
            sort_keys=True,
        )

        return (
            "id: %d\n"
            "event: state\n"
            "data: %s\n"
            "\n"
            % (
                published_event.event_id,
                payload,
            )
        )

    @staticmethod
    def format_keep_alive():
        """
        Return an SSE comment.

        Comments are ignored by EventSource clients but
        keep proxies and load balancers from considering
        the connection idle.
        """

        return ": keep-alive\n\n"

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
