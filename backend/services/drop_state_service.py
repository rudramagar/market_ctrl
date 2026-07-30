import logging
from threading import (
    Event,
    RLock,
    Thread,
    current_thread,
)

from backend.protocol.errors import (
    DropFormatError,
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
    ):
        if drop_client is None:
            raise ValueError(
                "DROP client is required"
            )

        sequence_number = int(sequence_number)

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

        self.session = session
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

        self._lock = RLock()
        self._thread = None
        self._stop_event = Event()
        self._started_event = Event()
        self._finished_event = Event()

        self._running = False
        self._last_error = None
        self._received_message_count = 0
        self._applied_message_count = 0
        self._reconnect_count = 0

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
    def reconnect_count(self):
        with self._lock:
            return self._reconnect_count

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

    def stop(self, timeout_seconds=5.0):
        """Request shutdown and wait for the worker."""

        self._stop_event.set()

        try:
            self.drop_client.close()
        except (ProtocolError, OSError):
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
                "reconnects": self._reconnect_count,
                "last_error": last_error,
                "next_soup_sequence": (
                    self.drop_client
                    .next_sequence_number
                ),
                "disconnect_reason": (
                    self.drop_client
                    .last_disconnect_reason
                ),
                "state_counts": self.state.counts(),
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
        self._reconnect_count = 0

        if self.clear_state_on_start:
            self.state.clear()

    def _run(self):
        next_sequence_number = (
            self.sequence_number
        )

        try:
            while not self._stop_event.is_set():
                try:
                    self.drop_client.connect(
                        session=self.session,
                        sequence_number=(
                            next_sequence_number
                        ),
                    )

                    self._started_event.set()

                    self._receive_messages()

                    if self._stop_event.is_set():
                        break

                    next_sequence_number = (
                        self._get_next_sequence(
                            next_sequence_number
                        )
                    )

                    disconnect_reason = (
                        self.drop_client
                        .last_disconnect_reason
                    )

                    if disconnect_reason == (
                        "end_of_session"
                    ):
                        logger.info(
                            "DROP end of session received"
                        )
                        break

                    if disconnect_reason != (
                        "connection_closed"
                    ):
                        break

                    if not self._wait_for_reconnect(
                        next_sequence_number
                    ):
                        break

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

                except (ProtocolError, OSError) as exc:
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
                        next_sequence_number,
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
            except (ProtocolError, OSError):
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

            applied = self.state.apply(message)

            with self._lock:
                self._received_message_count += 1

                if applied:
                    self._applied_message_count += 1

    def _wait_for_reconnect(
        self,
        sequence_number,
        error=None,
    ):
        if not self._can_reconnect():
            return False

        with self._lock:
            self._reconnect_count += 1
            reconnect_count = self._reconnect_count

        if error is None:
            logger.warning(
                "DROP connection closed; "
                "reconnecting from Soup sequence %d "
                "(attempt %d)",
                sequence_number,
                reconnect_count,
            )
        else:
            logger.warning(
                "DROP connection error: %s; "
                "reconnecting from Soup sequence %d "
                "(attempt %d)",
                error,
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
