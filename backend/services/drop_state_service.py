import logging
from threading import (
    Event,
    RLock,
    Thread,
    current_thread,
)

from backend.checkpoint.session_checkpoint import (
    SessionCheckpointError,
    SessionCheckpointFormatError,
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
        session_checkpoint=None,
        restore_checkpoint_on_start=True,
        checkpoint_save_interval_messages=100,
        save_checkpoint_on_shutdown=True,
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

        checkpoint_save_interval_messages = int(
            checkpoint_save_interval_messages
        )

        if checkpoint_save_interval_messages < 0:
            raise ValueError(
                "checkpoint save interval cannot "
                "be negative"
            )

        self.drop_client = drop_client

        self.state = (
            application_state
            if application_state is not None
            else ApplicationState()
        )

        if (
            session_checkpoint is not None
            and session_checkpoint.application_state
            is not self.state
        ):
            raise ValueError(
                "session checkpoint must use the "
                "same ApplicationState instance"
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

        self.session_checkpoint = (
            session_checkpoint
        )
        self.restore_checkpoint_on_start = bool(
            restore_checkpoint_on_start
        )
        self.checkpoint_save_interval_messages = (
            checkpoint_save_interval_messages
        )
        self.save_checkpoint_on_shutdown = bool(
            save_checkpoint_on_shutdown
        )

        self._lock = RLock()
        self._thread = None

        self._stop_event = Event()
        self._started_event = Event()
        self._finished_event = Event()

        self._running = False
        self._connected = False
        self._connection_state = "stopped"
        self._state_ready = False
        self._last_error = None

        self._received_message_count = 0
        self._applied_message_count = 0

        self._connection_count = 0
        self._reconnect_count = 0
        self._full_replay_fallback_count = 0

        self._current_session = None

        self._checkpoint_restored = False
        self._checkpoint_save_count = 0
        self._checkpoint_last_saved_at = None
        self._checkpoint_last_error = None
        self._checkpoint_restored_trade_date = None
        self._checkpoint_restored_sequence = None

        self._messages_since_checkpoint = 0
        self._last_checkpoint_session = None
        self._last_checkpoint_sequence = None

    @property
    def running(self):
        with self._lock:
            return self._running

    @property
    def connected(self):
        with self._lock:
            return self._connected

    @property
    def connection_state(self):
        with self._lock:
            return self._connection_state

    @property
    def state_ready(self):
        with self._lock:
            return self._state_ready

    @property
    def drop_live(self):
        with self._lock:
            connected = self._connected

        return (
            connected
            and self.drop_client.connected
            and self.drop_client.live
        )

    @property
    def data_available(self):
        with self._lock:
            state_ready = self._state_ready

        return (
            state_ready
            and self.drop_live
        )

    @property
    def last_packet_age_seconds(self):
        return (
            self.drop_client
            .last_packet_age_seconds
        )

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

    @property
    def checkpoint_restored(self):
        with self._lock:
            return self._checkpoint_restored

    @property
    def checkpoint_save_count(self):
        with self._lock:
            return self._checkpoint_save_count

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

        self._set_connection_state(
            connected=False,
            connection_state="stopping",
            state_ready=False,
        )

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

            checkpoint_last_error = (
                str(self._checkpoint_last_error)
                if self._checkpoint_last_error
                is not None
                else None
            )

            connected = self._connected
            state_ready = self._state_ready
            connection_state = (
                self._connection_state
            )

            status = {
                "running": self._running,
                "connected": connected,
                "connection_state": (
                    connection_state
                ),
                "state_ready": state_ready,
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

                "checkpoint_enabled": (
                    self.session_checkpoint
                    is not None
                ),
                "checkpoint_restored": (
                    self._checkpoint_restored
                ),
                "checkpoint_saves": (
                    self._checkpoint_save_count
                ),
                "checkpoint_last_saved_at": (
                    self._checkpoint_last_saved_at
                ),
                "checkpoint_last_error": (
                    checkpoint_last_error
                ),
                "checkpoint_restored_trade_date": (
                    self
                    ._checkpoint_restored_trade_date
                ),
                "checkpoint_restored_sequence": (
                    self
                    ._checkpoint_restored_sequence
                ),
                "messages_since_checkpoint": (
                    self._messages_since_checkpoint
                ),
            }

        drop_live = (
            connected
            and self.drop_client.connected
            and self.drop_client.live
        )

        data_available = (
            state_ready
            and drop_live
        )

        effective_connection_state = (
            connection_state
        )

        if connected and not drop_live:
            effective_connection_state = "stale"

        status.update(
            {
                "connection_state": (
                    effective_connection_state
                ),
                "drop_live": drop_live,
                "data_available": (
                    data_available
                ),
                "last_packet_age_seconds": (
                    self.drop_client
                    .last_packet_age_seconds
                ),
                "liveness_timeout_seconds": (
                    self.drop_client
                    .liveness_timeout_seconds
                ),
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
        )

        return status

    def _prepare_run(self):
        self._stop_event.clear()
        self._started_event.clear()
        self._finished_event.clear()

        self._connected = False
        self._connection_state = "starting"
        self._state_ready = False
        self._last_error = None

        self._received_message_count = 0
        self._applied_message_count = 0

        self._connection_count = 0
        self._reconnect_count = 0
        self._full_replay_fallback_count = 0

        self._current_session = None

        self._checkpoint_restored = False
        self._checkpoint_save_count = 0
        self._checkpoint_last_saved_at = None
        self._checkpoint_last_error = None
        self._checkpoint_restored_trade_date = None
        self._checkpoint_restored_sequence = None

        self._messages_since_checkpoint = 0
        self._last_checkpoint_session = None
        self._last_checkpoint_sequence = None

    def _run(self):
        requested_session = self.session
        next_sequence_number = (
            self.sequence_number
        )
        full_replay_fallback_used = False

        try:
            (
                requested_session,
                next_sequence_number,
            ) = self._initialize_start_position(
                requested_session,
                next_sequence_number,
            )

            while not self._stop_event.is_set():
                try:
                    self.drop_client.connect(
                        session=requested_session,
                        sequence_number=(
                            next_sequence_number
                        ),
                    )

                    self._set_connection_state(
                        connected=True,
                        connection_state="connected",
                        state_ready=True,
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

                    self._set_connection_state(
                        connected=False,
                        connection_state="disconnected",
                        state_ready=False,
                    )

                    next_sequence_number = (
                        self._get_next_sequence(
                            next_sequence_number
                        )
                    )

                    self._save_checkpoint(
                        force=True
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
                        self._checkpoint_restored = False
                        self._checkpoint_restored_trade_date = None
                        self._checkpoint_restored_sequence = None

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

                    self._set_connection_state(
                        connected=False,
                        connection_state="starting",
                        state_ready=False,
                    )

                    self.state.clear()
                    self._delete_checkpoint()

                    try:
                        self.drop_client.close()

                    except (
                        ProtocolError,
                        OSError,
                    ):
                        pass

                    continue

                except SoupLoginRejectedError as exc:
                    if self._stop_event.is_set():
                        break

                    with self._lock:
                        checkpoint_was_restored = (
                            self._checkpoint_restored
                        )

                    if (
                        checkpoint_was_restored
                        and self.allow_full_replay_fallback
                        and not full_replay_fallback_used
                    ):
                        full_replay_fallback_used = True

                        with self._lock:
                            self._full_replay_fallback_count += 1
                            self._checkpoint_restored = False
                            self._checkpoint_restored_trade_date = None
                            self._checkpoint_restored_sequence = None
                            self._current_session = None

                        logger.warning(
                            "restored DROP Soup session was "
                            "rejected; deleting checkpoint and "
                            "starting full replay: reason=%s",
                            exc,
                        )

                        requested_session = ""
                        next_sequence_number = 1

                        self._set_connection_state(
                            connected=False,
                            connection_state="starting",
                            state_ready=False,
                        )

                        self.state.clear()
                        self._delete_checkpoint()

                        try:
                            self.drop_client.close()

                        except (
                            ProtocolError,
                            OSError,
                        ):
                            pass

                        continue

                    self._set_error(exc)

                    logger.error(
                        "DROP state service failed: %s",
                        exc,
                    )
                    break

                except DropFormatError as exc:
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

            if self.save_checkpoint_on_shutdown:
                self._save_checkpoint(
                    force=True
                )

            try:
                self.drop_client.close()

            except (
                ProtocolError,
                OSError,
            ):
                pass

            with self._lock:
                self._running = False
                self._connected = False
                self._connection_state = "stopped"
                self._state_ready = False
                self._thread = None

            self._finished_event.set()

    def _initialize_start_position(
        self,
        requested_session,
        next_sequence_number,
    ):
        if (
            self.session_checkpoint is None
            or not self.restore_checkpoint_on_start
        ):
            if self.clear_state_on_start:
                self.state.clear()

            return (
                requested_session,
                next_sequence_number,
            )

        try:
            restored = (
                self.session_checkpoint.restore()
            )

        except SessionCheckpointFormatError as exc:
            self._set_checkpoint_error(exc)

            logger.warning(
                "invalid session checkpoint; "
                "deleting it and starting full "
                "DROP replay: %s",
                exc,
            )

            self.state.clear()
            self._delete_checkpoint()

            return "", 1

        except SessionCheckpointError as exc:
            self._set_checkpoint_error(exc)

            logger.warning(
                "session checkpoint could not be "
                "loaded; starting without it: %s",
                exc,
            )

            if self.clear_state_on_start:
                self.state.clear()

            return (
                requested_session,
                next_sequence_number,
            )

        if restored is None:
            if self.clear_state_on_start:
                self.state.clear()

            return (
                requested_session,
                next_sequence_number,
            )

        restored_session = restored[
            "soup_session"
        ]
        restored_sequence = restored[
            "next_soup_sequence"
        ]

        with self._lock:
            self._checkpoint_restored = True
            self._checkpoint_restored_trade_date = (
                restored["trade_date"]
            )
            self._checkpoint_restored_sequence = (
                restored_sequence
            )
            self._current_session = (
                restored_session
            )
            self._last_checkpoint_session = (
                restored_session
            )
            self._last_checkpoint_sequence = (
                restored_sequence
            )

        logger.info(
            "session checkpoint restored: "
            "session=%r next_soup_sequence=%d "
            "trade_date=%d counts=%r",
            restored_session,
            restored_sequence,
            restored["trade_date"],
            restored["restored_counts"],
        )

        return (
            restored_session,
            restored_sequence,
        )

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
                self._messages_since_checkpoint += 1

                if applied:
                    self._applied_message_count += 1

            self._save_checkpoint(
                force=False
            )

    def _save_checkpoint(
        self,
        force=False,
    ):
        if self.session_checkpoint is None:
            return False

        with self._lock:
            messages_since_checkpoint = (
                self._messages_since_checkpoint
            )

        if not force:
            if (
                self.checkpoint_save_interval_messages
                == 0
            ):
                return False

            if (
                messages_since_checkpoint
                < self
                .checkpoint_save_interval_messages
            ):
                return False

        soup_session = (
            self.drop_client.accepted_session
        )

        if not soup_session:
            with self._lock:
                soup_session = (
                    self._current_session
                )

        next_soup_sequence = (
            self.drop_client.next_sequence_number
        )

        if (
            not soup_session
            or next_soup_sequence is None
            or self.state.session.trade_date is None
        ):
            return False

        with self._lock:
            if (
                soup_session
                == self._last_checkpoint_session
                and next_soup_sequence
                == self._last_checkpoint_sequence
                and self._messages_since_checkpoint
                == 0
            ):
                return False

        try:
            checkpoint = (
                self.session_checkpoint.save(
                    soup_session=soup_session,
                    next_soup_sequence=(
                        next_soup_sequence
                    ),
                )
            )

        except SessionCheckpointError as exc:
            self._set_checkpoint_error(exc)

            with self._lock:
                self._messages_since_checkpoint = 0

            logger.error(
                "failed to save session checkpoint: %s",
                exc,
            )
            return False

        with self._lock:
            self._checkpoint_save_count += 1
            self._checkpoint_last_saved_at = (
                checkpoint["saved_at"]
            )
            self._checkpoint_last_error = None
            self._messages_since_checkpoint = 0
            self._last_checkpoint_session = (
                checkpoint["soup_session"]
            )
            self._last_checkpoint_sequence = (
                checkpoint[
                    "next_soup_sequence"
                ]
            )

        logger.info(
            "session checkpoint saved: "
            "session=%r next_soup_sequence=%d "
            "trade_date=%d",
            checkpoint["soup_session"],
            checkpoint["next_soup_sequence"],
            checkpoint["trade_date"],
        )

        return True

    def _delete_checkpoint(self):
        if self.session_checkpoint is None:
            return False

        try:
            deleted = (
                self.session_checkpoint.delete()
            )

        except SessionCheckpointError as exc:
            self._set_checkpoint_error(exc)

            logger.error(
                "failed to delete session checkpoint: %s",
                exc,
            )
            return False

        with self._lock:
            self._last_checkpoint_session = None
            self._last_checkpoint_sequence = None
            self._messages_since_checkpoint = 0

        return deleted

    def _wait_for_reconnect(
        self,
        session,
        sequence_number,
        error=None,
    ):
        self._set_connection_state(
            connected=False,
            connection_state="reconnecting",
            state_ready=False,
        )

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
        if self.max_reconnect_attempts in (
            None,
            0,
        ):
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

    def _set_connection_state(
        self,
        connected,
        connection_state,
        state_ready=None,
    ):
        with self._lock:
            self._connected = bool(
                connected
            )
            self._connection_state = (
                connection_state
            )

            if state_ready is not None:
                self._state_ready = bool(
                    state_ready
                )

    def _set_error(self, error):
        with self._lock:
            self._last_error = error
            self._connected = False
            self._connection_state = "error"
            self._state_ready = False

    def _set_checkpoint_error(self, error):
        with self._lock:
            self._checkpoint_last_error = error