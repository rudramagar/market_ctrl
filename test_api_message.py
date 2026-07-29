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
        description="Update a matching-engine user state."
    )

    parser.add_argument("-H", "--host", required=True)
    parser.add_argument("-p", "--port", required=True, type=int)
    parser.add_argument("-u", "--username", required=True)
    parser.add_argument("-P", "--password", required=True)

    parser.add_argument(
        "--user-id",
        required=True,
        type=int,
    )
    parser.add_argument(
        "--state",
        required=True,
        choices=("A", "S"),
        help="A=active, S=suspended",
    )
    parser.add_argument(
        "--sequence",
        type=int,
        default=0,
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
    )

    return parser.parse_args()


def run(args):
    api_client = ApiClient(
        host=args.host,
        port=args.port,
        username=args.username,
        password=args.password,
        sequence=args.sequence,
        timeout_seconds=args.timeout,
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

        correlation_id = api_client.update_user_state(
            user_id=args.user_id,
            state=args.state,
        )

        print(
            "request accepted: user_id=%d state=%s "
            "correlation_id=%d"
            % (
                args.user_id,
                args.state,
                correlation_id,
            )
        )

        return 0

    except ApiRequestRejectedError as exc:
        print(
            "request rejected: code=%d reason=%s "
            "correlation_id=%d"
            % (
                exc.reject_reason,
                exc.reject_text,
                exc.correlation_id,
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

    except KeyboardInterrupt:
        print("\nstopped")

    finally:
        api_client.close()

    return 1


def main():
    return run(parse_arguments())


if __name__ == "__main__":
    sys.exit(main())
