#!/usr/bin/env python3

import copy

from backend.web.http_app import (
    create_http_app,
)
from backend.web.state_api import (
    StateApi,
)


class FakeEventBus:
    def __init__(self):
        self.latest_event_id = 11


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
                    "firm_name": (
                        "Japannext Internal QA"
                    ),
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
        return copy.deepcopy(
            self._snapshot
        )

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


def assert_json_response(
    response,
    expected_status,
):
    if response.status_code != expected_status:
        raise AssertionError(
            "unexpected HTTP status: "
            "expected=%d actual=%d body=%r"
            % (
                expected_status,
                response.status_code,
                response.get_data(
                    as_text=True
                ),
            )
        )

    if not response.is_json:
        raise AssertionError(
            "response is not JSON"
        )

    if (
        response.headers.get(
            "Cache-Control"
        )
        != "no-store"
    ):
        raise AssertionError(
            "cache-control header mismatch"
        )

    return response.get_json()


def main():
    state_api = StateApi(
        application_state=(
            FakeApplicationState()
        ),
        drop_service=(
            FakeDropService()
        ),
    )

    app = create_http_app(
        state_api
    )

    app.testing = True

    client = app.test_client()

    health = assert_json_response(
        client.get("/health"),
        200,
    )

    if health["status"] != "ok":
        raise AssertionError(
            "health response mismatch"
        )

    if health["drop_session"] != "1785458280":
        raise AssertionError(
            "health session mismatch"
        )

    print(
        "HTTP health endpoint: PASSED"
    )

    status = assert_json_response(
        client.get(
            "/api/v1/status"
        ),
        200,
    )

    if (
        status["drop"]["next_soup_sequence"]
        != 8920
    ):
        raise AssertionError(
            "HTTP status response mismatch"
        )

    print(
        "HTTP status endpoint: PASSED"
    )

    session = assert_json_response(
        client.get(
            "/api/v1/session"
        ),
        200,
    )

    if (
        session["item"]["trade_date"]
        ["trade_date"]
        != 20260731
    ):
        raise AssertionError(
            "HTTP session response mismatch"
        )

    print(
        "HTTP session endpoint: PASSED"
    )

    users = assert_json_response(
        client.get(
            "/api/v1/users"
        ),
        200,
    )

    if users["count"] != 2:
        raise AssertionError(
            "HTTP user count mismatch"
        )

    if [
        record["user_id"]
        for record in users["items"]
    ] != [400, 402]:
        raise AssertionError(
            "HTTP user ordering mismatch"
        )

    print(
        "HTTP user list endpoint: PASSED"
    )

    user = assert_json_response(
        client.get(
            "/api/v1/users/402"
        ),
        200,
    )

    if user["item"]["state"] != "S":
        raise AssertionError(
            "HTTP user response mismatch"
        )

    if user["latest_event_id"] != 11:
        raise AssertionError(
            "HTTP user event ID mismatch"
        )

    print(
        "HTTP single user endpoint: PASSED"
    )

    firms = assert_json_response(
        client.get(
            "/api/v1/firms"
        ),
        200,
    )

    if firms["count"] != 1:
        raise AssertionError(
            "HTTP firm count mismatch"
        )

    firm = assert_json_response(
        client.get(
            "/api/v1/firms/2"
        ),
        200,
    )

    if (
        firm["item"]["firm_code"]
        != "00099900"
    ):
        raise AssertionError(
            "HTTP firm response mismatch"
        )

    print(
        "HTTP firm endpoints: PASSED"
    )

    markets = assert_json_response(
        client.get(
            "/api/v1/markets"
        ),
        200,
    )

    if markets["count"] != 1:
        raise AssertionError(
            "HTTP market count mismatch"
        )

    market = assert_json_response(
        client.get(
            "/api/v1/markets/16"
        ),
        200,
    )

    if (
        market["item"]["market_name"]
        != "XNET"
    ):
        raise AssertionError(
            "HTTP market response mismatch"
        )

    print(
        "HTTP market endpoints: PASSED"
    )

    missing_user = assert_json_response(
        client.get(
            "/api/v1/users/999999"
        ),
        404,
    )

    if (
        missing_user["error"]["code"]
        != "not_found"
    ):
        raise AssertionError(
            "HTTP not-found response mismatch"
        )

    if (
        missing_user["error"]
        ["entity_type"]
        != "user"
    ):
        raise AssertionError(
            "HTTP not-found entity mismatch"
        )

    print(
        "HTTP state not-found response: PASSED"
    )

    invalid_user = assert_json_response(
        client.get(
            "/api/v1/users/0"
        ),
        400,
    )

    if (
        invalid_user["error"]["code"]
        != "bad_request"
    ):
        raise AssertionError(
            "HTTP bad-request response mismatch"
        )

    print(
        "HTTP bad-request response: PASSED"
    )

    missing_route = assert_json_response(
        client.get(
            "/api/v1/unknown"
        ),
        404,
    )

    if (
        missing_route["error"]["code"]
        != "not_found"
    ):
        raise AssertionError(
            "HTTP route response mismatch"
        )

    print(
        "HTTP route not-found response: PASSED"
    )

    wrong_method = assert_json_response(
        client.post(
            "/api/v1/users"
        ),
        405,
    )

    if (
        wrong_method["error"]["code"]
        != "method_not_allowed"
    ):
        raise AssertionError(
            "HTTP method response mismatch"
        )

    print(
        "HTTP method-not-allowed response: PASSED"
    )
    print(
        "HTTP application test: PASSED"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
