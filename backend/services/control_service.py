from dataclasses import dataclass
from threading import RLock

from backend.protocol.api.messages import (
    FirmState,
    MarketState,
    UserState,
)
from backend.protocol.errors import (
    ControlTimeoutError,
)


@dataclass(frozen=True)
class ControlResult:
    entity_type: str
    entity_id: int
    requested_state: str
    correlation_id: int
    confirmed_sequence: int
    confirmed_timestamp_ns: int


class ControlService:
    """Send API control requests and confirm them through DROP."""

    def __init__(
        self,
        api_client,
        application_state,
        confirmation_timeout_seconds=5.0,
    ):
        if api_client is None:
            raise ValueError(
                "API client is required"
            )

        if application_state is None:
            raise ValueError(
                "application state is required"
            )

        confirmation_timeout_seconds = float(
            confirmation_timeout_seconds
        )

        if confirmation_timeout_seconds <= 0:
            raise ValueError(
                "confirmation timeout must be positive"
            )

        self.api_client = api_client
        self.state = application_state
        self.confirmation_timeout_seconds = (
            confirmation_timeout_seconds
        )

        self._request_lock = RLock()

    def update_user_state(
        self,
        user_id,
        state,
        timeout_seconds=None,
    ):
        user_id = int(user_id)

        state = self._normalize_state(
            UserState,
            state,
        )

        with self._request_lock:
            current = self.state.users.get_user(
                user_id
            )

            previous_sequence = self._get_sequence(
                current
            )

            correlation_id = (
                self.api_client.update_user_state(
                    user_id,
                    state,
                )
            )

            confirmed = (
                self.state.wait_for_user_state(
                    user_id=user_id,
                    expected_state=state,
                    after_sequence=previous_sequence,
                    timeout_seconds=(
                        self._resolve_timeout(
                            timeout_seconds
                        )
                    ),
                )
            )

            return self._build_result(
                entity_type="user",
                entity_id=user_id,
                requested_state=state,
                correlation_id=correlation_id,
                confirmed=confirmed,
            )

    def update_firm_state(
        self,
        firm_id,
        state,
        timeout_seconds=None,
    ):
        firm_id = int(firm_id)

        state = self._normalize_state(
            FirmState,
            state,
        )

        with self._request_lock:
            current = self.state.firms.get_firm(
                firm_id
            )

            previous_sequence = self._get_sequence(
                current
            )

            correlation_id = (
                self.api_client.update_firm_state(
                    firm_id,
                    state,
                )
            )

            confirmed = (
                self.state.wait_for_firm_state(
                    firm_id=firm_id,
                    expected_state=state,
                    after_sequence=previous_sequence,
                    timeout_seconds=(
                        self._resolve_timeout(
                            timeout_seconds
                        )
                    ),
                )
            )

            return self._build_result(
                entity_type="firm",
                entity_id=firm_id,
                requested_state=state,
                correlation_id=correlation_id,
                confirmed=confirmed,
            )

    def update_market_state(
        self,
        market_id,
        state,
        timeout_seconds=None,
    ):
        market_id = int(market_id)

        state = self._normalize_state(
            MarketState,
            state,
        )

        with self._request_lock:
            current = self.state.markets.get_market(
                market_id
            )

            previous_sequence = self._get_sequence(
                current
            )

            correlation_id = (
                self.api_client.update_market_state(
                    market_id,
                    state,
                )
            )

            confirmed = (
                self.state.wait_for_market_state(
                    market_id=market_id,
                    expected_state=state,
                    after_sequence=previous_sequence,
                    timeout_seconds=(
                        self._resolve_timeout(
                            timeout_seconds
                        )
                    ),
                )
            )

            return self._build_result(
                entity_type="market",
                entity_id=market_id,
                requested_state=state,
                correlation_id=correlation_id,
                confirmed=confirmed,
            )

    @staticmethod
    def _normalize_state(state_class, state):
        if isinstance(state, state_class):
            return state.value

        try:
            return state_class(state).value

        except ValueError:
            valid_values = ", ".join(
                item.value
                for item in state_class
            )

            raise ValueError(
                "invalid state %r; expected one of: %s"
                % (
                    state,
                    valid_values,
                )
            )

    def _resolve_timeout(
        self,
        timeout_seconds,
    ):
        if timeout_seconds is None:
            return self.confirmation_timeout_seconds

        timeout_seconds = float(timeout_seconds)

        if timeout_seconds <= 0:
            raise ValueError(
                "confirmation timeout must be positive"
            )

        return timeout_seconds

    @staticmethod
    def _get_sequence(record):
        if record is None:
            return 0

        return record.last_sequence

    @staticmethod
    def _build_result(
        entity_type,
        entity_id,
        requested_state,
        correlation_id,
        confirmed,
    ):
        if confirmed is None:
            raise ControlTimeoutError(
                "DROP did not confirm %s %d state %s"
                % (
                    entity_type,
                    entity_id,
                    requested_state,
                )
            )

        return ControlResult(
            entity_type=entity_type,
            entity_id=entity_id,
            requested_state=requested_state,
            correlation_id=correlation_id,
            confirmed_sequence=(
                confirmed.last_sequence
            ),
            confirmed_timestamp_ns=(
                confirmed.last_timestamp_ns
            ),
        )
