#!/usr/bin/env python3

import json
from urllib.request import urlopen

from backend.web.http_app import (
    create_http_app,
)
from backend.web.http_server import (
    HttpServer,
)


class FakeStateApi:
    def health(self):
        return {
            "status": "ok",
            "drop_configured": True,
            "drop_running": True,
            "drop_session": "1785458280",
            "last_error": None,
            "state_counts": {
                "users": 70,
                "firms": 5,
                "markets": 1,
                "user_types": 4,
                "user_markets": 46,
                "system_events": 11,
            },
            "latest_event_id": 0,
        }

    def status(self):
        return {
            "state": {
                "counts": {
                    "users": 70,
                },
                "latest_event_id": 0,
            },
            "drop": {
                "running": True,
            },
        }

    def get_session(self):
        return {
            "item": {
                "trade_date": {
                    "trade_date": 20260731,
                },
            },
            "latest_event_id": 0,
        }

    def list_users(self):
        return {
            "items": [],
            "count": 0,
            "latest_event_id": 0,
        }

    def get_user(self, user_id):
        return {
            "item": {
                "user_id": user_id,
            },
            "latest_event_id": 0,
        }

    def list_firms(self):
        return {
            "items": [],
            "count": 0,
            "latest_event_id": 0,
        }

    def get_firm(self, firm_id):
        return {
            "item": {
                "firm_id": firm_id,
            },
            "latest_event_id": 0,
        }

    def list_markets(self):
        return {
            "items": [],
            "count": 0,
            "latest_event_id": 0,
        }

    def get_market(self, market_id):
        return {
            "item": {
                "market_id": market_id,
            },
            "latest_event_id": 0,
        }


def main():
    application = create_http_app(
        FakeStateApi()
    )

    server = HttpServer(
        application=application,
        host="127.0.0.1",
        port=0,
    )

    try:
        server.start()

        if not server.running:
            raise AssertionError(
                "HTTP server did not start"
            )

        if not server.bound_port:
            raise AssertionError(
                "HTTP server has no bound port"
            )

        url = (
            "http://127.0.0.1:%d/health"
            % server.bound_port
        )

        with urlopen(
            url,
            timeout=5.0,
        ) as response:
            if response.status != 200:
                raise AssertionError(
                    "unexpected HTTP status: %d"
                    % response.status
                )

            payload = json.loads(
                response.read().decode(
                    "utf-8"
                )
            )

        if payload["status"] != "ok":
            raise AssertionError(
                "health payload mismatch"
            )

        if (
            payload["state_counts"]["users"]
            != 70
        ):
            raise AssertionError(
                "health state count mismatch"
            )

        print(
            "HTTP listener start: PASSED"
        )
        print(
            "real HTTP request: PASSED"
        )

    finally:
        if not server.stop():
            raise AssertionError(
                "HTTP server did not stop"
            )

    if server.running:
        raise AssertionError(
            "HTTP server is still running"
        )

    print(
        "HTTP listener shutdown: PASSED"
    )
    print(
        "HTTP server test: PASSED"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
