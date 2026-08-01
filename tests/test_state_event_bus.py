#!/usr/bin/env python3

from backend.events.state_event import (
    EVENT_UPDATED,
    StateEvent,
)
from backend.events.state_event_bus import (
    StateEventBus,
    StateEventBusError,
    StateEventHistoryGapError,
)


def create_event(
    entity_id,
    sequence,
    old_state,
    new_state,
):
    return StateEvent(
        event_type=EVENT_UPDATED,
        entity_type="user",
        entity_id=entity_id,
        sequence=sequence,
        timestamp_ns=sequence * 1000,
        message_type="UserStatusMessage",
        record={
            "user_id": entity_id,
            "state": new_state,
            "last_sequence": sequence,
        },
        changed_fields={
            "state": {
                "old": old_state,
                "new": new_state,
            },
        },
    )


def test_publish_and_history():
    event_bus = StateEventBus(
        history_size=10
    )

    first = event_bus.publish(
        create_event(
            entity_id=402,
            sequence=9001,
            old_state="A",
            new_state="S",
        )
    )

    second = event_bus.publish(
        create_event(
            entity_id=402,
            sequence=9002,
            old_state="S",
            new_state="A",
        )
    )

    if first.event_id != 1:
        raise AssertionError(
            "first event ID mismatch"
        )

    if second.event_id != 2:
        raise AssertionError(
            "second event ID mismatch"
        )

    if event_bus.latest_event_id != 2:
        raise AssertionError(
            "latest event ID mismatch"
        )

    events = event_bus.get_events(
        after_event_id=0
    )

    if len(events) != 2:
        raise AssertionError(
            "event history size mismatch"
        )

    if (
        events[1].to_dict()
        ["record"]["state"]
        != "A"
    ):
        raise AssertionError(
            "published event data mismatch"
        )

    print(
        "event publish and history: PASSED"
    )


def test_subscription():
    event_bus = StateEventBus()

    event_bus.publish(
        create_event(
            entity_id=402,
            sequence=9101,
            old_state="A",
            new_state="S",
        )
    )

    subscription = event_bus.subscribe()

    event_bus.publish(
        create_event(
            entity_id=402,
            sequence=9102,
            old_state="S",
            new_state="A",
        )
    )

    events = subscription.next_events(
        timeout_seconds=0.1
    )

    if len(events) != 1:
        raise AssertionError(
            "subscription event count mismatch"
        )

    if events[0].event_id != 2:
        raise AssertionError(
            "subscription event ID mismatch"
        )

    if subscription.after_event_id != 2:
        raise AssertionError(
            "subscription cursor mismatch"
        )

    if subscription.next_events(
        timeout_seconds=0.01
    ):
        raise AssertionError(
            "subscription timeout should "
            "return no events"
        )

    subscription.close()

    if subscription.next_events(
        timeout_seconds=0.01
    ):
        raise AssertionError(
            "closed subscription returned events"
        )

    print(
        "event subscription: PASSED"
    )


def test_history_gap():
    event_bus = StateEventBus(
        history_size=2
    )

    event_bus.publish(
        create_event(
            entity_id=402,
            sequence=9201,
            old_state="A",
            new_state="S",
        )
    )

    event_bus.publish(
        create_event(
            entity_id=402,
            sequence=9202,
            old_state="S",
            new_state="A",
        )
    )

    event_bus.publish(
        create_event(
            entity_id=402,
            sequence=9203,
            old_state="A",
            new_state="S",
        )
    )

    if event_bus.oldest_event_id != 2:
        raise AssertionError(
            "oldest event ID mismatch"
        )

    try:
        event_bus.get_events(
            after_event_id=0
        )

    except StateEventHistoryGapError as exc:
        if exc.oldest_event_id != 2:
            raise AssertionError(
                "history gap details mismatch"
            )

    else:
        raise AssertionError(
            "history gap was not detected"
        )

    available = event_bus.get_events(
        after_event_id=1
    )

    if [
        event.event_id
        for event in available
    ] != [2, 3]:
        raise AssertionError(
            "available history mismatch"
        )

    print(
        "event history gap detection: PASSED"
    )


def test_close():
    event_bus = StateEventBus()
    subscription = event_bus.subscribe()

    event_bus.close()

    if subscription.next_events(
        timeout_seconds=0.1
    ):
        raise AssertionError(
            "closed bus returned events"
        )

    try:
        event_bus.publish(
            create_event(
                entity_id=402,
                sequence=9301,
                old_state="A",
                new_state="S",
            )
        )

    except StateEventBusError:
        pass

    else:
        raise AssertionError(
            "closed bus accepted an event"
        )

    print(
        "event bus close: PASSED"
    )


def main():
    test_publish_and_history()
    test_subscription()
    test_history_gap()
    test_close()

    print(
        "state event bus test: PASSED"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
