#!/usr/bin/env python3

import argparse
import sys

from backend.protocol.api.client import ApiClient
from backend.protocol.errors import (
    ApiError,
    ApiRequestRejectedError,
    ConnectionClosedError,
    SoupEndOfSessionError,
    SoupLoginRejectedError,
    TransportError,
)


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Update a matching-engine firm state."
    )

    parser.add_argument("-H", "--host", required=True)
    parser.add_argument("-p", "--port", required=True, type=int)
    parser.add_argument("-u", "--username", required=True)
    parser.add_argument("-P", "--password", required=True)
    parser.add_argument(
        "--firm-id",
        required=True,
        type=int,
    )
    parser.add_argument(
        "--state",
        required=True,
        choices=("A", "S"),
        help="A=active, S=suspended",
    )

    return parser.parse_args()


def run(args):
    api_client = ApiClient(
        host=args.host,
        port=args.port,
        username=args.username,
        password=args.password,
    )

    try:
        accepted = api_client.connect()

        print(
            "login accepted: session=%s sequence=%d"
            % (
                accepted.session,
                accepted.sequence,
            )
        )

        correlation_id = api_client.update_firm_state(
            firm_id=args.firm_id,
            state=args.state,
        )

        print(
            "request accepted: firm_id=%d state=%s "
            "correlation_id=%d"
            % (
                args.firm_id,
                args.state,
                correlation_id,
            )
        )

        return 0

    except ApiRequestRejectedError as exc:
        print(
            "request rejected: code=%d reason=%s"
            % (
                exc.reject_reason,
                exc.reject_text,
            )
        )

    except SoupLoginRejectedError as exc:
        print("login rejected: %s" % exc)

    except SoupEndOfSessionError:
        print("Soup session ended")

    except ConnectionClosedError:
        print("server closed the connection")

    except TransportError as exc:
        print("transport error: %s" % exc)

    except ApiError as exc:
        print("API error: %s" % exc)

    finally:
        api_client.close()

    return 1


if __name__ == "__main__":
    sys.exit(run(parse_arguments()))
