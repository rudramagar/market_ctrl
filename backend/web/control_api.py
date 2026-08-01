import copy


ACTIVE_STATE = "A"
SUSPENDED_STATE = "S"

VALID_CONTROL_STATES = (
    ACTIVE_STATE,
    SUSPENDED_STATE,
)


class ControlApiError(Exception):
    """Control API operation failed."""


class ControlNotFoundError(
    ControlApiError
):
    """Requested control entity was not found."""

    def __init__(
        self,
        entity_type,
        entity_id,
    ):
        self.entity_type = entity_type
        self.entity_id = entity_id

        super().__init__(
            "%s %r was not found"
            % (
                entity_type,
                entity_id,
            )
        )


class ControlApi:
    """
    Framework-independent control interface.

    The API validates the requested entity and state,
    calls ControlService, waits for DROP confirmation,
    and returns a JSON-ready dictionary.
    """

    def __init__(
        self,
        control_service,
        application_state,
        default_timeout_seconds=10.0,
    ):
        if control_service is None:
            raise ValueError(
                "control service is required"
            )

        if application_state is None:
            raise ValueError(
                "application state is required"
            )

        default_timeout_seconds = float(
            default_timeout_seconds
        )

        if default_timeout_seconds <= 0:
            raise ValueError(
                "default timeout must be positive"
            )

        self.control_service = (
            control_service
        )
        self.application_state = (
            application_state
        )
        self.default_timeout_seconds = (
            default_timeout_seconds
        )

    def update_user_state(
        self,
        user_id,
        state,
        timeout_seconds=None,
    ):
        user_id = self._validate_entity_id(
            user_id,
            "user ID",
        )

        requested_state = (
            self._validate_state(
                state
            )
        )

        timeout_seconds = (
            self._resolve_timeout(
                timeout_seconds
            )
        )

        current = (
            self.application_state.users
            .get_user(
                user_id
            )
        )

        if current is None:
            raise ControlNotFoundError(
                entity_type="user",
                entity_id=user_id,
            )

        if current.state == requested_state:
            return self._unchanged_response(
                entity_type="user",
                entity_id=user_id,
                requested_state=(
                    requested_state
                ),
                record=current,
            )

        result = (
            self.control_service
            .update_user_state(
                user_id=user_id,
                state=requested_state,
                timeout_seconds=(
                    timeout_seconds
                ),
            )
        )

        confirmed = (
            self.application_state.users
            .get_user(
                user_id
            )
        )

        return self._result_response(
            result=result,
            record=confirmed,
        )

    def update_firm_state(
        self,
        firm_id,
        state,
        timeout_seconds=None,
    ):
        firm_id = self._validate_entity_id(
            firm_id,
            "firm ID",
        )

        requested_state = (
            self._validate_state(
                state
            )
        )

        timeout_seconds = (
            self._resolve_timeout(
                timeout_seconds
            )
        )

        current = (
            self.application_state.firms
            .get_firm(
                firm_id
            )
        )

        if current is None:
            raise ControlNotFoundError(
                entity_type="firm",
                entity_id=firm_id,
            )

        if current.state == requested_state:
            return self._unchanged_response(
                entity_type="firm",
                entity_id=firm_id,
                requested_state=(
                    requested_state
                ),
                record=current,
            )

        result = (
            self.control_service
            .update_firm_state(
                firm_id=firm_id,
                state=requested_state,
                timeout_seconds=(
                    timeout_seconds
                ),
            )
        )

        confirmed = (
            self.application_state.firms
            .get_firm(
                firm_id
            )
        )

        return self._result_response(
            result=result,
            record=confirmed,
        )

    def update_market_state(
        self,
        market_id,
        state,
        timeout_seconds=None,
    ):
        market_id = (
            self._validate_entity_id(
                market_id,
                "market ID",
            )
        )

        requested_state = (
            self._validate_state(
                state
            )
        )

        timeout_seconds = (
            self._resolve_timeout(
                timeout_seconds
            )
        )

        current = (
            self.application_state.markets
            .get_market(
                market_id
            )
        )

        if current is None:
            raise ControlNotFoundError(
                entity_type="market",
                entity_id=market_id,
            )

        if current.state == requested_state:
            return self._unchanged_response(
                entity_type="market",
                entity_id=market_id,
                requested_state=(
                    requested_state
                ),
                record=current,
            )

        result = (
            self.control_service
            .update_market_state(
                market_id=market_id,
                state=requested_state,
                timeout_seconds=(
                    timeout_seconds
                ),
            )
        )

        confirmed = (
            self.application_state.markets
            .get_market(
                market_id
            )
        )

        return self._result_response(
            result=result,
            record=confirmed,
        )

    def suspend_user(
        self,
        user_id,
        timeout_seconds=None,
    ):
        return self.update_user_state(
            user_id=user_id,
            state=SUSPENDED_STATE,
            timeout_seconds=timeout_seconds,
        )

    def activate_user(
        self,
        user_id,
        timeout_seconds=None,
    ):
        return self.update_user_state(
            user_id=user_id,
            state=ACTIVE_STATE,
            timeout_seconds=timeout_seconds,
        )

    def suspend_firm(
        self,
        firm_id,
        timeout_seconds=None,
    ):
        return self.update_firm_state(
            firm_id=firm_id,
            state=SUSPENDED_STATE,
            timeout_seconds=timeout_seconds,
        )

    def activate_firm(
        self,
        firm_id,
        timeout_seconds=None,
    ):
        return self.update_firm_state(
            firm_id=firm_id,
            state=ACTIVE_STATE,
            timeout_seconds=timeout_seconds,
        )

    def suspend_market(
        self,
        market_id,
        timeout_seconds=None,
    ):
        return self.update_market_state(
            market_id=market_id,
            state=SUSPENDED_STATE,
            timeout_seconds=timeout_seconds,
        )

    def activate_market(
        self,
        market_id,
        timeout_seconds=None,
    ):
        return self.update_market_state(
            market_id=market_id,
            state=ACTIVE_STATE,
            timeout_seconds=timeout_seconds,
        )

    def _result_response(
        self,
        result,
        record,
    ):
        if result is None:
            raise ControlApiError(
                "control service returned no result"
            )

        entity_type = self._get_result_value(
            result,
            names=(
                "entity_type",
                "entity",
            ),
        )

        entity_id = self._get_result_value(
            result,
            names=(
                "entity_id",
            ),
        )

        requested_state = (
            self._get_result_value(
                result,
                names=(
                    "requested_state",
                    "state",
                ),
            )
        )

        confirmed_sequence = (
            self._get_result_value(
                result,
                names=(
                    "confirmed_sequence",
                    "matching_engine_sequence",
                    "sequence",
                ),
                required=False,
            )
        )

        confirmed_timestamp_ns = (
            self._get_result_value(
                result,
                names=(
                    "confirmed_timestamp_ns",
                    "timestamp_ns",
                ),
                required=False,
            )
        )

        correlation_id = (
            self._get_result_value(
                result,
                names=(
                    "correlation_id",
                ),
                required=False,
            )
        )

        api_response_confirmed = (
            self._get_result_value(
                result,
                names=(
                    "api_response_confirmed",
                ),
                required=False,
                default=True,
            )
        )

        api_error = self._get_result_value(
            result,
            names=(
                "api_error",
            ),
            required=False,
        )

        confirmed_by_drop = (
            self._get_result_value(
                result,
                names=(
                    "confirmed_by_drop",
                ),
                required=False,
                default=True,
            )
        )

        record_values = (
            self._record_to_dict(
                record
            )
        )

        return {
            "status": "confirmed",
            "changed": True,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "requested_state": (
                requested_state
            ),
            "confirmed_state": (
                record_values.get("state")
                if record_values is not None
                else requested_state
            ),
            "correlation_id": (
                correlation_id
            ),
            "confirmed_sequence": (
                confirmed_sequence
            ),
            "confirmed_timestamp_ns": (
                confirmed_timestamp_ns
            ),
            "api_response_confirmed": (
                bool(
                    api_response_confirmed
                )
            ),
            "confirmed_by_drop": (
                bool(
                    confirmed_by_drop
                )
            ),
            "api_error": api_error,
            "item": record_values,
            "latest_event_id": (
                self._latest_event_id()
            ),
        }

    def _unchanged_response(
        self,
        entity_type,
        entity_id,
        requested_state,
        record,
    ):
        record_values = (
            self._record_to_dict(
                record
            )
        )

        return {
            "status": "unchanged",
            "changed": False,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "requested_state": (
                requested_state
            ),
            "confirmed_state": (
                requested_state
            ),
            "correlation_id": None,
            "confirmed_sequence": (
                record_values.get(
                    "state_sequence",
                    record_values.get(
                        "last_sequence"
                    ),
                )
            ),
            "confirmed_timestamp_ns": (
                record_values.get(
                    "state_timestamp_ns",
                    record_values.get(
                        "last_timestamp_ns"
                    ),
                )
            ),
            "api_response_confirmed": False,
            "confirmed_by_drop": True,
            "api_error": None,
            "item": record_values,
            "latest_event_id": (
                self._latest_event_id()
            ),
        }

    def _latest_event_id(self):
        event_bus = getattr(
            self.application_state,
            "event_bus",
            None,
        )

        if event_bus is None:
            return 0

        return event_bus.latest_event_id

    def _resolve_timeout(
        self,
        timeout_seconds,
    ):
        if timeout_seconds is None:
            return (
                self.default_timeout_seconds
            )

        timeout_seconds = float(
            timeout_seconds
        )

        if timeout_seconds <= 0:
            raise ValueError(
                "timeout must be positive"
            )

        return timeout_seconds

    @staticmethod
    def _validate_state(state):
        if not isinstance(state, str):
            raise TypeError(
                "state must be a string"
            )

        state = state.strip().upper()

        if state not in VALID_CONTROL_STATES:
            raise ValueError(
                "state must be A or S"
            )

        return state

    @staticmethod
    def _validate_entity_id(
        entity_id,
        description,
    ):
        if (
            not isinstance(entity_id, int)
            or isinstance(entity_id, bool)
        ):
            raise TypeError(
                "%s must be an integer"
                % description
            )

        if entity_id < 1:
            raise ValueError(
                "%s must be at least 1"
                % description
            )

        return entity_id

    @staticmethod
    def _record_to_dict(record):
        if record is None:
            return None

        to_dict = getattr(
            record,
            "to_dict",
            None,
        )

        if not callable(to_dict):
            raise ControlApiError(
                "state record cannot be serialized"
            )

        values = to_dict()

        if not isinstance(values, dict):
            raise ControlApiError(
                "state record serialization "
                "must return a dictionary"
            )

        return copy.deepcopy(
            values
        )

    @staticmethod
    def _get_result_value(
        result,
        names,
        required=True,
        default=None,
    ):
        for name in names:
            if hasattr(result, name):
                return getattr(
                    result,
                    name
                )

        if required:
            raise ControlApiError(
                "control result is missing: %s"
                % ", ".join(names)
            )

        return default
