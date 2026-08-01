#!/usr/bin/env python3

import json

from backend.events.state_event import (
    EVENT_UPDATED,
    StateEvent,
)
from backend.events.state_event_bus import (
    StateEventBus,
)
from backend.web.http_app import (
    create_http_app,
)
from backend.web.state_event_stream import (
    StateEventStream,
)


class FakeStateApi:
    pass


def create_event(
    sequence,
    old_state,
    new_state,
):
    return StateEvent(
        event_type=EVENT_UPDATED,
        entity_type="user",
        entity_id=402,
        sequence=sequence,
        timestamp_ns=(
            sequence * 1000
        ),
        message_type=(
            "UserStatusMessage"
        ),
        record={
            "user_id": 402,
            "state": new_state,
            "state_sequence": sequence,
        },
        changed_fields={
            "state": {
                "old": old_state,
                "new": new_state,
            },
        },
    )


def parse_sse(text):
    result = {}

    for line in text.splitlines():
        if line.startswith("id: "):
            result["id"] = int(
                line[4:]
            )

        elif line.startswith("event: "):
            result["event"] = line[7:]

        elif line.startswith("data: "):
            result["data"] = json.loads(
                line[6:]
            )

    return result


def read_first_chunk(response):
    chunk = next(
        response.response
    )

    if isinstance(chunk, bytes):
        return chunk.decode(
            "utf-8"
        )

    return chunk


def test_live_event_endpoint():
    event_bus = StateEventBus()

    published = event_bus.publish(
        create_event(
            sequence=1001,
            old_state="A",
            new_state="S",
        )
    )

    event_stream = StateEventStream(
        event_bus=event_bus,
        heartbeat_seconds=1.0,
    )

    app = create_http_app(
        state_api=FakeStateApi(),
        state_event_stream=event_stream,
    )

    app.testing = True
    client = app.test_client()

    response = client.get(
        "/api/v1/events?after_event_id=0",
        buffered=False,
    )

    try:
        if response.status_code != 200:
            raise AssertionError(
                "SSE status mismatch"
            )

        if (
            response.mimetype
            != "text/event-stream"
        ):
            raise AssertionError(
                "SSE content type mismatch"
            )

        if (
            response.headers.get(
                "X-Accel-Buffering"
            )
            != "no"
        ):
            raise AssertionError(
                "SSE buffering header mismatch"
            )

        parsed = parse_sse(
            read_first_chunk(
                response
            )
        )

        if (
            parsed["id"]
            != published.event_id
        ):
            raise AssertionError(
                "SSE HTTP event ID mismatch"
            )

        if parsed["event"] != "state":
            raise AssertionError(
                "SSE HTTP event name mismatch"
            )

        if (
            parsed["data"]["record"]
            ["state"]
            != "S"
        ):
            raise AssertionError(
                "SSE HTTP state mismatch"
            )

    finally:
        response.close()

    print(
        "HTTP SSE live event: PASSED"
    )


def test_last_event_id_header():
    event_bus = StateEventBus()

    first = event_bus.publish(
        create_event(
            sequence=1101,
            old_state="A",
            new_state="S",
        )
    )

    second = event_bus.publish(
        create_event(
            sequence=1102,
            old_state="S",
            new_state="A",
        )
    )

    event_stream = StateEventStream(
        event_bus=event_bus,
    )

    app = create_http_app(
        state_api=FakeStateApi(),
        state_event_stream=event_stream,
    )

    app.testing = True
    client = app.test_client()

    response = client.get(
        "/api/v1/events",
        headers={
            "Last-Event-ID": str(
                first.event_id
            ),
        },
        buffered=False,
    )

    try:
        parsed = parse_sse(
            read_first_chunk(
                response
            )
        )

        if parsed["id"] != second.event_id:
            raise AssertionError(
                "Last-Event-ID resume mismatch"
            )

        if (
            parsed["data"]["record"]
            ["state"]
            != "A"
        ):
            raise AssertionError(
                "resumed event state mismatch"
            )

    finally:
        response.close()

    print(
        "HTTP SSE reconnect cursor: PASSED"
    )


def test_history_gap_reset():
    event_bus = StateEventBus(
        history_size=2
    )

    event_bus.publish(
        create_event(
            sequence=1201,
            old_state="A",
            new_state="S",
        )
    )

    event_bus.publish(
        create_event(
            sequence=1202,
            old_state="S",
            new_state="A",
        )
    )

    event_bus.publish(
        create_event(
            sequence=1203,
            old_state="A",
            new_state="S",
        )
    )

    event_stream = StateEventStream(
        event_bus=event_bus,
    )

    app = create_http_app(
        state_api=FakeStateApi(),
        state_event_stream=event_stream,
    )

    app.testing = True
    client = app.test_client()

    response = client.get(
        "/api/v1/events?after_event_id=0"
    )

    parsed = parse_sse(
        response.get_data(
            as_text=True
        )
    )

    if parsed["event"] != "reset":
        raise AssertionError(
            "history gap reset missing"
        )

    if (
        parsed["data"]["reason"]
        != "history_gap"
    ):
        raise AssertionError(
            "history gap reason mismatch"
        )

    if (
        parsed["data"]["oldest_event_id"]
        != 2
    ):
        raise AssertionError(
            "oldest event ID mismatch"
        )

    print(
        "HTTP SSE history reset: PASSED"
    )


def test_cursor_ahead_reset():
    event_bus = StateEventBus()

    event_bus.publish(
        create_event(
            sequence=1301,
            old_state="A",
            new_state="S",
        )
    )

    event_stream = StateEventStream(
        event_bus=event_bus,
    )

    app = create_http_app(
        state_api=FakeStateApi(),
        state_event_stream=event_stream,
    )

    app.testing = True
    client = app.test_client()

    response = client.get(
        "/api/v1/events?after_event_id=99"
    )

    parsed = parse_sse(
        response.get_data(
            as_text=True
        )
    )

    if parsed["event"] != "reset":
        raise AssertionError(
            "cursor reset missing"
        )

    if (
        parsed["data"]["reason"]
        != "cursor_ahead"
    ):
        raise AssertionError(
            "cursor reset reason mismatch"
        )

    if (
        parsed["data"]["latest_event_id"]
        != 1
    ):
        raise AssertionError(
            "latest event ID mismatch"
        )

    print(
        "HTTP SSE restart reset: PASSED"
    )


def test_invalid_cursor():
    event_bus = StateEventBus()

    event_stream = StateEventStream(
        event_bus=event_bus,
    )

    app = create_http_app(
        state_api=FakeStateApi(),
        state_event_stream=event_stream,
    )

    app.testing = True
    client = app.test_client()

    response = client.get(
        "/api/v1/events"
        "?after_event_id=invalid"
    )

    if response.status_code != 400:
        raise AssertionError(
            "invalid cursor status mismatch"
        )

    payload = response.get_json()

    if (
        payload["error"]["code"]
        != "bad_request"
    ):
        raise AssertionError(
            "invalid cursor response mismatch"
        )

    print(
        "HTTP SSE invalid cursor: PASSED"
    )


def main():
    test_live_event_endpoint()
    test_last_event_id_header()
    test_history_gap_reset()
    test_cursor_ahead_reset()
    test_invalid_cursor()

    print(
        "HTTP SSE test: PASSED"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
