#!/usr/bin/env python3

import argparse
import sys

from backend.protocol.drop.message_format import (
    decode_firm_message,
    decode_firm_status_message,
    decode_sbe_header,
    decode_user_message,
    decode_user_status_message,
)
from backend.protocol.errors import (
    ConnectionClosedError,
    DropFormatError,
    SoupEndOfSessionError,
)
from backend.protocol.soup.session import SoupSession
from backend.protocol.transport.socket import TcpSocket


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Decode DROP User messages."
    )

    parser.add_argument("-H", "--host", required=True)
    parser.add_argument("-p", "--port", required=True, type=int)
    parser.add_argument("-u", "--username", required=True)
    parser.add_argument("-P", "--password", required=True)
    parser.add_argument("-s", "--sequence", type=int, default=1)

    return parser.parse_args()


def run(args):
    tcp_socket = TcpSocket(
        host=args.host,
        port=args.port,
    )
    soup_session = SoupSession(tcp_socket)

    try:
        soup_session.connect()

        accepted = soup_session.login(
            username=args.username,
            password=args.password,
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
                soup_session.send_heartbeat()
                continue

            if packet.packet_type != "S":
                continue

            header = decode_sbe_header(packet.payload)

            if header.template_id == 1:
                user = decode_user_message(packet.payload)
            
                print(
                    "user: id=%d name=%s firm_id=%d state=%s"
                    % (
                        user.user_id,
                        user.user_name,
                        user.firm_id,
                        user.state,
                    )
                )
            
            elif header.template_id == 4:
                firm = decode_firm_message(packet.payload)
            
                print(
                    "firm: id=%d code=%s name=%s type=%s state=%s"
                    % (
                        firm.firm_id,
                        firm.firm_code,
                        firm.firm_name,
                        firm.firm_type,
                        firm.state,
                    )
                )
            
            elif header.template_id == 20:
                status = decode_firm_status_message(
                    packet.payload
                )
            
                print(
                    "firm status: id=%d state=%s "
                    "matching_engine_sequence=%d"
                    % (
                        status.firm_id,
                        status.state,
                        status.mercury_header.matching_engine_sequence,
                    )
                )
            
            elif header.template_id == 21:
                status = decode_user_status_message(
                    packet.payload
                )
            
                print(
                    "user status: id=%d state=%s "
                    "matching_engine_sequence=%d"
                    % (
                        status.user_id,
                        status.state,
                        status.mercury_header.matching_engine_sequence,
                    )
                )


    except ConnectionClosedError:
        print(
            "server closed the connection at sequence %d"
            % soup_session.next_sequence
        )

    except SoupEndOfSessionError:
        print("Soup session ended")

    except DropFormatError as exc:
        print("DROP format error: %s" % exc)
        return 1

    except KeyboardInterrupt:
        print("\nstopped")

    finally:
        soup_session.close()

    return 0


def main():
    return run(parse_arguments())


if __name__ == "__main__":
    sys.exit(main())
