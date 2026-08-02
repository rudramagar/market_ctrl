#!/usr/bin/env python3

import argparse
import logging
import os
import signal
import sys
from threading import Event

from backend.checkpoint.session_checkpoint import (
    SessionCheckpoint,
)
from backend.checkpoint.snapshot_store import (
    SnapshotStore,
)
from backend.protocol.api.client import (
    ApiClient,
)
from backend.protocol.drop.client import (
    DropClient,
)
from backend.protocol.errors import (
    ProtocolError,
)
from backend.services.control_service import (
    ControlService,
)
from backend.services.drop_state_service import (
    DropStateService,
)
from backend.settings import (
    SettingsError,
    get_checkpoint_file,
    get_checkpoint_restore_enabled,
    get_checkpoint_save_interval_messages,
    get_checkpoint_save_on_shutdown,
    get_drop_password,
    get_drop_username,
)
from backend.state.application_state import (
    ApplicationState,
)
from backend.web.control_api import (
    ControlApi,
)
from backend.web.http_app import (
    create_http_app,
)
from backend.web.http_server import (
    HttpServer,
)
from backend.web.state_api import (
    StateApi,
)
from backend.web.state_event_stream import (
    StateEventStream,
)


logger = logging.getLogger(__name__)

class HealthRequestLogFilter(logging.Filter):
    """Suppress repetitive successful health-check access logs."""

    def filter(self, record):
        message = record.getMessage()

        return not (
            '"GET /health ' in message
            and (
                '" 200 ' in message
                or '" 503 ' in message
            )
        )

def parse_arguments():
    parser = argparse.ArgumentParser(
        description=(
            "Market Control backend service"
        )
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
        "--session",
        default="",
        help=(
            "Requested DROP Soup session when no "
            "checkpoint is restored"
        ),
    )

    parser.add_argument(
        "-s",
        "--sequence",
        type=int,
        default=1,
        help=(
            "Requested DROP Soup sequence when no "
            "checkpoint is restored"
        ),
    )

    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="DROP socket timeout in seconds",
    )

    parser.add_argument(
        "--reconnect-delay",
        type=float,
        default=2.0,
        help="Delay between DROP reconnect attempts",
    )

    parser.add_argument(
        "--reconnect-attempts",
        type=int,
        default=None,
        help=(
            "Maximum DROP reconnect attempts. "
            "The default is unlimited"
        ),
    )

    parser.add_argument(
        "--disable-checkpoint",
        action="store_true",
        help="Disable checkpoint save and restore",
    )

    parser.add_argument(
        "--api-host",
        default=None,
        help=(
            "Mercury API host. The DROP host is "
            "used by default"
        ),
    )

    parser.add_argument(
        "--api-port",
        type=int,
        default=11005,
        help="Mercury API SoupBinTCP port",
    )

    parser.add_argument(
        "--api-session",
        default="",
        help="Requested Mercury API Soup session",
    )

    parser.add_argument(
        "--api-sequence",
        type=int,
        default=0,
        help="Requested Mercury API Soup sequence",
    )

    parser.add_argument(
        "--api-timeout",
        type=float,
        default=10.0,
        help="Mercury API socket timeout",
    )

    parser.add_argument(
        "--api-response-recovery-attempts",
        type=int,
        default=1,
        help=(
            "Attempts to recover an API response "
            "without resending its request"
        ),
    )

    parser.add_argument(
        "--api-reconnect-delay",
        type=float,
        default=0.5,
        help="API response recovery delay",
    )

    parser.add_argument(
        "--control-timeout",
        type=float,
        default=10.0,
        help="DROP control confirmation timeout",
    )

    parser.add_argument(
        "--disable-control",
        action="store_true",
        help="Disable Mercury API control endpoints",
    )

    parser.add_argument(
        "--http-host",
        default="127.0.0.1",
        help=(
            "HTTP listener address. Use 0.0.0.0 "
            "inside Kubernetes"
        ),
    )

    parser.add_argument(
        "--http-port",
        type=int,
        default=8080,
        help="HTTP listener port",
    )

    parser.add_argument(
        "--disable-http",
        action="store_true",
        help="Disable the HTTP server",
    )

    parser.add_argument(
        "--log-level",
        choices=(
            "DEBUG",
            "INFO",
            "WARNING",
            "ERROR",
        ),
        default="INFO",
        help="Application log level",
    )

    return parser.parse_args()


def configure_logging(log_level):
    logging.basicConfig(
        level=getattr(
            logging,
            log_level,
        ),
        format=(
            "%(asctime)s "
            "%(levelname)s "
            "%(name)s: "
            "%(message)s"
        ),
    )

    logging.getLogger("werkzeug").addFilter(HealthRequestLogFilter())


def ensure_parent_directory(path):
    parent_directory = os.path.dirname(
        path
    )

    if not parent_directory:
        return

    try:
        os.makedirs(
            parent_directory,
            exist_ok=True,
        )

    except OSError as exc:
        raise SettingsError(
            "cannot create checkpoint directory "
            "%s: %s"
            % (
                parent_directory,
                exc,
            )
        ) from exc


def get_required_environment(
    primary_name,
    fallback_name,
):
    value = os.getenv(
        primary_name
    )

    if value:
        return value

    value = os.getenv(
        fallback_name
    )

    if value:
        return value

    raise SettingsError(
        "%s or %s is required"
        % (
            primary_name,
            fallback_name,
        )
    )


def create_session_checkpoint(
    application_state,
    checkpoint_disabled,
):
    if checkpoint_disabled:
        logger.warning(
            "session checkpointing is disabled"
        )
        return None

    checkpoint_file = get_checkpoint_file()

    ensure_parent_directory(
        checkpoint_file
    )

    snapshot_store = SnapshotStore(
        checkpoint_file
    )

    logger.info(
        "session checkpoint file: %s",
        checkpoint_file,
    )

    return SessionCheckpoint(
        snapshot_store=snapshot_store,
        application_state=application_state,
    )


def create_drop_service(args):
    application_state = ApplicationState()

    session_checkpoint = (
        create_session_checkpoint(
            application_state=(
                application_state
            ),
            checkpoint_disabled=(
                args.disable_checkpoint
            ),
        )
    )

    drop_client = DropClient(
        host=args.host,
        port=args.port,
        username=get_drop_username(),
        password=get_drop_password(),
        timeout_seconds=args.timeout,
    )

    checkpoint_enabled = (
        session_checkpoint is not None
    )

    return DropStateService(
        drop_client=drop_client,
        application_state=application_state,
        session=args.session,
        sequence_number=args.sequence,
        reconnect_delay_seconds=(
            args.reconnect_delay
        ),
        max_reconnect_attempts=(
            args.reconnect_attempts
        ),
        allow_full_replay_fallback=True,
        session_checkpoint=session_checkpoint,
        restore_checkpoint_on_start=(
            checkpoint_enabled
            and get_checkpoint_restore_enabled()
        ),
        checkpoint_save_interval_messages=(
            get_checkpoint_save_interval_messages()
            if checkpoint_enabled
            else 0
        ),
        save_checkpoint_on_shutdown=(
            checkpoint_enabled
            and get_checkpoint_save_on_shutdown()
        ),
    )


def create_control_components(
    args,
    drop_service,
):
    if args.disable_control:
        logger.warning(
            "Mercury API control is disabled"
        )
        return None, None

    api_username = (
        get_required_environment(
            "MARKET_CONTROL_API_USERNAME",
            "API_USERNAME",
        )
    )

    api_password = (
        get_required_environment(
            "MARKET_CONTROL_API_PASSWORD",
            "API_PASSWORD",
        )
    )

    api_host = (
        args.api_host
        if args.api_host
        else args.host
    )

    api_client = ApiClient(
        host=api_host,
        port=args.api_port,
        username=api_username,
        password=api_password,
        session=args.api_session,
        sequence=args.api_sequence,
        timeout_seconds=args.api_timeout,
        response_recovery_attempts=(
            args.api_response_recovery_attempts
        ),
        reconnect_delay_seconds=(
            args.api_reconnect_delay
        ),
        close_after_request=True,
    )

    control_service = ControlService(
        api_client=api_client,
        application_state=(
            drop_service.state
        ),
        confirmation_timeout_seconds=(
            args.control_timeout
        ),
    )

    control_api = ControlApi(
        control_service=control_service,
        application_state=(
            drop_service.state
        ),
        default_timeout_seconds=(
            args.control_timeout
        ),
    )

    logger.info(
        "Mercury API control configured: "
        "host=%s port=%d recovery_attempts=%d "
        "confirmation_timeout=%.3f",
        api_host,
        args.api_port,
        args.api_response_recovery_attempts,
        args.control_timeout,
    )

    return api_client, control_api


def create_web_server(
    args,
    drop_service,
    control_api,
):
    if args.disable_http:
        logger.warning(
            "HTTP server is disabled"
        )
        return None

    state_api = StateApi(
        application_state=(
            drop_service.state
        ),
        drop_service=drop_service,
    )

    state_event_stream = StateEventStream(
        event_bus=(
            drop_service.state.event_bus
        ),
        heartbeat_seconds=15.0,
        batch_size=100,
    )

    http_application = create_http_app(
        state_api=state_api,
        state_event_stream=(
            state_event_stream
        ),
        control_api=control_api,
    )

    return HttpServer(
        application=http_application,
        host=args.http_host,
        port=args.http_port,
        threaded=True,
    )


def log_service_status(
    drop_service,
    http_server,
):
    status = drop_service.status()
    counts = status["state_counts"]

    logger.info(
        "DROP service stopped: "
        "session=%r next_sequence=%r "
        "connections=%d reconnects=%d "
        "full_replay_fallbacks=%d",
        status["current_session"],
        status["next_soup_sequence"],
        status["connections"],
        status["reconnects"],
        status["full_replay_fallbacks"],
    )

    logger.info(
        "application state: "
        "users=%d firms=%d markets=%d "
        "user_types=%d user_markets=%d "
        "system_events=%d",
        counts["users"],
        counts["firms"],
        counts["markets"],
        counts["user_types"],
        counts["user_markets"],
        counts["system_events"],
    )

    logger.info(
        "latest state event ID: %d",
        drop_service.state
        .event_bus.latest_event_id,
    )

    if status["checkpoint_enabled"]:
        logger.info(
            "checkpoint status: "
            "restored=%s saves=%d "
            "restored_sequence=%r "
            "last_saved_at=%r error=%r",
            status["checkpoint_restored"],
            status["checkpoint_saves"],
            status[
                "checkpoint_restored_sequence"
            ],
            status[
                "checkpoint_last_saved_at"
            ],
            status[
                "checkpoint_last_error"
            ],
        )

    if http_server is not None:
        logger.info(
            "HTTP server status: "
            "running=%s host=%r port=%r error=%r",
            http_server.running,
            http_server.bound_host,
            http_server.bound_port,
            (
                str(http_server.last_error)
                if http_server.last_error
                is not None
                else None
            ),
        )


def close_api_client(api_client):
    if api_client is None:
        return

    try:
        api_client.close()

    except (
        ProtocolError,
        OSError,
    ) as exc:
        logger.warning(
            "API client shutdown failed: %s",
            exc,
        )


def run(args):
    shutdown_event = Event()

    def request_shutdown(
        signal_number,
        frame,
    ):
        del frame

        logger.info(
            "shutdown requested: signal=%d",
            signal_number,
        )

        shutdown_event.set()

    signal.signal(
        signal.SIGINT,
        request_shutdown,
    )

    signal.signal(
        signal.SIGTERM,
        request_shutdown,
    )

    drop_service = create_drop_service(
        args
    )

    api_client, control_api = (
        create_control_components(
            args=args,
            drop_service=drop_service,
        )
    )

    http_server = create_web_server(
        args=args,
        drop_service=drop_service,
        control_api=control_api,
    )

    try:
        drop_service.start()

        logger.info(
            "DROP state service started: "
            "host=%s port=%d "
            "requested_session=%r "
            "requested_sequence=%d",
            args.host,
            args.port,
            args.session,
            args.sequence,
        )

        if http_server is not None:
            http_server.start()

        while not shutdown_event.wait(1.0):
            if drop_service.last_error is not None:
                logger.error(
                    "DROP service stopped with error"
                )
                break

            if not drop_service.running:
                logger.warning(
                    "DROP service is no longer running"
                )
                break

            if http_server is not None:
                if http_server.last_error is not None:
                    logger.error(
                        "HTTP server stopped with error"
                    )
                    break

                if not http_server.running:
                    logger.warning(
                        "HTTP server is no longer running"
                    )
                    break

    finally:
        # Stop new HTTP control requests first.
        if http_server is not None:
            http_server.stop(
                timeout_seconds=10.0
            )

        # No request can now use the API client.
        close_api_client(
            api_client
        )

        # Save the final checkpoint and close DROP.
        drop_service.stop(
            timeout_seconds=10.0
        )

    log_service_status(
        drop_service=drop_service,
        http_server=http_server,
    )

    if drop_service.last_error is not None:
        logger.error(
            "DROP state service failed: %s",
            drop_service.last_error,
        )
        return 1

    if (
        http_server is not None
        and http_server.last_error is not None
    ):
        logger.error(
            "HTTP server failed: %s",
            http_server.last_error,
        )
        return 1

    return 0


def main():
    args = parse_arguments()

    configure_logging(
        args.log_level
    )

    try:
        return run(args)

    except SettingsError as exc:
        logger.error(
            "configuration error: %s",
            exc,
        )
        return 2

    except KeyboardInterrupt:
        return 0

    except Exception:
        logger.exception(
            "unexpected application failure"
        )
        return 1


if __name__ == "__main__":
    sys.exit(
        main()
    )
