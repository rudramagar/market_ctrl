#!/usr/bin/env python3

import json

from backend.events.state_event import (
    EVENT_UPDATED,
    StateEvent,
)
from backend.events.state_event_bus import (
    StateEventBus,
    StateEventHistoryGapError,
)
from backend.web.state_event_stream import (
    StateEventCursorError,
    StateEventStream,
)


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
            "user_name": "TX99900C",
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


def parse_sse_event(
    text,
):
    parsed = {}

    for line in text.splitlines():
        if line.startswith("id: "):
            parsed["id"] = int(
                line[4:]
            )

        elif line.startswith("event: "):
            parsed["event"] = line[7:]

        elif line.startswith("data: "):
            parsed["data"] = json.loads(
                line[6:]
            )

    return parsed


def test_event_format():
    event_bus = StateEventBus()

    published = event_bus.publish(
        create_event(
            sequence=9001,
            old_state="A",
            new_state="S",
        )
    )

    stream = StateEventStream(
        event_bus
    )

    text = stream.format_event(
        published
    )

    parsed = parse_sse_event(
        text
    )

    if parsed["id"] != 1:
        raise AssertionError(
            "SSE event ID mismatch"
        )

    if parsed["event"] != "state":
        raise AssertionError(
            "SSE event name mismatch"
        )

    if (
        parsed["data"]["entity_id"]
        != 402
    ):
        raise AssertionError(
            "SSE entity ID mismatch"
        )

    if (
        parsed["data"]["record"]["state"]
        != "S"
    ):
        raise AssertionError(
            "SSE record state mismatch"
        )

    if (
        parsed["data"]["changed_fields"]
        ["state"]
        != {
            "old": "A",
            "new": "S",
        }
    ):
        raise AssertionError(
            "SSE changed fields mismatch"
        )

    print(
        "SSE event formatting: PASSED"
    )


def test_live_stream():
    event_bus = StateEventBus()

    first = event_bus.publish(
        create_event(
            sequence=9101,
            old_state="A",
            new_state="S",
        )
    )

    stream = StateEventStream(
        event_bus=event_bus,
        heartbeat_seconds=1.0,
    )

    iterator = stream.iter_events(
        after_event_id=first.event_id
    )

    second = event_bus.publish(
        create_event(
            sequence=9102,
            old_state="S",
            new_state="A",
        )
    )

    text = next(iterator)
    parsed = parse_sse_event(
        text
    )

    if parsed["id"] != second.event_id:
        raise AssertionError(
            "live SSE event ID mismatch"
        )

    if (
        parsed["data"]["record"]["state"]
        != "A"
    ):
        raise AssertionError(
            "live SSE state mismatch"
        )

    iterator.close()

    print(
        "SSE live event delivery: PASSED"
    )


def test_keep_alive():
    event_bus = StateEventBus()

    stream = StateEventStream(
        event_bus=event_bus,
        heartbeat_seconds=0,
    )

    iterator = stream.iter_events()

    text = next(iterator)

    if text != ": keep-alive\n\n":
        raise AssertionError(
            "SSE keep-alive mismatch: %r"
            % text
        )

    iterator.close()

    print(
        "SSE keep-alive: PASSED"
    )


def test_history_gap():
    event_bus = StateEventBus(
        history_size=2
    )

    event_bus.publish(
        create_event(
            sequence=9201,
            old_state="A",
            new_state="S",
        )
    )

    event_bus.publish(
        create_event(
            sequence=9202,
            old_state="S",
            new_state="A",
        )
    )

    event_bus.publish(
        create_event(
            sequence=9203,
            old_state="A",
            new_state="S",
        )
    )

    stream = StateEventStream(
        event_bus
    )

    try:
        stream.validate_after_event_id(
            0
        )

    except StateEventHistoryGapError as exc:
        if exc.oldest_event_id != 2:
            raise AssertionError(
                "history gap details mismatch"
            )

    else:
        raise AssertionError(
            "SSE history gap was not detected"
        )

    print(
        "SSE history gap detection: PASSED"
    )


def test_cursor_ahead():
    event_bus = StateEventBus()

    event_bus.publish(
        create_event(
            sequence=9301,
            old_state="A",
            new_state="S",
        )
    )

    stream = StateEventStream(
        event_bus
    )

    try:
        stream.validate_after_event_id(
            99
        )

    except StateEventCursorError as exc:
        if exc.latest_event_id != 1:
            raise AssertionError(
                "cursor error details mismatch"
            )

    else:
        raise AssertionError(
            "cursor ahead was not detected"
        )

    print(
        "SSE restart cursor detection: PASSED"
    )


def test_closed_bus():
    event_bus = StateEventBus()
    stream = StateEventStream(
        event_bus
    )

    event_bus.close()

    iterator = stream.iter_events()

    try:
        next(iterator)

    except StopIteration:
        pass

    else:
        raise AssertionError(
            "closed event bus produced data"
        )

    print(
        "SSE closed bus handling: PASSED"
    )


def main():
    test_event_format()
    test_live_stream()
    test_keep_alive()
    test_history_gap()
    test_cursor_ahead()
    test_closed_bus()

    print(
        "state event stream test: PASSED"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
