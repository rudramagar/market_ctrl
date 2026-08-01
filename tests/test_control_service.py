#!/usr/bin/env python3

import argparse
import logging
import os
import sys
import time

from backend.protocol.api.client import ApiClient
from backend.protocol.drop.client import DropClient
from backend.protocol.errors import (
    ControlError,
    ProtocolError,
)
from backend.protocol.errors import (
    ConnectionClosedError,
)
from backend.services.control_service import (
    ControlService,
)
from backend.services.drop_state_service import (
    DropStateService,
)
from backend.settings import (
    get_drop_password,
    get_drop_username,
)

class FaultInjectingApiClient(ApiClient):
    """API client that simulates response-read failures."""

    def __init__(
        self,
        *args,
        **kwargs
    ):
        self._remaining_read_failures = int(
            kwargs.pop(
                "inject_read_failures",
                0,
            )
        )

        super().__init__(
            *args,
            **kwargs
        )

    def _receive_result(
        self,
        correlation_id,
    ):
        if self._remaining_read_failures > 0:
            self._remaining_read_failures -= 1

            raise ConnectionClosedError(
                "injected API response read failure"
            )

        return super()._receive_result(
            correlation_id
        )

def parse_arguments():
    parser = argparse.ArgumentParser(
        description=(
            "Send an API control request and "
            "confirm it through DROP"
        )
    )

    parser.add_argument(
        "-H",
        "--host",
        required=True,
        help="API and DROP server host",
    )
    parser.add_argument(
        "--drop-port",
        type=int,
        default=12001,
        help="DROP SoupBinTCP port",
    )
    parser.add_argument(
        "--api-port",
        type=int,
        default=11005,
        help="API SoupBinTCP port",
    )

    parser.add_argument(
        "--drop-username",
        help="Overrides DROP_USERNAME",
    )
    parser.add_argument(
        "--drop-password",
        help="Overrides DROP_PASSWORD",
    )
    parser.add_argument(
        "--api-username",
        help="Overrides API_USERNAME",
    )
    parser.add_argument(
        "--api-password",
        help="Overrides API_PASSWORD",
    )

    parser.add_argument(
        "--session",
        default="",
        help="Requested DROP Soup session",
    )
    parser.add_argument(
        "-s",
        "--sequence",
        type=int,
        default=1,
        help="Starting DROP Soup sequence",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Socket timeout in seconds",
    )
    parser.add_argument(
        "--confirmation-timeout",
        type=float,
        default=10.0,
        help="DROP confirmation timeout",
    )
    parser.add_argument(
        "--startup-timeout",
        type=float,
        default=20.0,
        help="Initial DROP replay timeout",
    )
    parser.add_argument(
        "--reconnect-delay",
        type=float,
        default=1.0,
        help="DROP reconnect delay",
    )

    parser.add_argument(
        "--entity",
        required=True,
        choices=("user", "firm", "market"),
        help="Entity to control",
    )
    parser.add_argument(
        "--entity-id",
        required=True,
        type=int,
        help="User, firm, or market ID",
    )
    parser.add_argument(
        "--state",
        required=True,
        choices=("A", "S"),
        help="Requested state",
    )
    parser.add_argument(
        "--no-restore",
        action="store_true",
        help=(
            "Do not restore the entity to its "
            "original state after the test"
        ),
    )
    parser.add_argument(
        "--inject-api-read-failures",
        type=int,
        default=0,
        choices=(0, 1, 2),
        help=(
            "simulate API response read failures "
            "after sending the request"
        ),
    )

    return parser.parse_args()


def resolve_required(
    command_line_value,
    environment_name,
):
    if command_line_value:
        return command_line_value

    value = os.getenv(environment_name)

    if value:
        return value

    raise ValueError(
        "%s is required"
        % environment_name
    )


def wait_for_initial_replay(
    service,
    timeout_seconds,
):
    """
    Wait until the initial DROP replay has ended.

    In the current QA environment, the DROP server closes
    the connection after replay. The service then starts its
    first reconnect from the next Soup sequence.
    """

    deadline = (
        time.monotonic()
        + float(timeout_seconds)
    )

    while time.monotonic() < deadline:
        status = service.status()

        if status["last_error"] is not None:
            raise RuntimeError(
                "DROP service failed: %s"
                % status["last_error"]
            )

        if status["reconnects"] >= 1:
            return

        if (
            not status["running"]
            and status["finished"]
        ):
            raise RuntimeError(
                "DROP service stopped before "
                "initial replay completed"
            )

        time.sleep(0.1)

    raise RuntimeError(
        "timed out waiting for initial DROP replay"
    )


def get_entity_record(
    application_state,
    entity_type,
    entity_id,
):
    if entity_type == "user":
        return application_state.users.get_user(
            entity_id
        )

    if entity_type == "firm":
        return application_state.firms.get_firm(
            entity_id
        )

    if entity_type == "market":
        return application_state.markets.get_market(
            entity_id
        )

    raise ValueError(
        "unsupported entity type: %s"
        % entity_type
    )


def wait_for_entity_record(
    application_state,
    entity_type,
    entity_id,
    timeout_seconds,
):
    if entity_type == "user":
        return application_state.wait_for_user(
            entity_id,
            timeout_seconds,
        )

    if entity_type == "firm":
        return application_state.wait_for_firm(
            entity_id,
            timeout_seconds,
        )

    if entity_type == "market":
        return application_state.wait_for_market(
            entity_id,
            timeout_seconds,
        )

    raise ValueError(
        "unsupported entity type: %s"
        % entity_type
    )


def update_entity_state(
    control_service,
    entity_type,
    entity_id,
    state,
    timeout_seconds,
):
    if entity_type == "user":
        return control_service.update_user_state(
            entity_id,
            state,
            timeout_seconds,
        )

    if entity_type == "firm":
        return control_service.update_firm_state(
            entity_id,
            state,
            timeout_seconds,
        )

    if entity_type == "market":
        return control_service.update_market_state(
            entity_id,
            state,
            timeout_seconds,
        )

    raise ValueError(
        "unsupported entity type: %s"
        % entity_type
    )


def print_record(label, record):
    if record is None:
        print("%s: not found" % label)
        return

    print(
        "%s: id=%d state=%s sequence=%d"
        % (
            label,
            get_record_id(record),
            record.state,
            record.last_sequence,
        )
    )


def get_record_id(record):
    if hasattr(record, "user_id"):
        return record.user_id

    if hasattr(record, "firm_id"):
        return record.firm_id

    if hasattr(record, "market_id"):
        return record.market_id

    raise ValueError(
        "unknown state record type: %s"
        % type(record).__name__
    )


def run(args):
    drop_username = (
        args.drop_username
        if args.drop_username
        else get_drop_username()
    )

    drop_password = (
        args.drop_password
        if args.drop_password
        else get_drop_password()
    )

    api_username = resolve_required(
        args.api_username,
        "API_USERNAME",
    )
    api_password = resolve_required(
        args.api_password,
        "API_PASSWORD",
    )

    drop_client = DropClient(
        host=args.host,
        port=args.drop_port,
        username=drop_username,
        password=drop_password,
        timeout_seconds=args.timeout,
    )

    drop_service = DropStateService(
        drop_client=drop_client,
        session=args.session,
        sequence_number=args.sequence,
        reconnect_delay_seconds=(
            args.reconnect_delay
        ),
        max_reconnect_attempts=None,
    )

    api_client = FaultInjectingApiClient(
        host=args.host,
        port=args.api_port,
        username=api_username,
        password=api_password,
        timeout_seconds=args.timeout,
        inject_read_failures=(
            args.inject_api_read_failures
        ),
    )

    original_state = None
    requested_confirmed = False

    try:
        drop_service.start()

        if not drop_service.wait_until_started(
            args.startup_timeout
        ):
            raise RuntimeError(
                "DROP state service did not start"
            )

        print(
            "DROP state service connected: "
            "requested_sequence=%d"
            % args.sequence
        )

        wait_for_initial_replay(
            drop_service,
            args.startup_timeout,
        )

        print(
            "initial DROP replay completed: "
            "next_soup_sequence=%s"
            % drop_client.next_sequence_number
        )

        record = wait_for_entity_record(
            application_state=drop_service.state,
            entity_type=args.entity,
            entity_id=args.entity_id,
            timeout_seconds=args.startup_timeout,
        )

        if record is None:
            raise RuntimeError(
                "%s %d was not found in DROP state"
                % (
                    args.entity,
                    args.entity_id,
                )
            )

        original_state = record.state

        print_record(
            "before request",
            record,
        )

        api_client.connect()

        control_service = ControlService(
            api_client=api_client,
            application_state=drop_service.state,
            confirmation_timeout_seconds=(
                args.confirmation_timeout
            ),
        )

        result = update_entity_state(
            control_service=control_service,
            entity_type=args.entity,
            entity_id=args.entity_id,
            state=args.state,
            timeout_seconds=(
                args.confirmation_timeout
            ),
        )

        requested_confirmed = True

        print(
            "request confirmed: "
            "entity=%s id=%d state=%s "
            "correlation_id=%d sequence=%d"
            % (
                result.entity_type,
                result.entity_id,
                result.requested_state,
                result.correlation_id,
                result.confirmed_sequence,
            )
        )

        current = get_entity_record(
            drop_service.state,
            args.entity,
            args.entity_id,
        )

        print_record(
            "after request",
            current,
        )

        if (
            not args.no_restore
            and original_state is not None
            and original_state != args.state
        ):
            restore_result = update_entity_state(
                control_service=control_service,
                entity_type=args.entity,
                entity_id=args.entity_id,
                state=original_state,
                timeout_seconds=(
                    args.confirmation_timeout
                ),
            )

            print(
                "restore confirmed: "
                "entity=%s id=%d state=%s "
                "correlation_id=%d sequence=%d"
                % (
                    restore_result.entity_type,
                    restore_result.entity_id,
                    restore_result.requested_state,
                    restore_result.correlation_id,
                    restore_result.confirmed_sequence,
                )
            )

            restored = get_entity_record(
                drop_service.state,
                args.entity,
                args.entity_id,
            )

            print_record(
                "after restore",
                restored,
            )

        elif args.no_restore:
            print(
                "restore skipped by --no-restore"
            )

        else:
            print(
                "restore not required; original "
                "state already matched requested state"
            )

        return 0

    except KeyboardInterrupt:
        print("\nstopped by user")
        return 130

    except (
        ControlError,
        ProtocolError,
        OSError,
        RuntimeError,
        ValueError,
    ) as exc:
        print(
            "control test failed: %s"
            % exc,
            file=sys.stderr,
        )

        if (
            requested_confirmed
            and not args.no_restore
            and original_state is not None
        ):
            print(
                "warning: verify the final entity "
                "state manually",
                file=sys.stderr,
            )

        return 1

    finally:
        try:
            api_client.close()
        except (ProtocolError, OSError):
            pass

        drop_service.stop()


def main():
    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s: %(message)s",
    )

    return run(parse_arguments())


if __name__ == "__main__":
    sys.exit(main())
