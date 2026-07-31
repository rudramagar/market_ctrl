#!/usr/bin/env python3

import argparse
import logging
import sys

from backend.checkpoint.session_checkpoint import (
    SessionCheckpoint,
)
from backend.checkpoint.snapshot_store import (
    SnapshotStore,
)
from backend.protocol.drop.client import (
    DropClient,
)
from backend.services.drop_state_service import (
    DropStateService,
)
from backend.settings import (
    get_drop_password,
    get_drop_username,
)
from backend.state.application_state import (
    ApplicationState,
)


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Test the DROP state service"
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
        "-u",
        "--username",
        help="DROP SoupBinTCP username",
    )

    parser.add_argument(
        "-P",
        "--password",
        help="DROP SoupBinTCP password",
    )

    parser.add_argument(
        "--session",
        default="",
        help="Requested SoupBinTCP session",
    )

    parser.add_argument(
        "-s",
        "--sequence",
        type=int,
        default=1,
        help="Requested starting Soup sequence",
    )

    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Socket timeout in seconds",
    )

    parser.add_argument(
        "--reconnect-attempt",
        "--reconnect-attempts",
        dest="reconnect_attempt",
        type=int,
        default=0,
        help=(
            "Maximum automatic reconnect attempts. "
            "Zero disables reconnection"
        ),
    )

    parser.add_argument(
        "--reconnect-delay",
        type=float,
        default=2.0,
        help="Delay between reconnect attempts",
    )

    parser.add_argument(
        "--user-id",
        type=int,
        default=402,
        help="User ID displayed after replay",
    )

    parser.add_argument(
        "--checkpoint-file",
        help=(
            "JSON checkpoint file used to save and "
            "restore the current DROP session"
        ),
    )

    parser.add_argument(
        "--checkpoint-save-interval",
        type=int,
        default=100,
        help=(
            "Save a checkpoint after this many DROP "
            "messages. Zero disables periodic saves"
        ),
    )

    parser.add_argument(
        "--no-checkpoint-restore",
        action="store_true",
        help=(
            "Do not restore an existing checkpoint "
            "during startup"
        ),
    )

    return parser.parse_args()


def print_market(market):
    print(
        "market: id=%d name=%s state=%s "
        "phase=%s trading_session=%s sequence=%d"
        % (
            market.market_id,
            market.market_name,
            market.state,
            market.phase_name,
            market.market_trading_session,
            market.last_sequence,
        )
    )


def print_firm(firm):
    print(
        "firm: id=%d code=%s name=%s "
        "type=%s state=%s sequence=%d"
        % (
            firm.firm_id,
            firm.firm_code,
            firm.firm_name,
            firm.firm_type,
            firm.state,
            firm.last_sequence,
        )
    )


def print_user_type(user_type):
    print(
        "user type: id=%d name=%s sequence=%d"
        % (
            user_type.user_type_id,
            user_type.user_type_name,
            user_type.last_sequence,
        )
    )


def print_session(application_state):
    session = application_state.session
    trading_engine = session.trading_engine
    last_event = session.last_system_event

    print("")
    print("session:")

    print(
        "session: id=%s trade_date=%s "
        "calendar_date=%s start_date=%s "
        "end_session=%s"
        % (
            session.session_id,
            session.trade_date,
            session.calendar_date,
            session.session_start_date,
            session.end_session_dispatched,
        )
    )

    if trading_engine is None:
        print("engine: not available")

    else:
        print(
            "engine: mode=%s version=%s "
            "timezone=%s sequence=%d"
            % (
                trading_engine.trading_session_mode,
                trading_engine.matching_engine_version,
                trading_engine.time_zone,
                trading_engine.last_sequence,
            )
        )

    if last_event is None:
        print("last event: not available")

    else:
        print(
            "last event: type=%d name=%s "
            "state=%s sequence=%d"
            % (
                last_event.system_event_type,
                last_event.event_name,
                last_event.event_state_name,
                last_event.last_sequence,
            )
        )


def print_selected_user(
    application_state,
    user_id,
):
    user = application_state.users.get_user(
        user_id
    )

    if user is None:
        print(
            "user %d was not found"
            % user_id
        )
        return

    print(
        "user: id=%d name=%s firm_id=%s "
        "user_type_id=%s state=%s sequence=%d"
        % (
            user.user_id,
            user.user_name,
            user.firm_id,
            user.user_type_id,
            user.state,
            user.last_sequence,
        )
    )

    user_type = None

    if user.user_type_id is not None:
        user_type = (
            application_state.references
            .get_user_type(
                user.user_type_id
            )
        )

    if user_type is None:
        print("user type: not available")

    else:
        print(
            "user type: id=%d name=%s"
            % (
                user_type.user_type_id,
                user_type.user_type_name,
            )
        )

    user_markets = (
        application_state.references
        .get_user_markets(
            user.user_id
        )
    )

    if not user_markets:
        print("user markets: none")

    else:
        print(
            "user markets: %s"
            % ", ".join(
                str(record.market_id)
                for record in user_markets
            )
        )


def verify_state_round_trip(
    application_state,
):
    """
    Verify that reconstructed DROP state can be
    restored without changing any values.
    """

    original_snapshot = (
        application_state.snapshot()
    )

    restored_state = ApplicationState()

    restored_counts = restored_state.restore(
        original_snapshot
    )

    restored_snapshot = (
        restored_state.snapshot()
    )

    if restored_snapshot != original_snapshot:
        raise AssertionError(
            "real DROP snapshot changed "
            "during restoration"
        )

    current_counts = restored_state.counts()

    if restored_counts != current_counts:
        raise AssertionError(
            "restored count mismatch: "
            "restore=%r current=%r"
            % (
                restored_counts,
                current_counts,
            )
        )

    print("")
    print(
        "real DROP state restore: PASSED"
    )
    print(
        "real DROP snapshot round trip: PASSED"
    )
    print(
        "restored counts: %r"
        % restored_counts
    )


def create_session_checkpoint(
    checkpoint_file,
    application_state,
):
    if not checkpoint_file:
        return None

    snapshot_store = SnapshotStore(
        checkpoint_file
    )

    print(
        "checkpoint file: %s"
        % snapshot_store.path
    )

    return SessionCheckpoint(
        snapshot_store=snapshot_store,
        application_state=application_state,
    )


def print_checkpoint_status(status):
    if not status["checkpoint_enabled"]:
        return

    print(
        "checkpoint restored: %s"
        % status["checkpoint_restored"]
    )

    print(
        "checkpoint saves: %d"
        % status["checkpoint_saves"]
    )

    print(
        "checkpoint restored trade date: %s"
        % status[
            "checkpoint_restored_trade_date"
        ]
    )

    print(
        "checkpoint restored sequence: %s"
        % status[
            "checkpoint_restored_sequence"
        ]
    )

    print(
        "checkpoint last saved at: %s"
        % status[
            "checkpoint_last_saved_at"
        ]
    )

    print(
        "checkpoint error: %s"
        % status["checkpoint_last_error"]
    )


def run(args):
    username = (
        args.username
        if args.username
        else get_drop_username()
    )

    password = (
        args.password
        if args.password
        else get_drop_password()
    )

    application_state = ApplicationState()

    session_checkpoint = (
        create_session_checkpoint(
            checkpoint_file=(
                args.checkpoint_file
            ),
            application_state=(
                application_state
            ),
        )
    )

    drop_client = DropClient(
        host=args.host,
        port=args.port,
        username=username,
        password=password,
        timeout_seconds=args.timeout,
    )

    service = DropStateService(
        drop_client=drop_client,
        application_state=application_state,
        session=args.session,
        sequence_number=args.sequence,
        reconnect_delay_seconds=(
            args.reconnect_delay
        ),
        max_reconnect_attempts=(
            args.reconnect_attempt
        ),
        session_checkpoint=session_checkpoint,
        restore_checkpoint_on_start=(
            not args.no_checkpoint_restore
        ),
        checkpoint_save_interval_messages=(
            args.checkpoint_save_interval
        ),
        save_checkpoint_on_shutdown=True,
    )

    try:
        service.start()

        print(
            "DROP state service started: "
            "requested_sequence=%d"
            % args.sequence
        )

        service.wait()

    except KeyboardInterrupt:
        print(
            "\nstopping DROP state service"
        )

        service.stop()

        return 0

    finally:
        service.stop()

    if service.last_error is not None:
        print(
            "DROP state service error: %s"
            % service.last_error,
            file=sys.stderr,
        )

        return 1

    status = service.status()
    counts = status["state_counts"]

    print(
        "reconnects: %d"
        % status["reconnects"]
    )

    print(
        "connections: %d"
        % status["connections"]
    )

    print(
        "full replay fallbacks: %d"
        % status[
            "full_replay_fallbacks"
        ]
    )

    print(
        "current Soup session: %s"
        % status["current_session"]
    )

    print(
        "next Soup sequence: %s"
        % status["next_soup_sequence"]
    )

    print(
        "disconnect reason: %s"
        % status["disconnect_reason"]
    )

    print_checkpoint_status(
        status
    )

    print("")

    print(
        "received messages: %d"
        % status["received_messages"]
    )

    print(
        "applied messages: %d"
        % status["applied_messages"]
    )

    print(
        "application state: "
        "users=%d firms=%d markets=%d "
        "user_types=%d user_markets=%d "
        "system_events=%d"
        % (
            counts["users"],
            counts["firms"],
            counts["markets"],
            counts["user_types"],
            counts["user_markets"],
            counts["system_events"],
        )
    )

    if status["unsupported_templates"]:
        print(
            "unsupported templates: %s"
            % ", ".join(
                str(template_id)
                for template_id
                in status[
                    "unsupported_templates"
                ]
            )
        )

    print_session(
        service.state
    )

    print("")
    print("markets:")

    for market in (
        service.state.markets.get_markets()
    ):
        print_market(
            market
        )

    print("")
    print("firms:")

    for firm in (
        service.state.firms.get_firms()
    ):
        print_firm(
            firm
        )

    print("")
    print("user types:")

    for user_type in (
        service.state.references
        .get_user_types()
    ):
        print_user_type(
            user_type
        )

    print("")
    print("selected user:")

    print_selected_user(
        application_state=service.state,
        user_id=args.user_id,
    )

    verify_state_round_trip(
        service.state
    )

    return 0


def main():
    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s: %(message)s",
    )

    return run(
        parse_arguments()
    )


if __name__ == "__main__":
    sys.exit(
        main()
    )
