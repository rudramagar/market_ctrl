import logging
import threading
import time

from backend.protocol.api.message_format import ApiMessageFormat
from backend.protocol.api.messages import (
    ApiMessageType,
    FirmState,
    MarketState,
    UserState,
)
from backend.protocol.errors import (
    ApiConnectionLostError,
    ApiError,
    ApiRequestRejectedError,
    ConnectionClosedError,
    ProtocolError,
    SoupEndOfSessionError,
    TransportError,
)
from backend.protocol.soup.session import SoupSession
from backend.protocol.transport.socket import TcpSocket


logger = logging.getLogger(__name__)


class ApiClient:
    """Matching-engine API client with safe response recovery."""

    def __init__(
        self,
        host,
        port,
        username,
        password,
        session="",
        sequence=0,
        timeout_seconds=10.0,
        response_recovery_attempts=1,
        reconnect_delay_seconds=0.5,
    ):
        if not host:
            raise ValueError("API host is required")

        if not username:
            raise ValueError("API username is required")

        if password is None:
            raise ValueError("API password is required")

        port = int(port)
        sequence = int(sequence)

        response_recovery_attempts = int(
            response_recovery_attempts
        )
        reconnect_delay_seconds = float(
            reconnect_delay_seconds
        )

        if port < 1 or port > 65535:
            raise ValueError(
                "invalid API port: %d" % port
            )

        if sequence < 0:
            raise ValueError(
                "API sequence cannot be negative"
            )

        if response_recovery_attempts < 0:
            raise ValueError(
                "response recovery attempts "
                "cannot be negative"
            )

        if reconnect_delay_seconds < 0:
            raise ValueError(
                "reconnect delay cannot be negative"
            )

        self.host = host
        self.port = port
        self.username = username
        self.password = password

        self.requested_session = session or ""
        self.requested_sequence = sequence

        self.timeout_seconds = float(
            timeout_seconds
        )
        self.response_recovery_attempts = (
            response_recovery_attempts
        )
        self.reconnect_delay_seconds = (
            reconnect_delay_seconds
        )

        self.message_format = ApiMessageFormat()
        self.soup_session = (
            self._new_soup_session()
        )

        self._login_accepted = None
        self._accepted_session = None
        self._next_sequence = sequence
        self._reconnect_count = 0

        self._connection_lock = (
            threading.RLock()
        )
        self._request_lock = (
            threading.Lock()
        )
        self._correlation_lock = (
            threading.Lock()
        )

        self._last_correlation_id = 0

    @property
    def connected(self):
        return (
            self._login_accepted is not None
            and self.soup_session is not None
            and self.soup_session.connected
        )

    @property
    def accepted_session(self):
        return self._accepted_session

    @property
    def next_sequence(self):
        return self._next_sequence

    @property
    def reconnect_count(self):
        return self._reconnect_count

    def connect(self):
        """Open the initial API Soup session."""

        with self._connection_lock:
            if self.connected:
                return self._login_accepted

            return self._connect_at(
                session=self.requested_session,
                sequence=self.requested_sequence,
                require_exact=bool(
                    self.requested_session
                ),
            )

    def update_user_state(
        self,
        user_id,
        state,
    ):
        user_id = int(user_id)

        if user_id <= 0:
            raise ValueError(
                "user_id must be positive"
            )

        return self._execute_request(
            ApiMessageType
            .UPDATE_USER_STATE_REQUEST,
            {
                "user_id": user_id,
                "suspension_status": (
                    self._normalize_user_state(
                        state
                    )
                ),
            },
        )

    def update_firm_state(
        self,
        firm_id,
        state,
    ):
        firm_id = int(firm_id)

        if firm_id <= 0:
            raise ValueError(
                "firm_id must be positive"
            )

        return self._execute_request(
            ApiMessageType
            .UPDATE_FIRM_STATE_REQUEST,
            {
                "firm_id": firm_id,
                "suspension_status": (
                    self._normalize_firm_state(
                        state
                    )
                ),
            },
        )

    def update_market_state(
        self,
        market_id,
        state,
    ):
        market_id = int(market_id)

        if market_id <= 0:
            raise ValueError(
                "market_id must be positive"
            )

        return self._execute_request(
            ApiMessageType
            .UPDATE_MARKET_STATE_REQUEST,
            {
                "market_id": market_id,
                "suspension_status": (
                    MarketState.validate(state)
                ),
            },
        )

    def close(self):
        """
        Close the API session and reset recovery
        information.
        """

        with self._connection_lock:
            soup_session = self.soup_session
            was_connected = self.connected

            self._login_accepted = None
            self._accepted_session = None
            self._next_sequence = (
                self.requested_sequence
            )

            if soup_session is not None:
                try:
                    if was_connected:
                        soup_session.logout()

                except (
                    ProtocolError,
                    OSError,
                ):
                    pass

                finally:
                    soup_session.close()

            self.soup_session = (
                self._new_soup_session()
            )

    def _execute_request(
        self,
        message_type,
        values,
    ):
        correlation_id = (
            self._next_correlation_id()
        )

        request_values = dict(values)
        request_values[
            "correlation_id"
        ] = correlation_id

        request = self.message_format.encode(
            message_type,
            request_values,
        )

        with self._request_lock:
            self._ensure_connected(
                correlation_id
            )

            try:
                self.soup_session.send_unsequenced(
                    request
                )

                self._receive_result(
                    correlation_id
                )

                return correlation_id

            except ApiRequestRejectedError:
                raise

            except (
                ConnectionClosedError,
                SoupEndOfSessionError,
                TransportError,
                OSError,
            ) as exc:
                self._mark_disconnected()

                self._recover_response(
                    correlation_id,
                    exc,
                )

                return correlation_id

    def _ensure_connected(
        self,
        correlation_id,
    ):
        """
        Reconnect before sending when the local
        connection is already known to be closed.
        """

        if self.connected:
            return

        try:
            with self._connection_lock:
                if self.connected:
                    return

                if self._accepted_session:
                    self._connect_at(
                        session=(
                            self._accepted_session
                        ),
                        sequence=(
                            self._next_sequence
                        ),
                        require_exact=True,
                    )

                    self._reconnect_count += 1

                else:
                    self._connect_at(
                        session=(
                            self.requested_session
                        ),
                        sequence=(
                            self.requested_sequence
                        ),
                        require_exact=bool(
                            self.requested_session
                        ),
                    )

        except Exception as exc:
            self._mark_disconnected()

            raise ApiConnectionLostError(
                correlation_id=correlation_id,
                request_may_have_been_sent=False,
                cause=exc,
            )

    def _recover_response(
        self,
        correlation_id,
        initial_error,
    ):
        """
        Recover the response without resending
        the API request.

        The request may already have reached the
        matching engine. Reconnect to the same
        Soup session and resume the response stream
        from the next expected sequence.
        """

        last_error = initial_error

        for attempt in range(
            1,
            self.response_recovery_attempts + 1,
        ):
            if self.reconnect_delay_seconds:
                time.sleep(
                    self.reconnect_delay_seconds
                )

            try:
                with self._connection_lock:
                    self._connect_at(
                        session=(
                            self._accepted_session
                        ),
                        sequence=(
                            self._next_sequence
                        ),
                        require_exact=True,
                    )

                    self._reconnect_count += 1

                logger.warning(
                    "API response recovery: "
                    "correlation_id=%d "
                    "attempt=%d "
                    "session=%r "
                    "sequence=%d",
                    correlation_id,
                    attempt,
                    self._accepted_session,
                    self._next_sequence,
                )

                self._receive_result(
                    correlation_id
                )

                return

            except ApiRequestRejectedError:
                raise

            except Exception as exc:
                last_error = exc
                self._mark_disconnected()

        raise ApiConnectionLostError(
            correlation_id=correlation_id,
            request_may_have_been_sent=True,
            cause=last_error,
        )

    def _connect_at(
        self,
        session,
        sequence,
        require_exact,
    ):
        session = session or ""
        sequence = int(sequence)

        if self.soup_session is not None:
            self.soup_session.close()

        soup_session = (
            self._new_soup_session()
        )

        try:
            soup_session.connect()

            accepted = soup_session.login(
                username=self.username,
                password=self.password,
                session=session,
                sequence=sequence,
            )

            if require_exact and (
                accepted.session != session
                or accepted.sequence
                != sequence
            ):
                raise ApiError(
                    "API resume mismatch: "
                    "requested_session=%r "
                    "accepted_session=%r "
                    "requested_sequence=%d "
                    "accepted_sequence=%d"
                    % (
                        session,
                        accepted.session,
                        sequence,
                        accepted.sequence,
                    )
                )

        except Exception:
            soup_session.close()
            raise

        self.soup_session = soup_session
        self._login_accepted = accepted
        self._accepted_session = (
            accepted.session
        )
        self._next_sequence = (
            soup_session.next_sequence
        )

        return accepted

    def _receive_result(
        self,
        correlation_id,
    ):
        try:
            payload = (
                self.soup_session
                .receive_sequenced()
            )

        finally:
            self._capture_sequence()

        message_type = (
            self.message_format
            .get_message_type(payload)
        )

        if message_type not in (
            ApiMessageType.ACCEPT_RESPONSE,
            ApiMessageType.REJECT_RESPONSE,
        ):
            raise ApiError(
                "unexpected API response type: %d"
                % message_type
            )

        response = self.message_format.decode(
            message_type,
            payload,
        )

        response_correlation_id = response[
            "correlation_id"
        ]

        if (
            response_correlation_id
            != correlation_id
        ):
            raise ApiError(
                "correlation ID mismatch: "
                "expected %d, received %d"
                % (
                    correlation_id,
                    response_correlation_id,
                )
            )

        if (
            message_type
            == ApiMessageType.REJECT_RESPONSE
        ):
            reject_reason = response[
                "reject_reason"
            ]

            reject_text = (
                self.message_format
                .get_reject_reason(
                    reject_reason
                )
            )

            raise ApiRequestRejectedError(
                correlation_id=correlation_id,
                reject_reason=reject_reason,
                reject_text=reject_text,
            )

    def _capture_sequence(self):
        if self.soup_session is None:
            return

        next_sequence = (
            self.soup_session.next_sequence
        )

        if next_sequence is not None:
            self._next_sequence = (
                next_sequence
            )

    def _mark_disconnected(self):
        with self._connection_lock:
            if self.soup_session is not None:
                self._capture_sequence()
                self.soup_session.close()

            self._login_accepted = None

    def _new_soup_session(self):
        return SoupSession(
            TcpSocket(
                host=self.host,
                port=self.port,
                timeout_seconds=(
                    self.timeout_seconds
                ),
            )
        )

    def _next_correlation_id(self):
        with self._correlation_lock:
            correlation_id = int(
                time.time() * 1_000_000
            )

            if (
                correlation_id
                <= self._last_correlation_id
            ):
                correlation_id = (
                    self._last_correlation_id
                    + 1
                )

            self._last_correlation_id = (
                correlation_id
            )

            return correlation_id

    @staticmethod
    def _normalize_user_state(state):
        if isinstance(state, UserState):
            return state

        try:
            return UserState(state)

        except ValueError as exc:
            raise ValueError(
                "state must be A or S"
            ) from exc

    @staticmethod
    def _normalize_firm_state(state):
        if isinstance(state, FirmState):
            return state

        try:
            return FirmState(state)

        except ValueError as exc:
            raise ValueError(
                "state must be A or S"
            ) from exc
