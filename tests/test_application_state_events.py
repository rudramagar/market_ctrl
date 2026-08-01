#!/usr/bin/env python3

from backend.protocol.drop.messages import (
    MercuryHeader,
    SbeHeader,
    UserMessage,
    UserStatusMessage,
)
from backend.state.application_state import (
    ApplicationState,
)


def headers(
    template_id,
    sequence,
):
    return {
        "sbe_header": SbeHeader(
            block_length=0,
            template_id=template_id,
            schema_id=901,
            version=1,
        ),
        "mercury_header": MercuryHeader(
            timestamp_nanoseconds=(
                sequence * 1000
            ),
            matching_engine_sequence=(
                sequence
            ),
        ),
    }


def user_message(
    sequence,
    state,
):
    return UserMessage(
        **headers(
            template_id=1,
            sequence=sequence,
        ),
        user_index=38,
        user_id=402,
        user_name="TX99900C",
        liquidity_provider=False,
        state=state,
        firm_index=2,
        firm_id=2,
        executing_firm="00099900",
        capacity="A",
        clearing_firm="",
        clearing_ref="",
        allow_override=False,
        live_order_limit=100,
        user_type_id=4,
    )


def user_status_message(
    sequence,
    state,
):
    return UserStatusMessage(
        **headers(
            template_id=21,
            sequence=sequence,
        ),
        user_index=38,
        user_id=402,
        state=state,
    )


def main():
    application_state = (
        ApplicationState()
    )

    if not application_state.apply(
        user_message(
            sequence=100,
            state="A",
        )
    ):
        raise AssertionError(
            "user definition was not applied"
        )

    events = (
        application_state.event_bus
        .get_events(
            after_event_id=0
        )
    )

    if len(events) != 1:
        raise AssertionError(
            "created event count mismatch"
        )

    created = events[0].to_dict()

    if created["event_type"] != "created":
        raise AssertionError(
            "expected created event"
        )

    if created["entity_type"] != "user":
        raise AssertionError(
            "created entity type mismatch"
        )

    if created["entity_id"] != 402:
        raise AssertionError(
            "created entity ID mismatch"
        )

    if created["record"]["state"] != "A":
        raise AssertionError(
            "created state mismatch"
        )

    print(
        "user created event: PASSED"
    )

    if not application_state.apply(
        user_status_message(
            sequence=101,
            state="S",
        )
    ):
        raise AssertionError(
            "user status was not applied"
        )

    events = (
        application_state.event_bus
        .get_events(
            after_event_id=1
        )
    )

    if len(events) != 1:
        raise AssertionError(
            "updated event count mismatch"
        )

    updated = events[0].to_dict()

    if updated["event_type"] != "updated":
        raise AssertionError(
            "expected updated event"
        )

    if (
        updated["message_type"]
        != "UserStatusMessage"
    ):
        raise AssertionError(
            "message type mismatch"
        )

    if updated["sequence"] != 101:
        raise AssertionError(
            "event sequence mismatch"
        )

    if updated["timestamp_ns"] != 101000:
        raise AssertionError(
            "event timestamp mismatch"
        )

    state_change = (
        updated["changed_fields"]["state"]
    )

    if state_change != {
        "old": "A",
        "new": "S",
    }:
        raise AssertionError(
            "state change mismatch: %r"
            % state_change
        )

    if updated["record"]["state"] != "S":
        raise AssertionError(
            "updated record mismatch"
        )

    print(
        "user updated event: PASSED"
    )

    if application_state.apply(
        user_status_message(
            sequence=101,
            state="A",
        )
    ):
        raise AssertionError(
            "duplicate sequence was applied"
        )

    if (
        application_state
        .event_bus.latest_event_id
        != 2
    ):
        raise AssertionError(
            "stale update published an event"
        )

    print(
        "stale event suppression: PASSED"
    )

    snapshot = (
        application_state.snapshot()
    )

    restored_state = ApplicationState()

    restored_state.restore(
        snapshot
    )

    if (
        restored_state
        .event_bus.latest_event_id
        != 0
    ):
        raise AssertionError(
            "snapshot restore published events"
        )

    restored_user = (
        restored_state.users.get_user(
            402
        )
    )

    if (
        restored_user is None
        or restored_user.state != "S"
    ):
        raise AssertionError(
            "restored user state mismatch"
        )

    print(
        "restore event suppression: PASSED"
    )
    print(
        "application state events test: PASSED"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
