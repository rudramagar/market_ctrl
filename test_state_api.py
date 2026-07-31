#!/usr/bin/env python3

from backend.web.state_api import (
    StateApi,
    StateNotFoundError,
)


class FakeEventBus:
    def __init__(self):
        self.latest_event_id = 7


class FakeApplicationState:
    def __init__(self):
        self.event_bus = FakeEventBus()

        self._snapshot = {
            "users": [
                {
                    "user_id": 402,
                    "user_name": "TX99900C",
                    "state": "S",
                    "last_sequence": 8918,
                },
                {
                    "user_id": 400,
                    "user_name": "TX99900A",
                    "state": "A",
                    "last_sequence": 8910,
                },
            ],
            "firms": [
                {
                    "firm_id": 2,
                    "firm_code": "00099900",
                    "state": "A",
                },
            ],
            "markets": [
                {
                    "market_id": 16,
                    "market_name": "XNET",
                    "state": None,
                    "phase": 2,
                },
            ],
            "references": {
                "user_types": [],
                "user_markets": [],
            },
            "session": {
                "trade_date": {
                    "trade_date": 20260731,
                    "calendar_date": 20260731,
                },
                "trading_engine": {
                    "session_id": 1,
                    "trading_session_mode": "T",
                },
                "system_events": [],
                "last_system_event": None,
                "end_session_dispatched": False,
            },
        }

    def snapshot(self):
        return {
            "users": [
                dict(record)
                for record in self._snapshot[
                    "users"
                ]
            ],
            "firms": [
                dict(record)
                for record in self._snapshot[
                    "firms"
                ]
            ],
            "markets": [
                dict(record)
                for record in self._snapshot[
                    "markets"
                ]
            ],
            "references": {
                "user_types": [],
                "user_markets": [],
            },
            "session": {
                "trade_date": dict(
                    self._snapshot[
                        "session"
                    ]["trade_date"]
                ),
                "trading_engine": dict(
                    self._snapshot[
                        "session"
                    ]["trading_engine"]
                ),
                "system_events": [],
                "last_system_event": None,
                "end_session_dispatched": False,
            },
        }

    def counts(self):
        return {
            "users": 2,
            "firms": 1,
            "markets": 1,
            "user_types": 0,
            "user_markets": 0,
            "system_events": 0,
        }


class FakeDropService:
    def status(self):
        return {
            "running": True,
            "started": True,
            "finished": False,
            "received_messages": 145,
            "applied_messages": 145,
            "connections": 1,
            "reconnects": 0,
            "full_replay_fallbacks": 0,
            "current_session": "1785458280",
            "requested_session": "1785458280",
            "accepted_session": "1785458280",
            "requested_sequence": 8910,
            "accepted_sequence": 8910,
            "next_soup_sequence": 8920,
            "disconnect_reason": None,
            "unsupported_templates": [
                9,
                23,
            ],
            "last_error": None,
            "checkpoint_enabled": True,
            "checkpoint_restored": True,
            "checkpoint_saves": 2,
            "checkpoint_last_saved_at": (
                "2026-07-31T08:20:00.000000Z"
            ),
            "checkpoint_last_error": None,
            "checkpoint_restored_trade_date": (
                20260731
            ),
            "checkpoint_restored_sequence": (
                8910
            ),
        }


def main():
    application_state = (
        FakeApplicationState()
    )

    state_api = StateApi(
        application_state=(
            application_state
        ),
        drop_service=FakeDropService(),
    )

    health = state_api.health()

    if health["status"] != "ok":
        raise AssertionError(
            "health status mismatch"
        )

    if not health["drop_running"]:
        raise AssertionError(
            "DROP health mismatch"
        )

    if health["latest_event_id"] != 7:
        raise AssertionError(
            "health event ID mismatch"
        )

    print(
        "health response: PASSED"
    )

    status = state_api.status()

    if (
        status["drop"]["current_session"]
        != "1785458280"
    ):
        raise AssertionError(
            "DROP status session mismatch"
        )

    if (
        status["state"]["counts"]["users"]
        != 2
    ):
        raise AssertionError(
            "state status count mismatch"
        )

    print(
        "status response: PASSED"
    )

    users = state_api.list_users()

    if users["count"] != 2:
        raise AssertionError(
            "user count mismatch"
        )

    user_ids = [
        record["user_id"]
        for record in users["items"]
    ]

    if user_ids != [400, 402]:
        raise AssertionError(
            "users were not sorted: %r"
            % user_ids
        )

    print(
        "user list response: PASSED"
    )

    user = state_api.get_user(
        402
    )

    if user["item"]["state"] != "S":
        raise AssertionError(
            "single user state mismatch"
        )

    if user["latest_event_id"] != 7:
        raise AssertionError(
            "single user event ID mismatch"
        )

    print(
        "single user response: PASSED"
    )

    firms = state_api.list_firms()

    if firms["items"][0]["firm_id"] != 2:
        raise AssertionError(
            "firm list mismatch"
        )

    firm = state_api.get_firm(
        2
    )

    if (
        firm["item"]["firm_code"]
        != "00099900"
    ):
        raise AssertionError(
            "single firm mismatch"
        )

    print(
        "firm responses: PASSED"
    )

    markets = state_api.list_markets()

    if (
        markets["items"][0]["market_id"]
        != 16
    ):
        raise AssertionError(
            "market list mismatch"
        )

    market = state_api.get_market(
        16
    )

    if (
        market["item"]["market_name"]
        != "XNET"
    ):
        raise AssertionError(
            "single market mismatch"
        )

    print(
        "market responses: PASSED"
    )

    session = state_api.get_session()

    if (
        session["item"]["trade_date"]
        ["trade_date"]
        != 20260731
    ):
        raise AssertionError(
            "session response mismatch"
        )

    # Verify returned data cannot mutate the source.
    session["item"]["trade_date"][
        "trade_date"
    ] = 1

    original_session = (
        application_state.snapshot()
        ["session"]
    )

    if (
        original_session["trade_date"]
        ["trade_date"]
        != 20260731
    ):
        raise AssertionError(
            "session response mutated state"
        )

    print(
        "session response: PASSED"
    )

    try:
        state_api.get_user(
            999999
        )

    except StateNotFoundError as exc:
        if exc.entity_type != "user":
            raise AssertionError(
                "not-found entity mismatch"
            )

    else:
        raise AssertionError(
            "missing user was not rejected"
        )

    print(
        "not-found response: PASSED"
    )
    print(
        "state API test: PASSED"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
