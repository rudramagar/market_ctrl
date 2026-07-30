#!/usr/bin/env python3

import argparse
import getpass
import logging
import sys

from backend.protocol.drop.client import DropClient
from backend.protocol.drop.messages import (
    FirmMessage,
    FirmStatusMessage,
    MarketMessage,
    MarketTradingStateMessage,
    UserMessage,
    UserStatusMessage,
)
from backend.protocol.errors import ProtocolError
from backend.state.market_state import (
    MarketStateStore,
)
from backend.state.user_state import UserStateStore

def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Test the DROP protocol client"
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
        required=True,
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
    parser.add_argument(
        "-n",
        "--count",
        type=int,
        default=0,
        help=(
            "Stop after this many decoded "
            "messages. Zero means no limit"
        ),
    )
    parser.add_argument(
        "--strict-templates",
        action="store_true",
        help=(
            "Fail when an unsupported DROP "
            "template is received"
        ),
    )

    return parser.parse_args()


def print_message(message):
    sequence = (
        message.mercury_header
        .matching_engine_sequence
    )

    if isinstance(message, UserMessage):
        print(
            "user: id=%d name=%s firm_id=%d "
            "state=%s sequence=%d"
            % (
                message.user_id,
                message.user_name,
                message.firm_id,
                message.state,
                sequence,
            )
        )
        return

    if isinstance(message, FirmMessage):
        print(
            "firm: id=%d code=%s name=%s "
            "type=%s state=%s sequence=%d"
            % (
                message.firm_id,
                message.firm_code,
                message.firm_name,
                message.firm_type,
                message.state,
                sequence,
            )
        )
        return

    if isinstance(message, MarketMessage):
        print(
            "market: id=%d name=%s "
            "trading_session=%d sequence=%d"
            % (
                message.market_id,
                message.market_name,
                message.market_trading_session,
                sequence,
            )
        )
        return

    if isinstance(
        message,
        MarketTradingStateMessage,
    ):
        print(
            "market state: id=%d state=%s "
            "sequence=%d"
            % (
                message.market_id,
                message.state,
                sequence,
            )
        )
        return

    if isinstance(message, FirmStatusMessage):
        print(
            "firm status: id=%d state=%s "
            "sequence=%d"
            % (
                message.firm_id,
                message.state,
                sequence,
            )
        )
        return

    if isinstance(message, UserStatusMessage):
        print(
            "user status: id=%d state=%s "
            "sequence=%d"
            % (
                message.user_id,
                message.state,
                sequence,
            )
        )
        return

    print(
        "decoded: type=%s template=%d "
        "sequence=%d"
        % (
            type(message).__name__,
            message.sbe_header.template_id,
            sequence,
        )
    )


def run(args):
    password = args.password

    if password is None:
        password = getpass.getpass(
            "DROP password: "
        )

    market_store = MarketStateStore()
    user_store = UserStateStore()

    drop_client = DropClient(
        host=args.host,
        port=args.port,
        username=args.username,
        password=password,
        timeout_seconds=args.timeout,
        strict_templates=args.strict_templates,
    )

    decoded_count = 0

    try:
        drop_client.connect(
            session=args.session,
            sequence_number=args.sequence,
        )

        print(
            "login accepted: "
            "requested_sequence=%d"
            % args.sequence
        )
        print("reading DROP messages...")

        while (
            args.count == 0
            or decoded_count < args.count
        ):
            message = drop_client.receive()

            if message is None:
                print(
                    "server closed the connection"
                )
                break

            market_store.apply(message)
            user_store.apply(message)

            print_message(message)
            decoded_count += 1

        print(
            "decoded messages: %d"
            % decoded_count
        )

        if drop_client.unsupported_template_ids:
            template_ids = sorted(
                drop_client
                .unsupported_template_ids
            )

            print(
                "unsupported templates: %s"
                % ", ".join(
                    str(template_id)
                    for template_id
                    in template_ids
                )
            )

        print("")
        print(
                "reconstructed markets: %d"
                % market_store.count
        )

        for market in market_store.get_markets():
            state = (
                market.state
                if market.state is not None
                else "UNKNOWN"
            )
        
            name = (
                market.market_name
                if market.market_name is not None
                else "UNKNOWN"
            )
        
            print(
                "market: id=%d name=%s state=%s "
                "trading_session=%s sequence=%d"
                % (
                    market.market_id,
                    name,
                    state,
                    market.market_trading_session,
                    market.last_sequence,
                )
            )

        print("")
        print(
            "reconstructed users: %d"
            % user_store.count
        )
        
        for user in user_store.get_users():
            state = (
                user.state
                if user.state is not None
                else "UNKNOWN"
            )
        
            name = (
                user.user_name
                if user.user_name is not None
                else "UNKNOWN"
            )
        
            firm_id = (
                user.firm_id
                if user.firm_id is not None
                else "UNKNOWN"
            )
        
            print(
                "user: id=%d name=%s firm_id=%s "
                "state=%s sequence=%d"
                % (
                    user.user_id,
                    name,
                    firm_id,
                    state,
                    user.last_sequence,
                )
            )

        return 0

    except KeyboardInterrupt:
        print("\nstopped by user")
        return 0

    except (ProtocolError, OSError) as exc:
        print(
            "DROP client error: %s"
            % exc,
            file=sys.stderr,
        )
        return 1

    finally:
        drop_client.close()


def main():
    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s: %(message)s",
    )

    return run(parse_arguments())


if __name__ == "__main__":
    sys.exit(main())
