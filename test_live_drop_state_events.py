#!/usr/bin/env python3

import argparse
import json
import os
import sys
import time

from backend.checkpoint.session_checkpoint import (
    SessionCheckpoint,
)
from backend.checkpoint.snapshot_store import (
    SnapshotStore,
)
from backend.events.state_event_bus import (
    StateEventHistoryGapError,
)
from backend.protocol.drop.client import (
    DropClient,
)
from backend.services.drop_state_service import (
    DropStateService,
)
from backend.settings import (
    get_checkpoint_file,
    get_drop_password,
    get_drop_username,
)
from backend.state.application_state import (
    ApplicationState,
)


def parse_arguments():
    parser = argparse.ArgumentParser(
        description=(
            "Wait for a live DROP state event"
        )
    )

    parser.add_argument(
        "-H",
        "--host",
        required=True,
        help="DROP SoupBinTCP host",
    )

    parser.add_argument(
        "-p",
        "--port",
        required=True,
        type=int,
        help="DROP SoupBinTCP port",
    )

    parser.add_argument(
        "--user-id",
        type=int,
        default=402,
        help="User ID to monitor",
    )

    parser.add_argument(
        "--expected-state",
        choices=(
            "A",
            "S",
        ),
        help=(
            "Wait until the user reaches this state"
        ),
    )

    parser.add_argument(
        "--wait-timeout",
        type=float,
        default=120.0,
        help=(
            "Maximum time to wait for an event"
        ),
    )

    parser.add_argument(
        "--socket-timeout",
        type=float,
        default=10.0,
        help="DROP socket timeout",
    )

    parser.add_argument(
        "--checkpoint-file",
        help=(
            "Checkpoint file. Defaults to the "
            "configured checkpoint path"
        ),
    )

    return parser.parse_args()


def print_current_user(
    application_state,
    user_id,
):
    user = application_state.users.get_user(
        user_id
    )

    if user is None:
        print(
            "current user %d: not available"
            % user_id
        )
        return

    print(
        "current user: id=%d name=%s "
        "state=%s state_sequence=%d"
        % (
            user.user_id,
            user.user_name,
            user.state,
            user.state_sequence,
        )
    )


def is_matching_event(
    published_event,
    user_id,
    expected_state,
):
    event = published_event.event

    if event.entity_type != "user":
        return False

    if event.entity_id != user_id:
        return False

    if expected_state is None:
        return True

    record = event.record

    return (
        record is not None
        and record.get("state")
        == expected_state
    )


def wait_for_user_event(
    subscription,
    user_id,
    expected_state,
    timeout_seconds,
):
    deadline = (
        time.monotonic()
        + timeout_seconds
    )

    while True:
        remaining = (
            deadline - time.monotonic()
        )

        if remaining <= 0:
            return None

        events = subscription.next_events(
            timeout_seconds=min(
                remaining,
                1.0,
            ),
            limit=100,
        )

        for published_event in events:
            event = published_event.event

            print(
                "event received: "
                "event_id=%d entity=%s "
                "entity_id=%r message=%s "
                "sequence=%d"
                % (
                    published_event.event_id,
                    event.entity_type,
                    event.entity_id,
                    event.message_type,
                    event.sequence,
                )
            )

            if is_matching_event(
                published_event=published_event,
                user_id=user_id,
                expected_state=expected_state,
            ):
                return published_event


def run(args):
    checkpoint_file = (
        args.checkpoint_file
        if args.checkpoint_file
        else get_checkpoint_file()
    )

    checkpoint_file = os.path.abspath(
        checkpoint_file
    )

    application_state = ApplicationState()

    snapshot_store = SnapshotStore(
        checkpoint_file
    )

    session_checkpoint = SessionCheckpoint(
        snapshot_store=snapshot_store,
        application_state=application_state,
    )

    drop_client = DropClient(
        host=args.host,
        port=args.port,
        username=get_drop_username(),
        password=get_drop_password(),
        timeout_seconds=(
            args.socket_timeout
        ),
    )

    service = DropStateService(
        drop_client=drop_client,
        application_state=application_state,
        sequence_number=1,
        reconnect_delay_seconds=2.0,
        max_reconnect_attempts=0,
        allow_full_replay_fallback=True,
        session_checkpoint=session_checkpoint,
        restore_checkpoint_on_start=True,
        checkpoint_save_interval_messages=100,
        save_checkpoint_on_shutdown=True,
    )

    subscription = None

    try:
        service.start()

        if not service.wait_until_started(
            timeout_seconds=10.0
        ):
            raise RuntimeError(
                "DROP service did not start"
            )

        if service.last_error is not None:
            raise service.last_error

        subscription = (
            application_state
            .event_bus
            .subscribe()
        )

        print(
            "checkpoint file: %s"
            % checkpoint_file
        )

        print_current_user(
            application_state=application_state,
            user_id=args.user_id,
        )

        print(
            "waiting for live user %d event"
            % args.user_id
        )

        if args.expected_state:
            print(
                "expected state: %s"
                % args.expected_state
            )

        print(
            "send the API command from "
            "another terminal"
        )

        try:
            published_event = (
                wait_for_user_event(
                    subscription=subscription,
                    user_id=args.user_id,
                    expected_state=(
                        args.expected_state
                    ),
                    timeout_seconds=(
                        args.wait_timeout
                    ),
                )
            )

        except StateEventHistoryGapError as exc:
            print(
                "event history gap: %s"
                % exc,
                file=sys.stderr,
            )
            return 1

        if published_event is None:
            print(
                "timed out waiting for user event",
                file=sys.stderr,
            )
            return 1

        print("")
        print(
            "matching live event:"
        )

        print(
            json.dumps(
                published_event.to_dict(),
                indent=2,
                sort_keys=True,
            )
        )

        record = published_event.event.record

        print("")
        print(
            "live DROP event test: PASSED"
        )

        print(
            "user %d state: %s"
            % (
                args.user_id,
                record.get("state"),
            )
        )

        return 0

    finally:
        if subscription is not None:
            subscription.close()

        service.stop(
            timeout_seconds=10.0
        )


def main():
    try:
        return run(
            parse_arguments()
        )

    except KeyboardInterrupt:
        print(
            "\nlive event test stopped"
        )
        return 0

    except Exception as exc:
        print(
            "live event test failed: %s"
            % exc,
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
