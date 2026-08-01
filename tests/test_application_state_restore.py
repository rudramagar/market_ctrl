#!/usr/bin/env python3

import copy

from backend.state.application_state import (
    ApplicationState,
)


def main():
    original = ApplicationState()

    snapshot = {
        "users": [
            {
                "user_index": 1,
                "user_id": 402,
                "user_name": "TX99900C",
                "liquidity_provider": False,
                "state": "A",
                "firm_index": 2,
                "firm_id": 2,
                "executing_firm": "00099900",
                "capacity": "A",
                "clearing_firm": "",
                "clearing_ref": "",
                "allow_override": False,
                "live_order_limit": 1000,
                "user_type_id": 4,
                "definition_sequence": 8400,
                "definition_timestamp_ns": 100,
                "state_sequence": 8440,
                "state_timestamp_ns": 200,
                "last_sequence": 8440,
                "last_timestamp_ns": 200,
            }
        ],
        "firms": [
            {
                "firm_index": 2,
                "firm_id": 2,
                "firm_code": "00099900",
                "psms_code": "",
                "firm_name": (
                    "Japannext co., ltd. Internal QA."
                ),
                "firm_type": "B",
                "state": "A",
                "definition_sequence": 8390,
                "definition_timestamp_ns": 100,
                "state_sequence": 8394,
                "state_timestamp_ns": 200,
                "last_sequence": 8394,
                "last_timestamp_ns": 200,
            }
        ],
        "markets": [
            {
                "market_index": 1,
                "market_id": 16,
                "market_name": "XNET",
                "market_trading_session": 0,
                "state": None,
                "phase": 2,
                "phase_name": "OPEN",
                "definition_sequence": 8402,
                "definition_timestamp_ns": 100,
                "state_sequence": 0,
                "state_timestamp_ns": 0,
                "phase_sequence": 8682,
                "phase_timestamp_ns": 200,
                "last_sequence": 8682,
                "last_timestamp_ns": 200,
            }
        ],
        "references": {
            "user_types": [
                {
                    "user_type_index": 4,
                    "user_type_id": 4,
                    "user_type_name": "fix",
                    "last_sequence": 8401,
                    "last_timestamp_ns": 100,
                }
            ],
            "user_markets": [
                {
                    "user_market_index": 1,
                    "user_id": 402,
                    "market_id": 16,
                    "last_sequence": 8430,
                    "last_timestamp_ns": 100,
                }
            ],
        },
        "session": {
            "trading_engine": None,
            "trade_date": {
                "trade_date": 20260731,
                "calendar_date": 20260731,
                "last_sequence": 8405,
                "last_timestamp_ns": 100,
            },
            "system_events": [],
            "last_system_event": None,
            "end_session_dispatched": False,
        },
    }

    restored_counts = original.restore(
        copy.deepcopy(snapshot)
    )

    restored_snapshot = original.snapshot()

    if restored_snapshot != snapshot:
        raise AssertionError(
            "restored snapshot does not match "
            "the original snapshot"
        )

    expected_counts = {
        "users": 1,
        "firms": 1,
        "markets": 1,
        "user_types": 1,
        "user_markets": 1,
        "system_events": 0,
    }

    if restored_counts != expected_counts:
        raise AssertionError(
            "unexpected restored counts: %r"
            % restored_counts
        )

    if original.counts() != expected_counts:
        raise AssertionError(
            "unexpected application counts: %r"
            % original.counts()
        )

    print(
        "application state restore: PASSED"
    )
    print(
        "snapshot round trip: PASSED"
    )
    print(
        "counts: %r"
        % restored_counts
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
