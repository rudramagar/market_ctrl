import logging
from dataclasses import dataclass
from typing import Optional

from backend.protocol.errors import (
    ApiConnectionLostError,
    ControlError,
    ControlTimeoutError,
)


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ControlResult:
    """Confirmed state-control result."""

    entity: str
    entity_id: int
    state: str
    correlation_id: int
    sequence: int

    api_response_confirmed: bool = True
    api_error: Optional[str] = None

    # Backward-compatible names used by existing tests.
    @property
    def entity_type(self):
        return self.entity

    @property
    def requested_state(self):
        return self.state

    @property
    def confirmed_sequence(self):
        return self.sequence

    @property
    def matching_engine_sequence(self):
        return self.sequence

    @property
    def confirmed_by_drop(self):
        return True

    def to_dict(self):
        return {
            "entity": self.entity,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "state": self.state,
            "requested_state": self.requested_state,
            "correlation_id": self.correlation_id,
            "sequence": self.sequence,
            "confirmed_sequence": (
                self.confirmed_sequence
            ),
            "api_response_confirmed": (
                self.api_response_confirmed
            ),
            "confirmed_by_drop": (
                self.confirmed_by_drop
            ),
            "api_error": self.api_error,
        }

class ControlService:
    """
    Send state-control requests through the API and
    confirm the resulting state through DROP.
    """

    def __init__(
        self,
        api_client,
        application_state,
        timeout_seconds=10.0,
        confirmation_timeout_seconds=None,
    ):
        if api_client is None:
            raise ValueError(
                "API client is required"
            )

        if application_state is None:
            raise ValueError(
                "application state is required"
            )

        if confirmation_timeout_seconds is not None:
            timeout_seconds = (
                confirmation_timeout_seconds
            )

        timeout_seconds = float(
            timeout_seconds
        )

        if timeout_seconds <= 0:
            raise ValueError(
                "control timeout must be positive"
            )

        self.api_client = api_client
        self.state = application_state
        self.timeout_seconds = timeout_seconds

    def update_user_state(
        self,
        user_id,
        state,
        timeout_seconds=None,
    ):
        user_id = self._validate_entity_id(
            "user",
            user_id,
        )
        expected_state = (
            self._normalize_state(state)
        )

        return self._execute(
            entity="user",
            entity_id=user_id,
            expected_state=expected_state,
            get_record=lambda: (
                self.state.users.get_user(
                    user_id
                )
            ),
            send_request=lambda: (
                self.api_client
                .update_user_state(
                    user_id,
                    expected_state,
                )
            ),
            wait_for_state=lambda after_sequence,
            wait_timeout: (
                self.state.wait_for_user_state(
                    user_id=user_id,
                    expected_state=(
                        expected_state
                    ),
                    after_sequence=(
                        after_sequence
                    ),
                    timeout_seconds=(
                        wait_timeout
                    ),
                )
            ),
            timeout_seconds=timeout_seconds,
        )

    def update_firm_state(
        self,
        firm_id,
        state,
        timeout_seconds=None,
    ):
        firm_id = self._validate_entity_id(
            "firm",
            firm_id,
        )
        expected_state = (
            self._normalize_state(state)
        )

        return self._execute(
            entity="firm",
            entity_id=firm_id,
            expected_state=expected_state,
            get_record=lambda: (
                self.state.firms.get_firm(
                    firm_id
                )
            ),
            send_request=lambda: (
                self.api_client
                .update_firm_state(
                    firm_id,
                    expected_state,
                )
            ),
            wait_for_state=lambda after_sequence,
            wait_timeout: (
                self.state.wait_for_firm_state(
                    firm_id=firm_id,
                    expected_state=(
                        expected_state
                    ),
                    after_sequence=(
                        after_sequence
                    ),
                    timeout_seconds=(
                        wait_timeout
                    ),
                )
            ),
            timeout_seconds=timeout_seconds,
        )

    def update_market_state(
        self,
        market_id,
        state,
        timeout_seconds=None,
    ):
        market_id = self._validate_entity_id(
            "market",
            market_id,
        )
        expected_state = (
            self._normalize_state(state)
        )

        return self._execute(
            entity="market",
            entity_id=market_id,
            expected_state=expected_state,
            get_record=lambda: (
                self.state.markets.get_market(
                    market_id
                )
            ),
            send_request=lambda: (
                self.api_client
                .update_market_state(
                    market_id,
                    expected_state,
                )
            ),
            wait_for_state=lambda after_sequence,
            wait_timeout: (
                self.state.wait_for_market_state(
                    market_id=market_id,
                    expected_state=(
                        expected_state
                    ),
                    after_sequence=(
                        after_sequence
                    ),
                    timeout_seconds=(
                        wait_timeout
                    ),
                )
            ),
            timeout_seconds=timeout_seconds,
        )

    def suspend_user(
        self,
        user_id,
        timeout_seconds=None,
    ):
        return self.update_user_state(
            user_id,
            "S",
            timeout_seconds,
        )

    def activate_user(
        self,
        user_id,
        timeout_seconds=None,
    ):
        return self.update_user_state(
            user_id,
            "A",
            timeout_seconds,
        )

    def suspend_firm(
        self,
        firm_id,
        timeout_seconds=None,
    ):
        return self.update_firm_state(
            firm_id,
            "S",
            timeout_seconds,
        )

    def activate_firm(
        self,
        firm_id,
        timeout_seconds=None,
    ):
        return self.update_firm_state(
            firm_id,
            "A",
            timeout_seconds,
        )

    def suspend_market(
        self,
        market_id,
        timeout_seconds=None,
    ):
        return self.update_market_state(
            market_id,
            "S",
            timeout_seconds,
        )

    def activate_market(
        self,
        market_id,
        timeout_seconds=None,
    ):
        return self.update_market_state(
            market_id,
            "A",
            timeout_seconds,
        )

    def _execute(
        self,
        entity,
        entity_id,
        expected_state,
        get_record,
        send_request,
        wait_for_state,
        timeout_seconds,
    ):
        current = get_record()

        if current is None:
            raise ControlError(
                "%s %d is not present in DROP state"
                % (
                    entity,
                    entity_id,
                )
            )

        after_sequence = (
            self._get_state_sequence(
                current
            )
        )

        correlation_id = None
        api_response_confirmed = True
        api_error = None

        try:
            correlation_id = send_request()

        except ApiConnectionLostError as exc:
            correlation_id = (
                exc.correlation_id
            )

            if (
                not exc
                .request_may_have_been_sent
            ):
                raise

            api_response_confirmed = False
            api_error = str(exc)

            logger.warning(
                "API response is ambiguous; "
                "checking DROP confirmation: "
                "entity=%s id=%d state=%s "
                "correlation_id=%d "
                "after_sequence=%d",
                entity,
                entity_id,
                expected_state,
                correlation_id,
                after_sequence,
            )

        wait_timeout = (
            self._resolve_timeout(
                timeout_seconds
            )
        )

        record = wait_for_state(
            after_sequence,
            wait_timeout,
        )

        if record is None:
            if not api_response_confirmed:
                raise ControlTimeoutError(
                    "API result is ambiguous and DROP "
                    "did not confirm the request: "
                    "entity=%s id=%d state=%s "
                    "correlation_id=%d "
                    "after_sequence=%d timeout=%.3f"
                    % (
                        entity,
                        entity_id,
                        expected_state,
                        correlation_id,
                        after_sequence,
                        wait_timeout,
                    )
                )

            raise ControlTimeoutError(
                "DROP did not confirm the request: "
                "entity=%s id=%d state=%s "
                "correlation_id=%d "
                "after_sequence=%d timeout=%.3f"
                % (
                    entity,
                    entity_id,
                    expected_state,
                    correlation_id,
                    after_sequence,
                    wait_timeout,
                )
            )

        sequence = (
            self._get_state_sequence(
                record
            )
        )

        logger.info(
            "control confirmed through DROP: "
            "entity=%s id=%d state=%s "
            "correlation_id=%d sequence=%d "
            "api_response_confirmed=%s",
            entity,
            entity_id,
            expected_state,
            correlation_id,
            sequence,
            api_response_confirmed,
        )

        return ControlResult(
            entity=entity,
            entity_id=entity_id,
            state=expected_state,
            correlation_id=correlation_id,
            sequence=sequence,
            api_response_confirmed=(
                api_response_confirmed
            ),
            api_error=api_error,
        )

    def _resolve_timeout(
        self,
        timeout_seconds,
    ):
        if timeout_seconds is None:
            return self.timeout_seconds

        timeout_seconds = float(
            timeout_seconds
        )

        if timeout_seconds <= 0:
            raise ValueError(
                "control timeout must be positive"
            )

        return timeout_seconds

    @staticmethod
    def _get_state_sequence(record):
        """
        Use only the administrative state sequence.

        Definition and market-phase sequences must
        not confirm a state-control request.
        """

        state_sequence = getattr(
            record,
            "state_sequence",
            None,
        )

        if state_sequence is None:
            state_sequence = getattr(
                record,
                "last_sequence",
                0,
            )

        return int(
            state_sequence or 0
        )

    @staticmethod
    def _validate_entity_id(
        entity,
        entity_id,
    ):
        entity_id = int(entity_id)

        if entity_id <= 0:
            raise ValueError(
                "%s ID must be positive"
                % entity
            )

        return entity_id

    @staticmethod
    def _normalize_state(state):
        if hasattr(state, "value"):
            state = state.value

        state = str(state).strip().upper()

        if state not in ("A", "S"):
            raise ValueError(
                "state must be A or S"
            )

        return state
