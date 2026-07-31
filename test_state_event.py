#!/usr/bin/env python3

from backend.events.state_event import (
    EVENT_UPDATED,
    StateEvent,
)


def main():
    record = {
        "user_id": 402,
        "user_name": "TX99900C",
        "state": "A",
        "last_sequence": 8901,
    }

    changed_fields = {
        "state": {
            "old": "S",
            "new": "A",
        },
        "last_sequence": {
            "old": 8873,
            "new": 8901,
        },
    }

    event = StateEvent(
        event_type=EVENT_UPDATED,
        entity_type="user",
        entity_id=402,
        sequence=8901,
        timestamp_ns=123456789,
        message_type="UserStatusMessage",
        record=record,
        changed_fields=changed_fields,
    )

    if event.event_type != "updated":
        raise AssertionError(
            "event type mismatch"
        )

    if event.entity_type != "user":
        raise AssertionError(
            "entity type mismatch"
        )

    if event.entity_id != 402:
        raise AssertionError(
            "entity ID mismatch"
        )

    if event.sequence != 8901:
        raise AssertionError(
            "sequence mismatch"
        )

    if (
        event.changed_fields["state"]["old"]
        != "S"
    ):
        raise AssertionError(
            "old state mismatch"
        )

    if (
        event.changed_fields["state"]["new"]
        != "A"
    ):
        raise AssertionError(
            "new state mismatch"
        )

    serialized = event.to_dict()

    expected = {
        "event_type": "updated",
        "entity_type": "user",
        "entity_id": 402,
        "sequence": 8901,
        "timestamp_ns": 123456789,
        "message_type": (
            "UserStatusMessage"
        ),
        "record": {
            "user_id": 402,
            "user_name": "TX99900C",
            "state": "A",
            "last_sequence": 8901,
        },
        "changed_fields": {
            "state": {
                "old": "S",
                "new": "A",
            },
            "last_sequence": {
                "old": 8873,
                "new": 8901,
            },
        },
    }

    if serialized != expected:
        raise AssertionError(
            "serialized event mismatch: %r"
            % serialized
        )

    # Verify that external dictionaries cannot
    # mutate the event.
    record["state"] = "BROKEN"
    changed_fields["state"]["new"] = (
        "BROKEN"
    )
    serialized["record"]["state"] = (
        "BROKEN"
    )

    if event.record["state"] != "A":
        raise AssertionError(
            "event record was mutated"
        )

    if (
        event.changed_fields["state"]["new"]
        != "A"
    ):
        raise AssertionError(
            "event changes were mutated"
        )

    print(
        "state event fields: PASSED"
    )
    print(
        "state event serialization: PASSED"
    )
    print(
        "state event immutability: PASSED"
    )
    print(
        "state event test: PASSED"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
