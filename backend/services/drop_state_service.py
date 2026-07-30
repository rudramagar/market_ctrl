import logging
from threading import (
    Event,
    RLock,
    Thread,
    current_thread,
)

from backend.protocol.errors import (
    DropFormatError,
    DropResumeError,
    ProtocolError,
    SoupLoginRejectedError,
)
from backend.state.application_state import (
    ApplicationState,
)


logger = logging.getLogger(__name__)


class DropStateService:
    """Maintain application state from the DROP stream."""

    def __init__(
        self,
        drop_client,
        application_state=None,
        session="",
        sequence_number=1,
        clear_state_on_start=True,
        reconnect_delay_seconds=2.0,
        max_reconnect_attempts=0,
        allow_full_replay_fallback=True,
    ):
        if drop_client is None:
            raise ValueError(
                "DROP client is required"
            )

        sequence_number = int(
            sequence_number
        )

        if sequence_number < 1:
            raise ValueError(
                "sequence number must be at least 1"
            )

        reconnect_delay_seconds = float(
            reconnect_delay_seconds
        )

        if reconnect_delay_seconds < 0:
            raise ValueError(
                "reconnect delay cannot be negative"
            )

        if max_reconnect_attempts is not None:
            max_reconnect_attempts = int(
                max_reconnect_attempts
            )

            if max_reconnect_attempts < 0:
                raise ValueError(
                    "maximum reconnect attempts "
                    "cannot be negative"
                )

        self.drop_client = drop_client

        self.state = (
            application_state
            if application_state is not None
            else ApplicationState()
        )

        self.session = (
            session
            if session is not None
            else ""
        )
        self.sequence_number = sequence_number

        self.clear_state_on_start = bool(
            clear_state_on_start
        )
        self.reconnect_delay_seconds = (
            reconnect_delay_seconds
        )
        self.max_reconnect_attempts = (
            max_reconnect_attempts
        )
        self.allow_full_replay_fallback = bool(
            allow_full_replay_fallback
        )

        self._lock = RLock()
        self._thread = None

        self._stop_event = Event()
        self._started_event = Event()
        self._finished_event = Event()

        self._running = False
        self._last_error = None

        self._received_message_count = 0
        self._applied_message_count = 0

        self._connection_count = 0
        self._reconnect_count = 0
        self._full_replay_fallback_count = 0

        self._current_session = None

    @property
    def running(self):
        with self._lock:
            return self._running

    @property
    def last_error(self):
        with self._lock:
            return self._last_error

    @property
    def received_message_count(self):
        with self._lock:
            return self._received_message_count

    @property
    def applied_message_count(self):
        with self._lock:
            return self._applied_message_count

    @property
    def connection_count(self):
        with self._lock:
            return self._connection_count

    @property
    def reconnect_count(self):
        with self._lock:
            return self._reconnect_count

    @property
    def full_replay_fallback_count(self):
        with self._lock:
            return (
                self._full_replay_fallback_count
            )

    @property
    def current_session(self):
        with self._lock:
            return self._current_session

    def start(self):
        """Start the worker in a background thread."""

        with self._lock:
            if self._running:
                raise RuntimeError(
                    "DROP state service is already running"
                )

            self._prepare_run()

            thread = Thread(
                target=self._run,
                name="drop-state-service",
            )
            thread.daemon = False

            self._thread = thread
            self._running = True

            try:
                thread.start()

            except Exception:
                self._thread = None
                self._running = False
                raise

    def run(self):
        """Run the worker in the current thread."""

        with self._lock:
            if self._running:
                raise RuntimeError(
                    "DROP state service is already running"
                )

            self._prepare_run()
            self._thread = None
            self._running = True

        self._run()

    def stop(
        self,
        timeout_seconds=5.0,
    ):
        """Request shutdown and wait for the worker."""

        self._stop_event.set()

        try:
            self.drop_client.close()

        except (
            ProtocolError,
            OSError,
        ):
            pass

        with self._lock:
            thread = self._thread

        if (
            thread is not None
            and thread is not current_thread()
        ):
            thread.join(timeout_seconds)

        return not self.running

    def wait_until_started(
        self,
        timeout_seconds=None,
    ):
        return self._started_event.wait(
            timeout_seconds
        )

    def wait(
        self,
        timeout_seconds=None,
    ):
        return self._finished_event.wait(
            timeout_seconds
        )

    def status(self):
        with self._lock:
            last_error = (
                str(self._last_error)
                if self._last_error is not None
                else None
            )

            return {
                "running": self._running,
                "started": (
                    self._started_event.is_set()
                ),
                "finished": (
                    self._finished_event.is_set()
                ),
                "received_messages": (
                    self._received_message_count
                ),
                "applied_messages": (
                    self._applied_message_count
                ),
                "connections": (
                    self._connection_count
                ),
                "reconnects": (
                    self._reconnect_count
                ),
                "full_replay_fallbacks": (
                    self
                    ._full_replay_fallback_count
                ),
                "current_session": (
                    self._current_session
                ),
                "last_error": last_error,
                "next_soup_sequence": (
                    self.drop_client
                    .next_sequence_number
                ),
                "requested_session": (
                    self.drop_client
                    .requested_session
                ),
                "accepted_session": (
                    self.drop_client
                    .accepted_session
                ),
                "requested_sequence": (
                    self.drop_client
                    .requested_sequence_number
                ),
                "accepted_sequence": (
                    self.drop_client
                    .accepted_sequence_number
                ),
                "disconnect_reason": (
                    self.drop_client
                    .last_disconnect_reason
                ),
                "state_counts": (
                    self.state.counts()
                ),
                "unsupported_templates": sorted(
                    self.drop_client
                    .unsupported_template_ids
                ),
            }

    def _prepare_run(self):
        self._stop_event.clear()
        self._started_event.clear()
        self._finished_event.clear()

        self._last_error = None

        self._received_message_count = 0
        self._applied_message_count = 0

        self._connection_count = 0
        self._reconnect_count = 0
        self._full_replay_fallback_count = 0

        self._current_session = None

        if self.clear_state_on_start:
            self.state.clear()

    def _run(self):
        requested_session = self.session
        next_sequence_number = (
            self.sequence_number
        )
        full_replay_fallback_used = False

        try:
            while not self._stop_event.is_set():
                try:
                    self.drop_client.connect(
                        session=requested_session,
                        sequence_number=(
                            next_sequence_number
                        ),
                    )

                    accepted_session = (
                        self.drop_client
                        .accepted_session
                    )

                    if accepted_session:
                        requested_session = (
                            accepted_session
                        )

                    with self._lock:
                        self._connection_count += 1
                        self._current_session = (
                            requested_session
                        )

                    self._started_event.set()

                    self._receive_messages()

                    next_sequence_number = (
                        self._get_next_sequence(
                            next_sequence_number
                        )
                    )

                    if self._stop_event.is_set():
                        break

                    disconnect_reason = (
                        self.drop_client
                        .last_disconnect_reason
                    )

                    if (
                        disconnect_reason
                        == "end_of_session"
                    ):
                        logger.info(
                            "DROP end of session received: "
                            "session=%r",
                            requested_session,
                        )
                        break

                    if (
                        disconnect_reason
                        != "connection_closed"
                    ):
                        break

                    if not self._wait_for_reconnect(
                        session=requested_session,
                        sequence_number=(
                            next_sequence_number
                        ),
                    ):
                        break

                except DropResumeError as exc:
                    if self._stop_event.is_set():
                        break

                    if (
                        not self
                        .allow_full_replay_fallback
                        or full_replay_fallback_used
                    ):
                        self._set_error(exc)

                        logger.error(
                            "DROP resume failed and full "
                            "replay fallback is unavailable: "
                            "%s",
                            exc,
                        )
                        break

                    full_replay_fallback_used = True

                    with self._lock:
                        self._full_replay_fallback_count += 1

                    requested_session = (
                        exc.accepted_session
                        if exc.accepted_session
                        else ""
                    )
                    next_sequence_number = 1

                    logger.warning(
                        "DROP resume checkpoint was not "
                        "accepted; clearing state and "
                        "starting full replay: "
                        "session=%r sequence=1",
                        requested_session,
                    )

                    self.state.clear()

                    try:
                        self.drop_client.close()

                    except (
                        ProtocolError,
                        OSError,
                    ):
                        pass

                    continue

                except (
                    SoupLoginRejectedError,
                    DropFormatError,
                ) as exc:
                    self._set_error(exc)

                    logger.error(
                        "DROP state service failed: %s",
                        exc,
                    )
                    break

                except (
                    ProtocolError,
                    OSError,
                ) as exc:
                    if self._stop_event.is_set():
                        break

                    next_sequence_number = (
                        self._get_next_sequence(
                            next_sequence_number
                        )
                    )

                    if not self._can_reconnect():
                        self._set_error(exc)

                        logger.error(
                            "DROP state service failed: %s",
                            exc,
                        )
                        break

                    if not self._wait_for_reconnect(
                        session=requested_session,
                        sequence_number=(
                            next_sequence_number
                        ),
                        error=exc,
                    ):
                        break

        except Exception as exc:
            self._set_error(exc)

            logger.exception(
                "unexpected DROP state service failure"
            )

        finally:
            self._started_event.set()

            try:
                self.drop_client.close()

            except (
                ProtocolError,
                OSError,
            ):
                pass

            with self._lock:
                self._running = False
                self._thread = None

            self._finished_event.set()

    def _receive_messages(self):
        while not self._stop_event.is_set():
            message = self.drop_client.receive()

            if message is None:
                return

            applied = self.state.apply(
                message
            )

            with self._lock:
                self._received_message_count += 1

                if applied:
                    self._applied_message_count += 1

    def _wait_for_reconnect(
        self,
        session,
        sequence_number,
        error=None,
    ):
        if not self._can_reconnect():
            return False

        with self._lock:
            self._reconnect_count += 1
            reconnect_count = (
                self._reconnect_count
            )

        if error is None:
            logger.warning(
                "DROP connection closed; "
                "reconnecting: session=%r "
                "Soup sequence=%d attempt=%d",
                session,
                sequence_number,
                reconnect_count,
            )

        else:
            logger.warning(
                "DROP connection error: %s; "
                "reconnecting: session=%r "
                "Soup sequence=%d attempt=%d",
                error,
                session,
                sequence_number,
                reconnect_count,
            )

        stopped = self._stop_event.wait(
            self.reconnect_delay_seconds
        )

        return not stopped

    def _can_reconnect(self):
        if self.max_reconnect_attempts is None:
            return True

        with self._lock:
            return (
                self._reconnect_count
                < self.max_reconnect_attempts
            )

    def _get_next_sequence(
        self,
        fallback_sequence,
    ):
        next_sequence = (
            self.drop_client
            .next_sequence_number
        )

        if next_sequence is None:
            return fallback_sequence

        return next_sequence

    def _set_error(self, error):
        with self._lock:
            self._last_error = error
