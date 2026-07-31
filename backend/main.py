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
from backend.protocol.drop.client import (
    DropClient,
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


logger = logging.getLogger(__name__)


def parse_arguments():
    parser = argparse.ArgumentParser(
        description=(
            "Market Control backend DROP state service"
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
            "Requested Soup session when no "
            "checkpoint is restored"
        ),
    )

    parser.add_argument(
        "-s",
        "--sequence",
        type=int,
        default=1,
        help=(
            "Requested Soup sequence when no "
            "checkpoint is restored"
        ),
    )

    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Socket timeout in seconds",
    )

    parser.add_argument(
        "--reconnect-delay",
        type=float,
        default=2.0,
        help="Delay between reconnect attempts",
    )

    parser.add_argument(
        "--reconnect-attempts",
        type=int,
        default=None,
        help=(
            "Maximum reconnect attempts. "
            "The default is unlimited"
        ),
    )

    parser.add_argument(
        "--disable-checkpoint",
        action="store_true",
        help=(
            "Disable checkpoint save and restore"
        ),
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


def log_service_status(service):
    status = service.status()
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

    service = create_drop_service(
        args
    )

    try:
        service.start()

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

        while service.running:
            if shutdown_event.wait(1.0):
                break

        if shutdown_event.is_set():
            service.stop(
                timeout_seconds=10.0
            )

        else:
            service.wait()

    finally:
        service.stop(
            timeout_seconds=10.0
        )

    log_service_status(
        service
    )

    if service.last_error is not None:
        logger.error(
            "DROP state service failed: %s",
            service.last_error,
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
