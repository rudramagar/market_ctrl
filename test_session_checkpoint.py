#!/usr/bin/env python3

import os
import shutil
import tempfile

from backend.checkpoint.session_checkpoint import (
    CHECKPOINT_FORMAT_VERSION,
    SessionCheckpoint,
)
from backend.checkpoint.snapshot_store import (
    SnapshotStore,
)
from backend.state.application_state import (
    ApplicationState,
)


def build_application_snapshot():
    return {
        "users": [],
        "firms": [],
        "markets": [],
        "references": {
            "user_types": [],
            "user_markets": [],
        },
        "session": {
            "trading_engine": None,
            "trade_date": {
                "trade_date": 20260731,
                "calendar_date": 20260731,
                "last_sequence": 8700,
                "last_timestamp_ns": 1000,
            },
            "system_events": [],
            "last_system_event": None,
            "end_session_dispatched": False,
        },
    }


def main():
    test_directory = tempfile.mkdtemp(
        prefix="market-control-checkpoint-"
    )

    checkpoint_path = os.path.join(
        test_directory,
        "current_session.json",
    )

    try:
        application_state = ApplicationState()

        original_snapshot = (
            build_application_snapshot()
        )

        application_state.restore(
            original_snapshot
        )

        snapshot_store = SnapshotStore(
            checkpoint_path
        )

        session_checkpoint = (
            SessionCheckpoint(
                snapshot_store=(
                    snapshot_store
                ),
                application_state=(
                    application_state
                ),
            )
        )

        print(
            "test directory: %s"
            % test_directory
        )

        if session_checkpoint.load() is not None:
            raise AssertionError(
                "new checkpoint store "
                "must be empty"
            )

        print(
            "empty checkpoint: PASSED"
        )

        saved = session_checkpoint.save(
            soup_session="1785458280",
            next_soup_sequence=8755,
        )

        if not session_checkpoint.exists:
            raise AssertionError(
                "checkpoint file was not created"
            )

        if (
            saved["format_version"]
            != CHECKPOINT_FORMAT_VERSION
        ):
            raise AssertionError(
                "unexpected format version"
            )

        if (
            saved["soup_session"]
            != "1785458280"
        ):
            raise AssertionError(
                "unexpected Soup session"
            )

        if (
            saved["next_soup_sequence"]
            != 8755
        ):
            raise AssertionError(
                "unexpected Soup sequence"
            )

        if saved["trade_date"] != 20260731:
            raise AssertionError(
                "unexpected trade date"
            )

        if saved["state"] != original_snapshot:
            raise AssertionError(
                "saved application state changed"
            )

        print(
            "checkpoint save: PASSED"
        )

        loaded = session_checkpoint.load()

        if loaded != saved:
            raise AssertionError(
                "loaded checkpoint does not "
                "match saved checkpoint"
            )

        print(
            "checkpoint load: PASSED"
        )

        application_state.clear()

        empty_counts = application_state.counts()

        expected_empty_counts = {
            "users": 0,
            "firms": 0,
            "markets": 0,
            "user_types": 0,
            "user_markets": 0,
            "system_events": 0,
        }

        if empty_counts != expected_empty_counts:
            raise AssertionError(
                "application state did not clear: %r"
                % empty_counts
            )

        restored = (
            session_checkpoint.restore()
        )

        if restored is None:
            raise AssertionError(
                "checkpoint was not restored"
            )

        if (
            restored["soup_session"]
            != "1785458280"
        ):
            raise AssertionError(
                "restored Soup session mismatch"
            )

        if (
            restored["next_soup_sequence"]
            != 8755
        ):
            raise AssertionError(
                "restored Soup sequence mismatch"
            )

        if restored["trade_date"] != 20260731:
            raise AssertionError(
                "restored trade date mismatch"
            )

        restored_snapshot = (
            application_state.snapshot()
        )

        if restored_snapshot != original_snapshot:
            raise AssertionError(
                "restored application state "
                "does not match original"
            )

        print(
            "checkpoint restore: PASSED"
        )
        print(
            "state snapshot round trip: PASSED"
        )
        print(
            "restored counts: %r"
            % restored["restored_counts"]
        )

        if not session_checkpoint.delete():
            raise AssertionError(
                "checkpoint was not deleted"
            )

        if session_checkpoint.exists:
            raise AssertionError(
                "checkpoint still exists"
            )

        if session_checkpoint.restore() is not None:
            raise AssertionError(
                "deleted checkpoint should "
                "restore as None"
            )

        print(
            "checkpoint delete: PASSED"
        )
        print(
            "session checkpoint test: PASSED"
        )

        return 0

    finally:
        shutil.rmtree(
            test_directory,
            ignore_errors=True,
        )


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
