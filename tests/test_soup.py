#!/usr/bin/env python3

import argparse
import sys

from backend.protocol.errors import (
    ConnectionClosedError,
    SoupEndOfSessionError,
    SoupError,
    SoupLoginRejectedError,
    TransportError,
)
from backend.protocol.soup.session import SoupSession
from backend.protocol.transport.socket import TcpSocket


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Test a SoupBinTCP connection."
    )

    parser.add_argument(
        "-H",
        "--host",
        required=True,
        help="SoupBinTCP server host",
    )
    parser.add_argument(
        "-p",
        "--port",
        required=True,
        type=int,
        help="SoupBinTCP server port",
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
        required=True,
        help="SoupBinTCP password",
    )
    parser.add_argument(
        "-s",
        "--sequence",
        type=int,
        default=1,
        help="Requested Soup sequence number",
    )
    parser.add_argument(
        "--session",
        default="",
        help="Requested Soup session",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Socket timeout in seconds",
    )

    return parser.parse_args()


def run(args):
    tcp_socket = TcpSocket(
        host=args.host,
        port=args.port,
        timeout_seconds=args.timeout,
    )

    soup_session = SoupSession(tcp_socket)

    try:
        soup_session.connect()

        accepted = soup_session.login(
            username=args.username,
            password=args.password,
            session=args.session,
            sequence=args.sequence,
        )

        print(
            "login accepted: session=%s sequence=%d"
            % (
                accepted.session,
                accepted.sequence,
            )
        )

        while True:
            packet = soup_session.receive_packet()

            if packet.packet_type == "H":
                print("server heartbeat")
                soup_session.send_heartbeat()
                continue

            print(
                "packet: type=%s length=%d next_sequence=%d"
                % (
                    packet.packet_type,
                    len(packet.payload),
                    soup_session.next_sequence,
                )
            )

    except SoupLoginRejectedError as exc:
        print("login rejected: %s" % exc)
        return 1

    except SoupEndOfSessionError:
        print(
            "Soup session ended at next sequence %d"
            % soup_session.next_sequence
        )
        return 0

    except ConnectionClosedError:
        print(
            "server closed the connection at next sequence %d"
            % soup_session.next_sequence
        )
        return 0

    except TransportError as exc:
        print("transport error: %s" % exc)
        return 1

    except SoupError as exc:
        print("Soup protocol error: %s" % exc)
        return 1

    except KeyboardInterrupt:
        print(
            "\nstopped at next sequence %d"
            % soup_session.next_sequence
        )
        return 0

    finally:
        soup_session.close()


def main():
    args = parse_arguments()
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
