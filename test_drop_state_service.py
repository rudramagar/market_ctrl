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
        help=(
            "DROP password. Prompted securely "
            "when omitted"
        ),
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

    return parser.parse_args()


def print_market(market):
    print(
        "market: id=%d name=%s state=%s "
        "trading_session=%s sequence=%d"
        % (
            market.market_id,
            market.market_name,
            market.state,
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
        "state=%s sequence=%d"
        % (
            user.user_id,
            user.user_name,
            user.firm_id,
            user.state,
            user.last_sequence,
        )
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
        print("\nstopping DROP state service")
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
        "users=%d firms=%d markets=%d"
        % (
            counts["users"],
            counts["firms"],
            counts["markets"],
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

    print("")
    print("markets:")

    for market in (
        service.state.markets.get_markets()
    ):
        print_market(market)

    print("")
    print("firms:")

    for firm in service.state.firms.get_firms():
        print_firm(firm)

    print("")
    print("selected user:")

    print_selected_user(
        service.state,
        402,
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
