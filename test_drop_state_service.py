#!/usr/bin/env python3

import argparse
import logging
import sys

from backend.protocol.drop.client import DropClient
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
        help="Requested starting sequence",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Socket timeout in seconds",
    )
    parser.add_argument(
        "--reconnect-attempts",
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

    return parser.parse_args()


def print_session(state):
    session = state.session
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

    if trading_engine is not None:
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

    if last_event is not None:
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


def print_market(market):
    print(
        "market: id=%d name=%s state=%s "
        "phase=%s trading_session=%s "
        "sequence=%d"
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


def print_user_types(state):
    print("")
    print("user types:")

    user_types = (
        state.references.get_user_types()
    )

    if not user_types:
        print("no user types found")
        return

    for user_type in user_types:
        print(
            "user type: id=%d name=%s "
            "sequence=%d"
            % (
                user_type.user_type_id,
                user_type.user_type_name,
                user_type.last_sequence,
            )
        )


def print_selected_user(state, user_id):
    user = state.users.get_user(user_id)

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

    user_type = (
        state.references.get_user_type(
            user.user_type_id
        )
    )

    if user_type is not None:
        print(
            "user type: id=%d name=%s"
            % (
                user_type.user_type_id,
                user_type.user_type_name,
            )
        )

    user_markets = (
        state.references.get_user_markets(
            user_id
        )
    )

    if not user_markets:
        print("user markets: none")
        return

    print(
        "user markets: %s"
        % ", ".join(
            str(user_market.market_id)
            for user_market in user_markets
        )
    )

def verify_state_round_trip(application_state,):
    """
    Verify that actual reconstructed DROP state can
    be restored without changing any values.
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

    if restored_counts != restored_state.counts():
        raise AssertionError(
            "restored count mismatch: "
            "restore=%r current=%r"
            % (
                restored_counts,
                restored_state.counts(),
            )
        )

    print()
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

    drop_client = DropClient(
        host=args.host,
        port=args.port,
        username=username,
        password=password,
        timeout_seconds=args.timeout,
    )

    service = DropStateService(
        drop_client=drop_client,
        session=args.session,
        sequence_number=args.sequence,
        reconnect_delay_seconds=(
            args.reconnect_delay
        ),
        max_reconnect_attempts=(
            args.reconnect_attempts
        ),
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
        % status["full_replay_fallbacks"]
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
                in status["unsupported_templates"]
            )
        )

    print_session(service.state)

    print("")
    print("markets:")

    for market in (
        service.state.markets.get_markets()
    ):
        print_market(market)

    print("")
    print("firms:")

    for firm in (
        service.state.firms.get_firms()
    ):
        print_firm(firm)

    print_user_types(service.state)

    print("")
    print("selected user:")

    print_selected_user(
        service.state,
        402,
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

    return run(parse_arguments())


if __name__ == "__main__":
    sys.exit(main())
