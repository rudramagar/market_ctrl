#!/usr/bin/env python3

import argparse
import getpass
import sys

from backend.protocol.drop.message_format import (
    DropMessageDecoder,
)
from backend.protocol.drop.messages import (
    FirmMessage,
    FirmStatusMessage,
    MarketMessage,
    MarketTradingStateMessage,
    UserMessage,
    UserStatusMessage,
)
from backend.protocol.errors import (
    ConnectionClosedError,
    DropFormatError,
    ProtocolError,
)
from backend.protocol.soup.session import SoupSession
from backend.protocol.transport.socket import TcpSocket


def parse_args():
    parser = argparse.ArgumentParser(
        description="Test the common DROP message decoder"
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
        help="SoupBinTCP username",
    )
    parser.add_argument(
        "-P",
        "--password",
        help=(
            "SoupBinTCP password. "
            "Prompted securely when omitted"
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
        help="Requested starting sequence number",
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
            "Stop after this many decoded messages. "
            "Zero means continue until disconnected"
        ),
    )

    return parser.parse_args()


def normalize_packet_type(packet_type):
    if isinstance(packet_type, bytes):
        return packet_type.decode("ascii")

    return packet_type


def print_message(message):
    sequence = (
        message.mercury_header
        .matching_engine_sequence
    )

    if isinstance(message, UserMessage):
        print(
            "user: "
            "id=%d name=%s firm_id=%d "
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
            "firm: "
            "id=%d code=%s name=%s "
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
            "market: "
            "id=%d name=%s trading_session=%d "
            "sequence=%d"
            % (
                message.market_id,
                message.market_name,
                message.market_trading_session,
                sequence,
            )
        )
        return

    if isinstance(message, MarketTradingStateMessage):
        print(
            "market state: "
            "id=%d state=%s sequence=%d"
            % (
                message.market_id,
                message.state,
                sequence,
            )
        )
        return

    if isinstance(message, FirmStatusMessage):
        print(
            "firm status: "
            "id=%d state=%s sequence=%d"
            % (
                message.firm_id,
                message.state,
                sequence,
            )
        )
        return

    if isinstance(message, UserStatusMessage):
        print(
            "user status: "
            "id=%d state=%s sequence=%d"
            % (
                message.user_id,
                message.state,
                sequence,
            )
        )
        return

    print(
        "decoded: type=%s template=%d sequence=%d"
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

    tcp_socket = TcpSocket(
        args.host,
        args.port,
        timeout_seconds=args.timeout,
    )

    soup_session = SoupSession(tcp_socket)
    message_decoder = DropMessageDecoder()

    unsupported_templates = set()
    decoded_count = 0
    server_closed = False

    try:
        soup_session.connect()

        soup_session.login(
            args.username,
            password,
            args.session,
            args.sequence,
        )

        print(
            "login accepted: requested_sequence=%d"
            % args.sequence
        )
        print("reading DROP messages...")

        while (
            args.count == 0
            or decoded_count < args.count
        ):
            packet = soup_session.receive_packet()
            packet_type = normalize_packet_type(
                packet.packet_type
            )

            if packet_type == "H":
                soup_session.send_heartbeat()
                continue

            if packet_type == "Z":
                server_closed = True

                print(
                    "server closed the connection "
                )
                break

            if packet_type != "S":
                print(
                    "ignored Soup packet type: %s"
                    % packet_type
                )
                continue

            try:
                template_id = (
                    message_decoder.get_template_id(
                        packet.payload
                    )
                )

                if not message_decoder.supports(
                    packet.payload
                ):
                    if (
                        template_id
                        not in unsupported_templates
                    ):
                        unsupported_templates.add(
                            template_id
                        )

                        print(
                            "unsupported DROP template: %d"
                            % template_id
                        )

                    continue

                message = message_decoder.decode(
                    packet.payload
                )

            except DropFormatError as exc:
                print(
                    "DROP decode error: %s"
                    % exc
                )
                continue

            print_message(message)
            decoded_count += 1

        print(
            "decoded messages: %d"
            % decoded_count
        )

        return 0

    except KeyboardInterrupt:
        print("\nstopped by user")
        return 0

    except ConnectionClosedError:
        server_closed = True
        print("server closed the connection")
        return 0

    except ProtocolError as exc:
        print(
            "protocol error: %s"
            % exc,
            file=sys.stderr,
        )
        return 1

    except OSError as exc:
        print(
            "socket error: %s"
            % exc,
            file=sys.stderr,
        )
        return 1

    finally:
        if not server_closed:
            try:
                soup_session.logout()
            except (ProtocolError, OSError):
                pass

        soup_session.close()


def main():
    args = parse_args()
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
