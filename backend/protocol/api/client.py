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
    ApiError,
    ApiRequestRejectedError,
    ProtocolError,
)
from backend.protocol.soup.session import SoupSession
from backend.protocol.transport.socket import TcpSocket


class ApiClient:
    """Matching-engine API client."""

    def __init__(
        self,
        host,
        port,
        username,
        password,
        session="",
        sequence=0,
        timeout_seconds=10.0,
    ):
        tcp_socket = TcpSocket(
            host=host,
            port=port,
            timeout_seconds=timeout_seconds,
        )

        self.username = username
        self.password = password
        self.requested_session = session
        self.requested_sequence = sequence

        self.soup_session = SoupSession(tcp_socket)
        self.message_format = ApiMessageFormat()

        self._login_accepted = None
        self._correlation_lock = threading.Lock()
        self._last_correlation_id = 0

    def connect(self):
        if self._login_accepted is not None:
            return self._login_accepted

        self.soup_session.connect()

        self._login_accepted = self.soup_session.login(
            username=self.username,
            password=self.password,
            session=self.requested_session,
            sequence=self.requested_sequence,
        )

        return self._login_accepted

    def update_user_state(self, user_id, state):
        if user_id <= 0:
            raise ValueError("user_id must be positive")

        state = self._normalize_user_state(state)
        correlation_id = self._next_correlation_id()

        request = self.message_format.encode(
            ApiMessageType.UPDATE_USER_STATE_REQUEST,
            {
                "correlation_id": correlation_id,
                "user_id": user_id,
                "suspension_status": state,
            },
        )

        self.soup_session.send_unsequenced(request)
        self._receive_result(correlation_id)

        return correlation_id

    def close(self):
        try:
            if self._login_accepted is not None:
                self.soup_session.logout()
        except ProtocolError:
            pass
        finally:
            self.soup_session.close()
            self._login_accepted = None

    @property
    def connected(self):
        return (
            self._login_accepted is not None
            and self.soup_session.connected
        )

    def _receive_result(self, correlation_id):
        payload = self.soup_session.receive_sequenced()
        message_type = self.message_format.get_message_type(
            payload
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

        if response_correlation_id != correlation_id:
            raise ApiError(
                "correlation ID mismatch: expected %d, received %d"
                % (
                    correlation_id,
                    response_correlation_id,
                )
            )

        if message_type == ApiMessageType.REJECT_RESPONSE:
            reject_reason = response["reject_reason"]
            reject_text = (
                self.message_format.get_reject_reason(
                    reject_reason
                )
            )

            raise ApiRequestRejectedError(
                correlation_id=correlation_id,
                reject_reason=reject_reason,
                reject_text=reject_text,
            )

    def _next_correlation_id(self):
        with self._correlation_lock:
            correlation_id = int(
                time.time() * 1_000_000
            )

            if correlation_id <= self._last_correlation_id:
                correlation_id = (
                    self._last_correlation_id + 1
                )

            self._last_correlation_id = correlation_id
            return correlation_id

    def update_firm_state(self, firm_id, state):
        if firm_id <= 0:
            raise ValueError("firm_id must be positive")

        state = self._normalize_firm_state(state)
        correlation_id = self._next_correlation_id()

        request = self.message_format.encode(
            ApiMessageType.UPDATE_FIRM_STATE_REQUEST,
            {
                "correlation_id": correlation_id,
                "firm_id": firm_id,
                "suspension_status": state,
            },
        )

        self.soup_session.send_unsequenced(request)
        self._receive_result(correlation_id)

        return correlation_id

    def update_market_state(self, market_id, state):
        state = MarketState.validate(state)
        correlation_id = self._next_correlation_id()

        payload = self.message_format.encode(
            ApiMessageType.UPDATE_MARKET_STATE_REQUEST,
            {
                "correlation_id": correlation_id,
                "market_id": int(market_id),
                "suspension_status": state,
            },
        )

        self.soup_session.send_unsequenced(payload)
        self._receive_result(correlation_id)

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
