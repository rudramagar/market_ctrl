import logging
from threading import (
    Event,
    RLock,
    Thread,
    current_thread,
)

from backend.protocol.errors import ProtocolError
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
    ):
        if drop_client is None:
            raise ValueError(
                "DROP client is required"
            )

        sequence_number = int(sequence_number)

        if sequence_number < 0:
            raise ValueError(
                "sequence number cannot be negative"
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

        self._lock = RLock()
        self._thread = None
        self._stop_event = Event()
        self._started_event = Event()
        self._finished_event = Event()

        self._running = False
        self._last_error = None
        self._received_message_count = 0
        self._applied_message_count = 0

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

    def start(self):
        """Start the DROP worker in a background thread."""

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
        """Run the DROP worker in the current thread."""

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
                "last_error": last_error,
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

        if self.clear_state_on_start:
            self.state.clear()

    def _run(self):
        try:
            self.drop_client.connect(
                session=self.session,
                sequence_number=self.sequence_number,
            )

            self._started_event.set()

            while not self._stop_event.is_set():
                message = self.drop_client.receive()

                if message is None:
                    break

                applied = self.state.apply(message)

                with self._lock:
                    self._received_message_count += 1

                    if applied:
                        self._applied_message_count += 1

        except (ProtocolError, OSError) as exc:
            if not self._stop_event.is_set():
                self._set_error(exc)

                logger.error(
                    "DROP state service failed: %s",
                    exc,
                )

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

    def _set_error(self, error):
        with self._lock:
            self._last_error = error
