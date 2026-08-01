#!/usr/bin/env python3


from backend.web.control_api import (
    ControlApi,
    ControlNotFoundError,
)


class FakeRecord:
    def __init__(
        self,
        entity_id,
        state,
        sequence,
        timestamp_ns,
    ):
        self.entity_id = entity_id
        self.state = state
        self.state_sequence = sequence
        self.state_timestamp_ns = (
            timestamp_ns
        )

    def to_dict(self):
        return {
            "entity_id": self.entity_id,
            "state": self.state,
            "state_sequence": (
                self.state_sequence
            ),
            "state_timestamp_ns": (
                self.state_timestamp_ns
            ),
            "last_sequence": (
                self.state_sequence
            ),
            "last_timestamp_ns": (
                self.state_timestamp_ns
            ),
        }


class FakeStore:
    def __init__(self, records):
        self.records = dict(
            records
        )

    def get_user(self, entity_id):
        return self.records.get(
            entity_id
        )

    def get_firm(self, entity_id):
        return self.records.get(
            entity_id
        )

    def get_market(self, entity_id):
        return self.records.get(
            entity_id
        )


class FakeEventBus:
    def __init__(self):
        self.latest_event_id = 10


class FakeApplicationState:
    def __init__(self):
        self.users = FakeStore(
            {
                402: FakeRecord(
                    entity_id=402,
                    state="A",
                    sequence=100,
                    timestamp_ns=100000,
                ),
            }
        )

        self.firms = FakeStore(
            {
                2: FakeRecord(
                    entity_id=2,
                    state="A",
                    sequence=200,
                    timestamp_ns=200000,
                ),
            }
        )

        self.markets = FakeStore(
            {
                16: FakeRecord(
                    entity_id=16,
                    state="A",
                    sequence=300,
                    timestamp_ns=300000,
                ),
            }
        )

        self.event_bus = FakeEventBus()


class FakeControlResult:
    def __init__(
        self,
        entity_type,
        entity_id,
        state,
        correlation_id,
        sequence,
    ):
        self.entity = entity_type
        self.entity_id = entity_id
        self.state = state
        self.correlation_id = correlation_id
        self.sequence = sequence

        self.api_response_confirmed = True
        self.api_error = None

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


class FakeControlService:
    def __init__(
        self,
        application_state,
    ):
        self.application_state = (
            application_state
        )
        self.calls = []
        self.next_correlation_id = 1000

    def update_user_state(
        self,
        user_id,
        state,
        timeout_seconds=None,
    ):
        return self._update(
            entity_type="user",
            entity_id=user_id,
            state=state,
            timeout_seconds=(
                timeout_seconds
            ),
            store=self.application_state.users,
        )

    def update_firm_state(
        self,
        firm_id,
        state,
        timeout_seconds=None,
    ):
        return self._update(
            entity_type="firm",
            entity_id=firm_id,
            state=state,
            timeout_seconds=(
                timeout_seconds
            ),
            store=self.application_state.firms,
        )

    def update_market_state(
        self,
        market_id,
        state,
        timeout_seconds=None,
    ):
        return self._update(
            entity_type="market",
            entity_id=market_id,
            state=state,
            timeout_seconds=(
                timeout_seconds
            ),
            store=self.application_state.markets,
        )

    def _update(
        self,
        entity_type,
        entity_id,
        state,
        timeout_seconds,
        store,
    ):
        self.calls.append(
            {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "state": state,
                "timeout_seconds": (
                    timeout_seconds
                ),
            }
        )

        current = store.records[
            entity_id
        ]

        sequence = (
            current.state_sequence
            + 1
        )

        store.records[entity_id] = (
            FakeRecord(
                entity_id=entity_id,
                state=state,
                sequence=sequence,
                timestamp_ns=(
                    sequence * 1000
                ),
            )
        )

        self.application_state.event_bus.latest_event_id += 1

        self.next_correlation_id += 1

        return FakeControlResult(
            entity_type=entity_type,
            entity_id=entity_id,
            state=state,
            correlation_id=(
                self.next_correlation_id
            ),
            sequence=sequence,
        )


def main():
    application_state = (
        FakeApplicationState()
    )

    control_service = (
        FakeControlService(
            application_state
        )
    )

    control_api = ControlApi(
        control_service=control_service,
        application_state=(
            application_state
        ),
        default_timeout_seconds=5.0,
    )

    user_result = (
        control_api.update_user_state(
            user_id=402,
            state="S",
        )
    )

    if user_result["status"] != "confirmed":
        raise AssertionError(
            "user result status mismatch"
        )

    if not user_result["changed"]:
        raise AssertionError(
            "user change flag mismatch"
        )

    if (
        user_result["confirmed_state"]
        != "S"
    ):
        raise AssertionError(
            "user confirmed state mismatch"
        )

    if (
        user_result["confirmed_sequence"]
        != 101
    ):
        raise AssertionError(
            "user sequence mismatch"
        )

    if (
        control_service.calls[0]
        ["timeout_seconds"]
        != 5.0
    ):
        raise AssertionError(
            "default timeout mismatch"
        )

    print(
        "user control result: PASSED"
    )

    firm_result = (
        control_api.suspend_firm(
            firm_id=2,
            timeout_seconds=3.0,
        )
    )

    if (
        firm_result["entity_type"]
        != "firm"
    ):
        raise AssertionError(
            "firm entity type mismatch"
        )

    if (
        firm_result["confirmed_state"]
        != "S"
    ):
        raise AssertionError(
            "firm confirmed state mismatch"
        )

    print(
        "firm control result: PASSED"
    )

    market_result = (
        control_api.suspend_market(
            market_id=16,
        )
    )

    if (
        market_result["entity_type"]
        != "market"
    ):
        raise AssertionError(
            "market entity type mismatch"
        )

    if (
        market_result["confirmed_state"]
        != "S"
    ):
        raise AssertionError(
            "market confirmed state mismatch"
        )

    print(
        "market control result: PASSED"
    )

    call_count = len(
        control_service.calls
    )

    unchanged = (
        control_api.update_user_state(
            user_id=402,
            state="S",
        )
    )

    if unchanged["status"] != "unchanged":
        raise AssertionError(
            "unchanged status mismatch"
        )

    if unchanged["changed"]:
        raise AssertionError(
            "unchanged change flag mismatch"
        )

    if (
        unchanged["api_response_confirmed"]
    ):
        raise AssertionError(
            "unchanged request should not call API"
        )

    if (
        len(control_service.calls)
        != call_count
    ):
        raise AssertionError(
            "unchanged request called "
            "ControlService"
        )

    print(
        "idempotent control request: PASSED"
    )

    try:
        control_api.update_user_state(
            user_id=999999,
            state="S",
        )

    except ControlNotFoundError as exc:
        if exc.entity_type != "user":
            raise AssertionError(
                "not-found entity mismatch"
            )

    else:
        raise AssertionError(
            "missing user was not rejected"
        )

    print(
        "missing entity detection: PASSED"
    )

    try:
        control_api.update_user_state(
            user_id=402,
            state="D",
        )

    except ValueError:
        pass

    else:
        raise AssertionError(
            "invalid state was not rejected"
        )

    print(
        "invalid state detection: PASSED"
    )

    try:
        control_api.update_user_state(
            user_id=402,
            state="A",
            timeout_seconds=0,
        )

    except ValueError:
        pass

    else:
        raise AssertionError(
            "invalid timeout was not rejected"
        )

    print(
        "invalid timeout detection: PASSED"
    )
    print(
        "control API test: PASSED"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
